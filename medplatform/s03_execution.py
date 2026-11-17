"""A7 explicit execution and O5 notifications. Importing starts no workers."""
import copy
import json
import threading
from datetime import datetime, time, timedelta

from .auth import digest
from .documents import all_docs, changed, encode, expected, fingerprint, get, meta, stamp, uid
from .errors import AppError
from .idempotency import Result
from .s02_service import SHANGHAI
from . import s03_execution_inputs as inputs

ROUTES = (
    ('A33','POST','/tasks','task_create',inputs.TaskCreateInput),
    ('A34','GET','/tasks/{id}','task',None),
    ('A35','GET','/patients/{p}/tasks','tasks',None),
    ('A36','POST','/tasks/{id}/run','task_run',inputs.TaskRunInput),
    ('A37','POST','/tasks/{id}/cancel','task_cancel',inputs.TaskCancelInput),
    ('A38','GET','/executions/{id}','execution',None),
    ('A39','GET','/tasks/{id}/executions','executions',None),
    ('A40','POST','/integrations/delivery-receipts','delivery_receipt',inputs.DeliveryReceiptInput),
    ('F-API01','POST','/patients/{p}/reminder-snoozes','reminder_snooze',inputs.ReminderSnoozeInput),
)
query_input = inputs.query_input
READS = {'task','tasks','execution','executions'}
TERMINAL = {'succeeded','failed','cancelled','expired'}
RULE = 'flow-v0.1-reminder-v1'


class S03Execution:
    def __init__(self, db, auth, receipts, clock, analytics=None):
        self.db, self.auth, self.receipts, self.clock = db, auth, receipts, clock
        self.analytics = analytics
        self.support_state = None
        self.instance_id = uid()
        # This local adapter performs no external effect. Tests may inject a
        # registered deterministic failure; there is no public adapter selector.
        self.delivery_adapter = lambda task, execution: {'delivery_status':'submitted'}

    def _task(self, c, identifier):
        row = c.execute('SELECT document_json FROM a_tasks WHERE task_id=?',(identifier,)).fetchone()
        if not row:
            raise AppError(404,'RESOURCE_NOT_FOUND','任务不可访问或不存在')
        return json.loads(row[0])

    def _execution(self, c, identifier):
        row = c.execute('SELECT document_json FROM a_executions WHERE execution_id=?',(identifier,)).fetchone()
        if not row:
            raise AppError(404,'RESOURCE_NOT_FOUND','执行不可访问或不存在')
        return json.loads(row[0])

    def _save_task(self, c, task, creator=None, *, new=False):
        raw=encode(task)
        if new:
            c.execute('INSERT INTO a_tasks VALUES (?,?,?,?,?,?,?)',
                      (task['task_id'],task['patient_id'],'demo',task['owner_module'],task['owner_operation_key'],creator,raw))
        else:
            c.execute('UPDATE a_tasks SET document_json=? WHERE task_id=?',(raw,task['task_id']))
        c.execute('INSERT INTO a_task_history VALUES (?,?,?)',(task['task_id'],task['meta']['revision'],raw))
        return task

    def _save_execution(self,c,execution,*,new=False):
        if new:
            c.execute('INSERT INTO a_executions VALUES (?,?,?,?)',
                      (execution['execution_id'],execution['task_id'],execution['attempt'],encode(execution)))
        else:
            c.execute('UPDATE a_executions SET document_json=? WHERE execution_id=?',
                      (encode(execution),execution['execution_id']))

    def _admin(self,c,principal):
        if principal is None:
            return  # Only explicit Python/CLI service calls may pass None.
        if not self.auth.account(principal,c)['is_admin']:
            raise AppError(403,'ADMIN_REQUIRED','此操作需要受控本地执行或维护身份')

    def _read_authorize(self,c,principal,patient):
        if principal is None:
            return
        account=self.auth.account(principal,c)
        if account['is_admin']:
            get(c,'Patient',patient)
        else:
            self.auth.require_patient(principal,patient,'tasks:read',c)

    def _authorize(self,c,action,principal,params,body):
        if action=='delivery_receipt':
            # No production channel identity/signature protocol is configured.
            raise AppError(503,'DELIVERY_ADAPTER_UNAVAILABLE','可信外部渠道认证与签名尚未接入')
        if action=='task_create':
            self._admin(c,principal);get(c,'Patient',body['patient_id'])
            return body['patient_id']
        if action=='reminder_snooze':
            patient=params['p']
            self.auth.require_patient(principal,patient,'reminder:write',c)
            task=self._task(c,body['source_task_id'])
            if task['patient_id']!=patient:
                raise AppError(404,'RESOURCE_NOT_FOUND','提醒任务不可访问')
            self._reminder_eligible(c,task,check_time=False)
            slot,_,_=self._slot_context(c,patient,task['payload']['dose_slot_id'])
            boundary=datetime.fromisoformat(slot['scheduled_at'])+timedelta(hours=4)
            next_at=self._next_slot_at(c,slot)
            if self.clock()>=boundary or (next_at and self.clock()>=next_at):
                raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','原提醒已超过稍后操作时效')
            return patient
        task=None
        if action=='execution':
            execution=self._execution(c,params['id']);task=self._task(c,execution['task_id'])
        elif action!='tasks':
            task=self._task(c,params['id'])
        patient=params.get('p') or task['patient_id']
        if action in ('task_run','task_cancel'):
            self._admin(c,principal)
        else:
            self._read_authorize(c,principal,patient)
        return patient

    def handle(self,action,principal,params,q,body=None,key=None):
        body=body or {}
        with self.db.connection(readonly=True) as c:
            patient=self._authorize(c,action,principal,params,body)
            if action in READS:
                result=self._read(c,action,principal,params,q)
                self._authorize(c,action,principal,params,body)
                return Result(result)
        if action=='task_run':
            return self.run_once(principal,params['id'],body['expected_revision'],key)
        scope=['demo','account',principal.account_id,patient,action,params]
        def operation(c):
            if action=='task_create':
                result=self.create_in_transaction(c,principal,body)
                return Result(result,201,resource_type='Task',resource_id=result['task_id'])
            if action=='task_cancel':
                task=self._task(c,params['id']);expected(task,body['expected_revision'])
                if task['status'] in TERMINAL:
                    raise AppError(409,'TASK_TERMINAL_CONFLICT','任务已终止，不能撤回已经发生的动作')
                new=changed(task,stamp(self.clock()));new['cancellation_requested']=True
                if task['status']!='running':
                    new.update(status='cancelled',next_attempt_at=None)
                new['failure_reason']=body['reason']
                self._save_task(c,new)
                return Result(new,resource_type='Task',resource_id=new['task_id'])
            if action=='reminder_snooze':
                return self._snooze(c,principal,patient,body)
            raise AppError(422,'TASK_TYPE_NOT_REGISTERED','公共任务操作未注册')
        return self.receipts.run(scope,key,{'path':params,'query':q,'body':body},
                                 lambda c:self._authorize(c,action,principal,params,body),operation)

    def _read(self,c,action,principal,params,q):
        if action=='task':
            return self._task(c,params['id'])
        if action=='execution':
            return self._execution(c,params['id'])
        if action=='tasks':
            docs=[json.loads(r[0]) for r in c.execute('SELECT document_json FROM a_tasks WHERE patient_id=?',(params['p'],))]
            if q.get('status'):
                docs=[d for d in docs if d['status']==q['status']]
            order=lambda d:(d['scheduled_at'],d['task_id'])
        else:
            docs=[json.loads(r[0]) for r in c.execute('SELECT document_json FROM a_executions WHERE task_id=?',(params['id'],))]
            order=lambda d:(d['attempt'],d['execution_id'])
        context=[principal.account_id,action,params,{k:v for k,v in q.items() if k not in ('cursor','limit')}]
        docs=sorted(docs,key=order)
        if q.get('cursor'):
            last=self.auth.read_cursor(q['cursor'],context)
            docs=[d for d in docs if list(order(d))>last]
        limit=int(q.get('limit',20));items=docs[:limit]
        cursor=self.auth.cursor(context,list(order(items[-1]))) if len(docs)>limit else None
        return {'items':items,'next_cursor':cursor}

    def create_in_transaction(self,c,principal,body,*,internal=False,snooze=False):
        """A registered owner calls this inside its own business transaction."""
        body=inputs.TaskCreateInput.model_validate(body).model_dump()
        if not internal:
            self._admin(c,principal)
        get(c,'Patient',body['patient_id'])
        b_owned = body['owner_module'] == 'B'
        if body['owner_module'] == 'C' or b_owned and (not internal or self.support_state is None):
            raise AppError(503,'TASK_OWNER_NOT_INTEGRATED','该任务的B或C业务处理器尚未接入')
        if b_owned:
            self.support_state.validate_task(c,body)
        elif body['kind'].startswith('refresh_'):
            if body['payload']['data_environment']!='demo':
                raise AppError(403,'ENVIRONMENT_FORBIDDEN','演示任务不能访问真实数据')
            if self.analytics is None:
                raise AppError(503,'ANALYTICS_UNAVAILABLE','统计与摘要处理器尚未接入')
        else:
            self._reminder_eligible(c,body,check_time=False,snooze=snooze)
        row=c.execute('SELECT document_json FROM a_tasks WHERE data_environment=? AND owner_module=? AND owner_operation_key=?',
                      ('demo',body['owner_module'],body['owner_operation_key'])).fetchone()
        if row:
            old=json.loads(row[0])
            if any(old[field]!=body[field] for field in body):
                raise AppError(409,'TASK_CONTENT_CONFLICT','相同来源业务键对应不同任务内容')
            return old
        task={'task_id':uid(),**body,'status':'pending','cancellation_requested':False,'attempt_count':0,
              'max_attempts':3,'next_attempt_at':None,'failure_reason':None,'meta':meta(stamp(self.clock()),'A-v0.4')}
        if task['kind']=='deliver_reminder' and self._reminder_count(c,task['payload']['dose_slot_id'])>=3:
            raise AppError(409,'REMINDER_LIMIT_REACHED','该时段初次、重复和稍后提醒总数已达上限')
        return self._save_task(c,task,principal.account_id if principal else None,new=True)

    def _scope(self,principal,task_id):
        return ['demo','account',principal.account_id if principal else '__explicit_internal__','task_run',task_id]

    def _receipt(self,c,scope,key,canonical):
        if not isinstance(key,str) or not 16<=len(key)<=128:
            raise AppError(422,'VALIDATION_ERROR','写操作需要有效幂等键')
        scope_hash,key_hash=fingerprint(scope),digest(key);fp=fingerprint(canonical)
        row=c.execute('SELECT * FROM idempotency_receipts WHERE scope_hash=? AND key_hash=?',(scope_hash,key_hash)).fetchone()
        if row:
            if row['request_fingerprint']!=fp:
                raise AppError(409,'IDEMPOTENCY_CONFLICT','同一执行键对应不同内容')
            if row['full_receipt_until']<=stamp(self.clock()) or row['state']=='expired':
                raise AppError(409,'IDEMPOTENCY_EXPIRED','原执行键已过期，请先核查原资源')
            if row['state']=='processing':
                raise AppError(409,'OPERATION_IN_PROGRESS','原执行正在处理或等待安全恢复')
            saved=c.execute('SELECT response_json FROM receipt_responses WHERE response_ref=?',(row['response_ref'],)).fetchone()
            if not saved:
                raise AppError(503,'RECEIPT_UNAVAILABLE','原执行回执暂不可用')
            return row,Result(**json.loads(saved[0]))
        identifier=uid();at=stamp(self.clock())
        c.execute('INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (identifier,scope_hash,key_hash,fp,'processing','Execution',None,None,None,None,None,
                   at,stamp(self.clock()+timedelta(days=7)),None))
        return {'receipt_id':identifier},None

    def _finish_receipt(self,c,identifier,execution):
        result=Result(execution,resource_type='Execution',resource_id=execution['execution_id'])
        response_ref=uid()
        body={name:getattr(result,name) for name in Result.__dataclass_fields__}
        c.execute('INSERT INTO receipt_responses VALUES (?,?)',(response_ref,encode(body)))
        c.execute("UPDATE idempotency_receipts SET state='committed',resource_id=?,http_status=200,response_ref=?,completed_at=? WHERE receipt_id=? AND state='processing'",
                  (execution['execution_id'],response_ref,stamp(self.clock()),identifier))
        return result

    def run_once(self,principal,task_id,expected_revision,key):
        # Expiration/recovery is an explicit write, never a side effect of GET.
        with self.db.connection(readonly=True) as c:
            self._admin(c,principal);task=self._task(c,task_id)
        self.maintain_due(principal,task['patient_id'])
        with self.db.transaction() as c:
            self._admin(c,principal);task=self._task(c,task_id)
            receipt,replayed=self._receipt(c,self._scope(principal,task_id),key,{'expected_revision':expected_revision})
            if replayed:
                return replayed
            expected(task,expected_revision)
            at=stamp(self.clock())
            if task['status'] not in ('pending','retry_wait') or task['scheduled_at']>at or task['valid_until']<=at or task['cancellation_requested']:
                raise AppError(409,'TASK_NOT_RUNNABLE','任务未到时、在途、终止或结果尚未核清')
            if task['attempt_count']>=task['max_attempts'] or (task['next_attempt_at'] and task['next_attempt_at']>at):
                raise AppError(409,'TASK_NOT_RUNNABLE','尚未到安全重试时间或已达到尝试上限')
            if task['kind']=='deliver_reminder':
                self._reminder_eligible(c,task)
            lease=c.execute('SELECT claim_token FROM a_task_leases WHERE task_id=?',(task_id,)).fetchone()
            token=lease[0]+1 if lease else 1
            c.execute("INSERT INTO a_task_leases VALUES (?,?,?,?,?,?) ON CONFLICT(task_id) DO UPDATE SET owner_instance_id=excluded.owner_instance_id,claim_token=excluded.claim_token,claimed_at=excluded.claimed_at,lease_until=excluded.lease_until,phase=excluded.phase",
                      (task_id,self.instance_id,token,at,stamp(self.clock()+timedelta(seconds=90)),'claimed'))
            task=changed(task,at);task.update(status='running',attempt_count=task['attempt_count']+1,next_attempt_at=None)
            self._save_task(c,task)
            execution={'execution_id':uid(),'task_id':task_id,'patient_id':task['patient_id'],'intervention_id':task['intervention_id'],
                       'attempt':task['attempt_count'],'execution_status':'running','delivery_status':'pending' if task['kind']=='deliver_reminder' else 'not_applicable',
                       'channel':'in_app' if task['kind']=='deliver_reminder' else None,'is_simulated':True,'result_ref':None,
                       'error_code':None,'error_message':None,'retryable':False,'started_at':at,'finished_at':None,
                       'submitted_at':None,'delivered_at':None}
            self._save_execution(c,execution,new=True)
            c.execute('INSERT INTO a_task_run_receipt_links VALUES (?,?)',(receipt['receipt_id'],execution['execution_id']))
            c.execute('UPDATE idempotency_receipts SET resource_id=? WHERE receipt_id=?',(execution['execution_id'],receipt['receipt_id']))
        # No database connection or transaction is held across a handler call.
        stop=threading.Event()
        def heartbeat():
            while not stop.wait(15):
                try:
                    if not self.renew_lease(task_id,token):
                        return
                except Exception:
                    return  # Final token check fails closed if renewal was lost.
        worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
        try:
            try:
                outcome=self.delivery_adapter(copy.deepcopy(task),copy.deepcopy(execution)) if task['kind']=='deliver_reminder' else {}
                if not isinstance(outcome,dict):
                    raise ValueError('invalid adapter result')
            except Exception:
                outcome={'error_code':'LOCAL_EXECUTION_FAILED','error_message':'本地注册处理未完成，未提交应用内通知','retryable':True}
            try:
                with self.db.transaction() as c:
                    self._assert_lease(c,task_id,token)
                    current=self._task(c,task_id)
                    try:
                        self._admin(c,principal)
                        if current['kind']=='deliver_reminder':
                            self._reminder_eligible(c,current)
                    except AppError as exc:
                        outcome={'error_code':exc.code,'error_message':exc.message,'retryable':False,'cancelled':True}
                    if current['cancellation_requested']:
                        outcome={'error_code':'CANCELLATION_REQUESTED','error_message':'任务已收到取消请求，未提交新的应用内通知','retryable':False,'cancelled':True}
                    elif current['valid_until']<=stamp(self.clock()):
                        outcome={'error_code':'TASK_EXPIRED','error_message':'执行结果提交前已超过原有效期，未提交新的业务效果','retryable':False,'expired':True}
                    return self._complete(c,current,execution,outcome,receipt['receipt_id'],token)
            except AppError as exc:
                if exc.code=='TASK_LEASE_LOST':
                    raise
                # The preceding transaction has fully rolled back. Settle this
                # known local failure now instead of leaving a false running row.
                with self.db.transaction() as c:
                    self._assert_lease(c,task_id,token)
                    current=self._task(c,task_id)
                    return self._complete(c,current,execution,{'error_code':exc.code,'error_message':exc.message,
                                          'retryable':exc.status==503},receipt['receipt_id'],token)
        finally:
            stop.set();worker.join(1)

    def _assert_lease(self,c,task_id,token):
        lease=c.execute('SELECT * FROM a_task_leases WHERE task_id=?',(task_id,)).fetchone()
        if not lease or lease['owner_instance_id']!=self.instance_id or lease['claim_token']!=token or lease['lease_until']<=stamp(self.clock()):
            raise AppError(409,'TASK_LEASE_LOST','执行领取权已失效，请查询原执行，不能重复提交结果')

    def renew_lease(self,task_id,token):
        with self.db.transaction() as c:
            now=stamp(self.clock())
            result=c.execute("UPDATE a_task_leases SET lease_until=? WHERE task_id=? AND owner_instance_id=? AND claim_token=? AND lease_until>? AND phase!='result_saved'",
                             (stamp(self.clock()+timedelta(seconds=90)),task_id,self.instance_id,token,now))
            return result.rowcount==1

    def _complete(self,c,task,execution,outcome,receipt_id,token):
        at=stamp(self.clock());new=changed(task,at);execution=copy.deepcopy(execution)
        execution['finished_at']=at
        if outcome.get('error_code') or outcome.get('outcome_unknown'):
            unknown=bool(outcome.get('outcome_unknown'));cancelled=bool(outcome.get('cancelled'));expired=bool(outcome.get('expired'))
            retryable=bool(outcome.get('retryable')) and not unknown and not cancelled and not expired
            execution.update(execution_status='outcome_unknown' if unknown else 'expired' if expired else 'cancelled' if cancelled else 'failed',
                             error_code=outcome.get('error_code','OUTCOME_UNKNOWN'),error_message=outcome.get('error_message','执行结果未知，请先核查原结果'),retryable=retryable)
            if execution['channel']:
                execution['delivery_status']='unknown' if unknown else 'expired' if expired else 'cancelled' if cancelled else 'failed'
            next_time=stamp(self.clock()+timedelta(seconds=60))
            retry=retryable and task['attempt_count']<3 and next_time<task['valid_until']
            new.update(status='retry_wait' if retry else 'expired' if expired else 'cancelled' if cancelled else 'failed',
                       next_attempt_at=next_time if retry else None,failure_reason=execution['error_message'])
        else:
            try:
                if task['kind']=='refresh_statistics':
                    result=self.analytics.refresh_statistics_in_transaction(c,None,task['patient_id'],
                               {**task['payload'],'as_of':at})
                    execution['result_ref']=result['statistics_id']
                elif task['kind']=='refresh_summary':
                    result=self.analytics.refresh_in_transaction(c,None,task['patient_id'],{**task['payload'],'as_of':at})
                    execution['result_ref']=result['summary_id']
                elif task['kind']=='expire_b_state' and self.support_state is not None:
                    execution['result_ref']=self.support_state.run_task(c,task)
                elif task['kind']=='deliver_reminder':
                    identifier=uid()
                    c.execute('INSERT INTO a_in_app_notifications VALUES (?,?,?,?,?,?,?)',
                              (identifier,task['task_id'],execution['execution_id'],task['patient_id'],task['payload']['content_ref'],at,1))
                    for account in c.execute('SELECT account_id FROM o_accounts WHERE self_patient_id=?',(task['patient_id'],)).fetchall():
                        c.execute('INSERT INTO a_notification_recipients VALUES (?,?,?,?,?)',(identifier,account[0],None,None,'submitted'))
                    preference=get(c,'ReminderPreferences',task['patient_id'])
                    if preference['notify_family']:
                        active={b['binding_id'] for b in all_docs(c,'FamilyBinding',task['patient_id']) if b['status']=='active'}
                        for grant in all_docs(c,'Grant',task['patient_id']):
                            if grant['binding_id'] in active and grant['status']=='active' and 'notify:receive' in grant['scopes'] and (grant['valid_until'] is None or grant['valid_until']>at):
                                c.execute('INSERT INTO a_notification_recipients VALUES (?,?,?,?,?) ON CONFLICT(notification_id,account_id) DO NOTHING',
                                          (identifier,grant['grantee_account_id'],grant['grant_id'],grant['grant_version'],'submitted'))
                    execution.update(result_ref=identifier,delivery_status='submitted',submitted_at=at)
                else:
                    raise AppError(503,'TASK_OWNER_NOT_INTEGRATED','该业务处理器尚未接入')
                execution['execution_status']='completed';new.update(status='succeeded',failure_reason=None)
            except AppError as exc:
                # No external side effect exists in these local handlers.
                # Let the caller roll back a failed computation in full; the
                # persisted running attempt is recovered by explicit maintenance.
                raise exc
        self._save_task(c,new);self._save_execution(c,execution)
        c.execute("UPDATE a_task_leases SET phase='result_saved' WHERE task_id=? AND claim_token=?",(task['task_id'],token))
        return self._finish_receipt(c,receipt_id,execution)

    def maintain_due(self,principal,patient):
        """Explicit expiry and lease recovery; no dispatch and no GET writes."""
        result={'expired':0,'cancelled':0,'recovered':0}
        with self.db.transaction() as c:
            if principal is not None:
                self._admin(c,principal)
            at=stamp(self.clock())
            tasks=[json.loads(r[0]) for r in c.execute('SELECT document_json FROM a_tasks WHERE patient_id=?',(patient,))]
            for task in tasks:
                if task['status']=='running':
                    lease=c.execute('SELECT * FROM a_task_leases WHERE task_id=?',(task['task_id'],)).fetchone()
                    if lease and lease['lease_until']>at:
                        continue
                    row=c.execute('SELECT document_json FROM a_executions WHERE task_id=? ORDER BY attempt DESC LIMIT 1',(task['task_id'],)).fetchone()
                    if not row:
                        continue
                    execution=json.loads(row[0]);local=task['kind'] in ('refresh_statistics','refresh_summary','deliver_reminder','expire_b_state')
                    outcome={'error_code':'EXECUTION_INTERRUPTED','error_message':'本地事务未提交，原尝试已记录；按安全间隔恢复' if local else '在途副作用结果未知，必须核查',
                             'retryable':local,'outcome_unknown':not local}
                    if local and task['cancellation_requested']:
                        outcome.update(cancelled=True,retryable=False,error_message='在途取消后的本地事务未提交，停止恢复执行')
                    elif local and task['valid_until']<=at:
                        outcome.update(expired=True,retryable=False,error_message='中断的本地事务未提交且任务已过期，不补发')
                    link=c.execute('SELECT receipt_id FROM a_task_run_receipt_links WHERE execution_id=?',(execution['execution_id'],)).fetchone()
                    self._complete(c,task,execution,outcome,link[0],lease['claim_token'] if lease else 0)
                    result['recovered']+=1
                    task=self._task(c,task['task_id'])
                if task['status'] not in ('pending','retry_wait'):
                    continue
                error=None
                if task['valid_until']<=at:
                    error=('expired','提醒或任务已超过原有效期，不补发')
                elif task['kind']=='deliver_reminder':
                    try:
                        self._reminder_eligible(c,task,check_time=False)
                    except AppError:
                        error=('cancelled','当前提醒设置、授权、患者处理或计划已变化，停止待发')
                if error:
                    new=changed(task,at);new.update(status=error[0],failure_reason=error[1],next_attempt_at=None)
                    self._save_task(c,new);result[error[0]]+=1
        return result

    def _slot_context(self,c,patient,slot_id):
        row=c.execute("SELECT * FROM dose_slots WHERE dose_slot_id=? AND patient_id=? AND data_environment='demo'",(slot_id,patient)).fetchone()
        if not row:
            raise AppError(404,'RESOURCE_NOT_FOUND','提醒时段不可访问')
        slot=dict(row);plan=get(c,'PlanVersion',slot['plan_id']+':'+str(slot['plan_version']))
        if plan['patient_id']!=patient:
            raise AppError(404,'RESOURCE_NOT_FOUND','提醒计划不可访问')
        if plan['timezone']!='Asia/Shanghai':
            raise AppError(409,'SLOT_CONTRACT_NOT_READY','本期尚不支持此计划时区的排程')
        entry=next((e for e in plan['entries'] if e['plan_entry_id']==slot['plan_entry_id']),None)
        if slot['status']!='active' or entry is None or slot['scheduled_at']<plan['effective_from'] or (plan['effective_until'] and slot['scheduled_at']>=plan['effective_until']):
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','原计划时段已被替代或失效')
        return slot,plan,entry

    def _next_slot_at(self,c,slot):
        current=datetime.fromisoformat(slot['scheduled_at']);right=current+timedelta(days=8);candidates=[]
        for plan in all_docs(c,'PlanVersion',slot['patient_id']):
            for entry in plan['entries']:
                if entry['medication_id']!=slot['medication_id']:
                    continue
                first=current.astimezone(SHANGHAI).date()
                for delta in range(9):
                    day=first+timedelta(days=delta)
                    if str(day)<entry['start_date'] or (entry['end_date'] and str(day)>entry['end_date']):
                        continue
                    if entry['schedule']['kind']=='weekly' and day.isoweekday() not in entry['schedule']['weekdays']:
                        continue
                    for hour in entry['schedule']['times']:
                        dt=datetime.combine(day,time.fromisoformat(hour),SHANGHAI);s=stamp(dt)
                        if current<dt<=right and s>=plan['effective_from'] and (not plan['effective_until'] or s<plan['effective_until']):
                            candidates.append(dt)
        return min(candidates) if candidates else None

    def _previous_slot_at(self,c,slot):
        current=datetime.fromisoformat(slot['scheduled_at']);candidates=[]
        first=current.astimezone(SHANGHAI).date()-timedelta(days=8)
        for plan in all_docs(c,'PlanVersion',slot['patient_id']):
            for entry in plan['entries']:
                if entry['medication_id']!=slot['medication_id']:
                    continue
                for delta in range(9):
                    day=first+timedelta(days=delta)
                    if str(day)<entry['start_date'] or (entry['end_date'] and str(day)>entry['end_date']):
                        continue
                    if entry['schedule']['kind']=='weekly' and day.isoweekday() not in entry['schedule']['weekdays']:
                        continue
                    for hour in entry['schedule']['times']:
                        dt=datetime.combine(day,time.fromisoformat(hour),SHANGHAI);s=stamp(dt)
                        if dt<current and s>=plan['effective_from'] and (not plan['effective_until'] or s<plan['effective_until']):
                            candidates.append(dt)
        return max(candidates) if candidates else None

    def _validate_shift(self,c,slot,entry,when):
        dose=datetime.fromisoformat(slot['scheduled_at'])
        if when==dose:
            return
        if entry['strict_timing'] is not False:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','严格时间要求未知或不允许偏移，只保留原定时刻')
        if entry['meal_requirement']:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','原资料存在餐时要求，未提供可靠餐时依据，不能偏移通知')
        if entry['min_interval_minutes']:
            before=self._previous_slot_at(c,slot);after=self._next_slot_at(c,slot)
            minimum=entry['min_interval_minutes']*60
            if (before and (when-before).total_seconds()<minimum) or (after and (after-when).total_seconds()<minimum):
                raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','偏移通知与原资料最小间隔边界冲突，请核对原医嘱')

    def _processed(self,c,slot):
        from .s03_records import effective_events, match_view
        at=stamp(self.clock())
        for event in effective_events(c,slot['patient_id'],'demo',at):
            match=match_view(c,event['event_id'],event['meta']['revision'],at)
            if event['evidence_type']=='self_report' and event['quality']['status']=='valid' and match and match['link_status']=='matched' and match['dose_slot_id']==slot['dose_slot_id'] and event['payload'].get('reported_status') in ('taken','not_taken','postponed','unknown'):
                return True
        return False

    def _base_notification_time(self,c,slot,entry,preference):
        dose=datetime.fromisoformat(slot['scheduled_at']);candidates=set()
        for anchor in preference['anchors']:
            for offset in (-1,0,1):
                day=dose.astimezone(SHANGHAI).date()+timedelta(days=offset)
                moment=datetime.combine(day,time.fromisoformat(anchor['local_time']),SHANGHAI)+timedelta(minutes=anchor['offset_minutes'])
                if abs((moment-dose).total_seconds())<=3600:
                    candidates.add(stamp(moment))
        if len(candidates)==1:
            candidate=datetime.fromisoformat(next(iter(candidates)))
            try:
                self._validate_shift(c,slot,entry,candidate)
                return candidate
            except AppError:
                pass
        return dose

    def _reminder_eligible(self,c,task,*,check_time=True,snooze=False):
        slot,plan,entry=self._slot_context(c,task['patient_id'],task['payload']['dose_slot_id'])
        preference=get(c,'ReminderPreferences',task['patient_id'],required=False)
        if not preference or not preference['enabled'] or preference['meta']['revision']!=task['payload']['reminder_revision'] or 'in_app' not in preference['channels']:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','提醒配置已关闭或修订已变化')
        content=c.execute('SELECT * FROM a_reminder_contents WHERE content_ref=?',(task['payload']['content_ref'],)).fetchone()
        if not content or content['patient_id']!=slot['patient_id'] or content['dose_slot_id']!=slot['dose_slot_id'] or content['reminder_revision']!=preference['meta']['revision']:
            raise AppError(404,'RESOURCE_NOT_FOUND','提醒内容引用不可访问')
        if self._processed(c,slot):
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','患者已明确处理此时段，停止待发提醒')
        scheduled=datetime.fromisoformat(task['scheduled_at']);dose=datetime.fromisoformat(slot['scheduled_at'])
        self._validate_shift(c,slot,entry,scheduled)
        next_at=self._next_slot_at(c,slot)
        if task.get('task_id'):
            snooze=bool(c.execute('SELECT 1 FROM a_reminder_snooze_links WHERE child_task_id=?',(task['task_id'],)).fetchone())
        if snooze:
            if scheduled>=dose+timedelta(hours=4):
                raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','稍后通知超过原剂量四小时边界')
        else:
            base=self._base_notification_time(c,slot,entry,preference)
            allowed={stamp(base+timedelta(minutes=(preference['repeat_interval_minutes'] or 0)*n)) for n in range(preference['max_repeats']+1)}
            if task['scheduled_at'] not in allowed:
                raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','通知时刻不符合当前已确认提醒配置')
        if datetime.fromisoformat(task['valid_until'])>scheduled+timedelta(minutes=30):
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','普通通知有效期不得超过计划通知后三十分钟')
        if next_at and scheduled>=next_at:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','通知安排已到下一正式时段')
        if next_at and datetime.fromisoformat(task['valid_until'])>next_at:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','通知有效期不得越过下一正式时段')
        if check_time and (stamp(self.clock())>=task['valid_until'] or (next_at and self.clock()>=next_at)):
            raise AppError(409,'TASK_NOT_RUNNABLE','原通知已过有效期，不补发')
        # The family switch is never permission to bypass a separate Grant.
        if preference['notify_family']:
            bindings={b['binding_id'] for b in all_docs(c,'FamilyBinding',slot['patient_id']) if b['status']=='active'}
            if not any(g['binding_id'] in bindings and g['status']=='active' and 'notify:receive' in g['scopes'] and (g['valid_until'] is None or g['valid_until']>stamp(self.clock())) for g in all_docs(c,'Grant',slot['patient_id'])):
                raise AppError(403,'SCOPE_REQUIRED','通知家人需要当前有效的独立接收授权')
        return slot,preference,entry

    def _reminder_count(self,c,slot_id):
        count=0
        for row in c.execute("SELECT document_json FROM a_tasks WHERE owner_module='O'"):
            task=json.loads(row[0])
            if task['kind']=='deliver_reminder' and task['payload']['dose_slot_id']==slot_id:
                if task['status'] in ('cancelled','expired') and task['attempt_count']==0:
                    continue  # Explicitly proved never submitted; audit is retained.
                count+=1
        return count

    def _snooze(self,c,principal,patient,body):
        source=self._task(c,body['source_task_id']);expected(source,body['expected_task_revision'])
        if source['owner_module']!='O' or source['kind']!='deliver_reminder' or source['status']!='succeeded':
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','稍后提醒需要结果明确的原应用内提醒')
        execution=c.execute('SELECT document_json FROM a_executions WHERE task_id=? ORDER BY attempt DESC LIMIT 1',(source['task_id'],)).fetchone()
        execution=json.loads(execution[0]) if execution else None
        if not execution or execution['channel']!='in_app' or execution['execution_status']!='completed' or execution['delivery_status']!='submitted':
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','原提醒结果不明确，不能重复排队')
        slot,preference,entry=self._reminder_eligible(c,source,check_time=False)
        existing=c.execute('SELECT child_task_id FROM a_reminder_snooze_links WHERE source_task_id=? AND source_task_revision=?',
                           (source['task_id'],body['expected_task_revision'])).fetchone()
        if existing:
            child=self._task(c,existing[0])
            # Different keys cannot request a different delay for one source.
            return Result(child,200,resource_type='Task',resource_id=child['task_id'])
        when=self.clock()+timedelta(minutes=body['snooze_minutes']);dose=datetime.fromisoformat(slot['scheduled_at'])
        next_at=self._next_slot_at(c,slot);boundary=min([dose+timedelta(hours=4)]+([next_at] if next_at else []))
        if entry['strict_timing'] is not False or when>=boundary or self.clock()>=boundary or self._reminder_count(c,slot['dose_slot_id'])>=3:
            raise AppError(409,'REMINDER_SNOOZE_NOT_ALLOWED','当前提醒不满足医嘱、时效或总次数条件')
        task_body={'patient_id':patient,'kind':'deliver_reminder','owner_module':'O',
                   'owner_operation_key':f"snooze:{source['task_id']}:{body['expected_task_revision']}",
                   'scheduled_at':stamp(when),'valid_until':stamp(min(when+timedelta(minutes=30),boundary)),
                   'payload':{**source['payload'],'reminder_revision':preference['meta']['revision']},
                   'intervention_id':None,'rule_version':RULE}
        child=self.create_in_transaction(c,principal,task_body,internal=True,snooze=True)
        c.execute('INSERT INTO a_reminder_snooze_links VALUES (?,?,?,?,?)',
                  (source['task_id'],body['expected_task_revision'],child['task_id'],slot['dose_slot_id'],stamp(self.clock())))
        return Result(child,201,resource_type='Task',resource_id=child['task_id'])

    def _materialize(self,c,patient,start,end):
        count=0
        for plan in all_docs(c,'PlanVersion',patient):
            if plan['timezone']!='Asia/Shanghai':
                raise AppError(409,'SLOT_CONTRACT_NOT_READY','本期尚不支持跨时区或DST排程')
            left=max(start,plan['effective_from']);right=min(end,plan['effective_until'] or end)
            if right<=left:
                continue
            first=datetime.fromisoformat(left).astimezone(SHANGHAI).date()
            last=datetime.fromisoformat(right).astimezone(SHANGHAI).date()
            days=(last-first).days+1
            for entry in plan['entries']:
                for offset in range(days):
                    day=first+timedelta(days=offset)
                    if str(day)<entry['start_date'] or (entry['end_date'] and str(day)>entry['end_date']):
                        continue
                    schedule=entry['schedule']
                    if schedule['kind']=='weekly' and day.isoweekday() not in schedule['weekdays']:
                        continue
                    for local in schedule['times']:
                        at=stamp(datetime.combine(day,time.fromisoformat(local),SHANGHAI))
                        if left<=at<right:
                            inserted=c.execute('INSERT INTO dose_slots VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(patient_id,data_environment,plan_id,plan_version,plan_entry_id,scheduled_at) DO NOTHING',
                               (uid(),patient,'demo',plan['plan_id'],plan['plan_version'],entry['plan_entry_id'],entry['medication_id'],at,'active','flow-v0.1-slot-v1',1))
                            count+=inserted.rowcount
            c.execute('INSERT INTO o_schedule_windows VALUES (?,?,?,?) ON CONFLICT DO NOTHING',(plan['plan_id'],plan['plan_version'],left,right))
        return count

    def maintenance(self,principal,patient,window_start,window_end):
        """Explicit <=31-day slot/notice/reminder maintenance. Never dispatches."""
        window=inputs.WindowTaskPayload.model_validate({'window_start':window_start,'window_end':window_end,'data_environment':'demo'}).model_dump()
        start,end=window['window_start'],window['window_end']
        with self.db.connection(readonly=True) as c:
            if principal is not None:
                if not self.auth.account(principal,c)['is_admin']:
                    self.auth.require_patient(principal,patient,'reminder:write',c)
                    self.auth.require_patient(principal,patient,'plan:read',c)
            get(c,'Patient',patient)
        due=self.maintain_due(None,patient)
        result={'materialized_slots':0,'created_tasks':0,'consumed_notices':0,'issues':[],**due}
        with self.db.transaction() as c:
            if principal is not None:
                if not self.auth.account(principal,c)['is_admin']:
                    self.auth.require_patient(principal,patient,'reminder:write',c)
                    self.auth.require_patient(principal,patient,'plan:read',c)
            result['materialized_slots']=self._materialize(c,patient,start,end)
            if self.support_state is not None:
                self.support_state.maintain_invitations(c,patient)
                self.support_state.consume_notices(c,patient)
            for notice in c.execute("SELECT n.* FROM change_notices n LEFT JOIN a_notice_consumptions x ON n.notice_id=x.notice_id AND x.consumer='A' WHERE n.patient_id=? AND n.data_environment='demo' AND n.kind IN ('plan_published','event_revision_changed') AND x.notice_id IS NULL",(patient,)).fetchall():
                ref=json.loads(notice['source_ref'])
                if notice['kind']=='plan_published':
                    source=get(c,'PlanVersion',ref['resource_id']+':'+str(ref['resource_revision']))
                    if source['patient_id']!=patient:
                        raise AppError(404,'RESOURCE_NOT_FOUND','变更来源患者不一致')
                elif not c.execute("SELECT 1 FROM source_events WHERE event_id=? AND patient_id=? AND data_environment='demo'",(ref['resource_id'],patient)).fetchone():
                    raise AppError(404,'RESOURCE_NOT_FOUND','变更来源事件不可访问')
                if self.analytics is not None and hasattr(self.analytics,'invalidate_in_transaction'):
                    self.analytics.invalidate_in_transaction(c,patient,dict(notice))
                elif notice['kind']=='event_revision_changed':
                    continue
                c.execute('INSERT INTO a_notice_consumptions VALUES (?,?,?,?,?,?)',(notice['notice_id'],'A','applied',ref['resource_id'],None,stamp(self.clock())))
                result['consumed_notices']+=1
            pref=get(c,'ReminderPreferences',patient,required=False)
            if not pref or not pref['enabled']:
                return result
            slots=c.execute("SELECT * FROM dose_slots WHERE patient_id=? AND data_environment='demo' AND status='active' AND scheduled_at>=? AND scheduled_at<? ORDER BY scheduled_at,dose_slot_id",(patient,start,end)).fetchall()
            for raw in slots:
                slot=dict(raw)
                if self._processed(c,slot):
                    continue
                _,plan,entry=self._slot_context(c,patient,slot['dose_slot_id'])
                dose=datetime.fromisoformat(slot['scheduled_at']);when=dose
                candidates=set()
                for anchor in pref['anchors']:
                    for offset in (-1,0,1):
                        day=dose.astimezone(SHANGHAI).date()+timedelta(days=offset)
                        proposed=datetime.combine(day,time.fromisoformat(anchor['local_time']),SHANGHAI)+timedelta(minutes=anchor['offset_minutes'])
                        if abs((proposed-dose).total_seconds())<=3600:
                            candidates.add(stamp(proposed))
                if len(candidates)>1:
                    result['issues'].append({'dose_slot_id':slot['dose_slot_id'],'code':'AMBIGUOUS_ANCHOR','message':'多个锚点对应不同通知时刻，需明确核对；保留原计划时刻'})
                elif candidates:
                    proposed=datetime.fromisoformat(next(iter(candidates)))
                    if entry['strict_timing'] is False:
                        try:
                            self._validate_shift(c,slot,entry,proposed)
                            when=proposed
                        except AppError as exc:
                            result['issues'].append({'dose_slot_id':slot['dose_slot_id'],'code':exc.code,'message':exc.message+'；保留原计划时刻'})
                    elif proposed!=dose:
                        result['issues'].append({'dose_slot_id':slot['dose_slot_id'],'code':'STRICT_TIMING','message':'严格时间未知或不允许偏移，保留原定通知时刻'})
                next_at=self._next_slot_at(c,slot)
                for repeat in range(pref['max_repeats']+1):
                    scheduled=when+timedelta(minutes=(pref['repeat_interval_minutes'] or 0)*repeat)
                    if repeat and entry['strict_timing'] is not False:
                        result['issues'].append({'dose_slot_id':slot['dose_slot_id'],'code':'STRICT_TIMING','message':'原医嘱时间要求不允许额外偏移通知'})
                        continue
                    valid=min([scheduled+timedelta(minutes=30)]+([next_at] if next_at else []))
                    if valid<=scheduled or stamp(valid)<=stamp(self.clock()):
                        continue  # Offline expired notifications are never queued.
                    operation=f"reminder:{slot['dose_slot_id']}:{pref['meta']['revision']}:{repeat}"
                    existing=c.execute("SELECT 1 FROM a_tasks WHERE owner_module='O' AND data_environment='demo' AND owner_operation_key=?",(operation,)).fetchone()
                    if existing:
                        continue
                    if self._reminder_count(c,slot['dose_slot_id'])>=3:
                        break
                    content_ref=uid();local=scheduled.astimezone(SHANGHAI).strftime('%H:%M')
                    privacy=pref['privacy_enabled'] or any(w['start']<=local<w['end'] for w in pref['privacy_windows'])
                    text=pref['custom_text'] or '今日事项待确认。'
                    if privacy:
                        text=pref['custom_text'] if pref['custom_text'] in ('今日事项待确认。','有一项日程需要处理。') else '今日事项待确认。'
                    c.execute('INSERT INTO a_reminder_contents VALUES (?,?,?,?,?,?,?)',(content_ref,patient,slot['dose_slot_id'],pref['meta']['revision'],text,int(privacy),stamp(self.clock())))
                    body={'patient_id':patient,'kind':'deliver_reminder','owner_module':'O','owner_operation_key':operation,
                          'scheduled_at':stamp(scheduled),'valid_until':stamp(valid),
                          'payload':{'dose_slot_id':slot['dose_slot_id'],'reminder_revision':pref['meta']['revision'],'content_ref':content_ref},
                          'intervention_id':None,'rule_version':RULE}
                    try:
                        self.create_in_transaction(c,principal,body,internal=True)
                        result['created_tasks']+=1
                    except AppError as exc:
                        c.execute('DELETE FROM a_reminder_contents WHERE content_ref=?',(content_ref,))
                        result['issues'].append({'dose_slot_id':slot['dose_slot_id'],'code':exc.code,'message':exc.message})
        return result

    def receive_delivery_receipt(self,provider_subject,body):
        """Only a registered internal mock channel calls this; HTTP A40 is closed."""
        if provider_subject!='demo-mock-channel':
            raise AppError(503,'DELIVERY_ADAPTER_UNAVAILABLE','渠道身份适配尚未接入')
        body=inputs.DeliveryReceiptInput.model_validate(body).model_dump()
        if body['occurred_at']>stamp(self.clock()):
            raise AppError(422,'VALIDATION_ERROR','渠道发生时间不能晚于当前服务器时钟')
        with self.db.transaction() as c:
            fp=fingerprint(body)
            row=c.execute('SELECT * FROM a_delivery_receipts WHERE provider_subject=? AND provider_event_id=?',(provider_subject,body['provider_event_id'])).fetchone()
            if row:
                if row['request_fingerprint']!=fp:
                    raise AppError(409,'RECEIPT_CONTENT_CONFLICT','同一渠道事件编号内容冲突')
                return json.loads(row['document_json'])
            execution=self._execution(c,body['execution_id']);task=self._task(c,execution['task_id'])
            if execution['channel'] not in ('mock','in_app'):
                raise AppError(409,'RECEIPT_CONTENT_CONFLICT','计算执行没有渠道投递回执')
            reason=None
            if body['status']=='delivered':
                reason='本地模拟渠道不证明真实送达，保留未确认'
            elif task['status'] in ('cancelled','expired','failed') or execution['delivery_status'] in ('delivered','failed','cancelled','expired'):
                reason='任务或投递已终止，晚到回执仅保留审计'
            else:
                try:
                    if task['kind']=='deliver_reminder':
                        self._reminder_eligible(c,task,check_time=True)
                except AppError:
                    reason='当前授权、配置或计划已变化，晚回执不恢复共享'
            if not reason:
                execution['delivery_status']=body['status']
                if body['status']=='submitted':
                    execution['submitted_at']=execution['submitted_at'] or body['occurred_at']
                else:
                    execution.update(error_code=body['failure_code'],error_message=body['failure_message'],retryable=False)
                self._save_execution(c,execution)
            receipt={'receipt_id':uid(),'provider_event_id':body['provider_event_id'],'execution_id':body['execution_id'],
                     'occurred_at':body['occurred_at'],'received_at':stamp(self.clock()),'status':body['status'],
                     'applied':reason is None,'ignore_reason':reason,'is_simulated':True,'execution':execution}
            c.execute('INSERT INTO a_delivery_receipts VALUES (?,?,?,?,?)',(receipt['receipt_id'],provider_subject,body['provider_event_id'],fp,encode(receipt)))
            return receipt
