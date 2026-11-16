"""A2/A3/A4/A6 evidence ingestion, immutable revisions and explicit links.

Only registered local demo inputs are enabled. Derived quality and links have
their own timestamped histories; the A1 source tables remain the only facts.
"""
import copy
import json
import sqlite3
from datetime import datetime

from . import s03_record_inputs as inputs
from .documents import encode, fingerprint, get, meta, stamp, uid
from .errors import AppError
from .idempotency import Result
from .s02_inputs import utc

RULE = 'flow-v0.1-explicit-slot-v1'
QUALITY_RULE = 'A-v0.4-quality-v1'
METRICS = {'sleep_duration':'h','step_count':'count','heart_rate':'beats/min'}

ROUTES = [
 ('A10','POST','/patients/{p}/medication-events','records_medication_create',inputs.MedicationEventInput),
 ('A11','GET','/patients/{p}/medication-events','records_medications',None),
 ('A12','GET','/medication-events/{id}','records_medication',None),
 ('A13','POST','/patients/{p}/measurements','records_measurement_create',inputs.MeasurementInput),
 ('A14','GET','/patients/{p}/measurements','records_measurements',None),
 ('A15','GET','/measurements/{id}','records_measurement',None),
 ('A16','POST','/events/{id}/corrections','records_correction',inputs.CorrectionInput),
 ('A17','POST','/events/{id}/withdrawals','records_withdrawal',inputs.WithdrawalInput),
 ('A18','GET','/events/{id}/revisions','records_revisions',None),
 ('A19','GET','/events/{id}/quality','records_quality',None),
 ('A20','POST','/events/{id}/reprocess','records_reprocess',inputs.ReprocessInput),
 ('A21','GET','/patients/{p}/device-bindings','records_device_bindings',None),
 ('A22','POST','/patients/{p}/device-bindings','records_device_bind',inputs.DeviceBindingInput),
 ('A23','POST','/device-bindings/{id}/revoke','records_device_revoke',inputs.DeviceRevokeInput),
 ('A24','POST','/integrations/device-events','records_device_event',inputs.DeviceEventInput),
 ('A25','POST','/demo/device-events','records_demo_device',inputs.DemoDeviceInput),
 ('A26','GET','/patients/{p}/dose-matches','records_matches',None),
 ('A27','POST','/dose-matches/review','records_match_review',inputs.MatchReviewInput),
]
READS = {action for _,method,_,action,_ in ROUTES if method=='GET'}
WINDOWS = {'records_medications','records_measurements','records_matches'}
LISTS = WINDOWS | {'records_revisions','records_device_bindings'}


def query_input(action, raw_query):
    pairs = list(raw_query.multi_items()) if hasattr(raw_query,'multi_items') else list(raw_query.items()) if hasattr(raw_query,'items') else list(raw_query)
    q = dict(pairs)
    allowed = {'cursor','limit'} if action in LISTS else set()
    if action in WINDOWS:
        allowed |= {'window_start','window_end','as_of','data_environment'}
    if action in {'records_medications','records_measurements'}:
        allowed.add('state')
    if action=='records_measurements':
        allowed.add('metric_code')
    if action=='records_matches':
        allowed.add('plan_id')
    try:
        if len(q)!=len(pairs) or set(q)-allowed:
            raise ValueError()
        if action in WINDOWS:
            q['window_start']=utc(q['window_start']);q['window_end']=utc(q['window_end'])
            seconds=(datetime.fromisoformat(q['window_end'])-datetime.fromisoformat(q['window_start'])).total_seconds()
            if not 0<seconds<=31*86400 or q['data_environment'] not in {'demo','real'}:
                raise ValueError()
            if 'as_of' in q:
                q['as_of']=utc(q['as_of'])
        if 'limit' in q and (not str(q['limit']).isascii() or not str(q['limit']).isdigit() or not 1<=int(q['limit'])<=100):
            raise ValueError()
        if 'cursor' in q and not q['cursor']:
            raise ValueError()
        if q.get('state','effective') not in {'effective','withdrawn','all'}:
            raise ValueError()
        for field in ('metric_code','plan_id'):
            if field in q and not 1<=len(q[field])<=(200 if field=='metric_code' else 128):
                raise ValueError()
    except (KeyError,ValueError,TypeError):
        raise AppError(422,'VALIDATION_ERROR','查询字段、重复参数、时间或范围不合法') from None
    return q


def source_row(conn,event_id):
    row=conn.execute('SELECT * FROM source_events WHERE event_id=?',(event_id,)).fetchone()
    if not row:
        raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
    return row


def revision_row(conn,event_id,as_of=None):
    sql='SELECT * FROM event_revisions WHERE event_id=?'
    args=[event_id]
    if as_of is not None:
        sql+=' AND created_at<=?';args.append(as_of)
    row=conn.execute(sql+' ORDER BY revision DESC LIMIT 1',args).fetchone()
    if not row:
        raise AppError(404,'RESOURCE_NOT_FOUND','该时点尚无可访问记录')
    return row


def quality_view(conn,event_id,event_revision,as_of=None):
    sql='SELECT quality_json FROM s03_quality_history WHERE event_id=? AND event_revision=?'
    args=[event_id,event_revision]
    if as_of is not None:
        sql+=' AND processed_at<=?';args.append(as_of)
    row=conn.execute(sql+' ORDER BY processed_at DESC,rowid DESC LIMIT 1',args).fetchone()
    return json.loads(row[0]) if row else {'event_id':event_id,'event_revision':event_revision,'status':'pending_validation',
                'issues':[],'normalized_measurement':None,'processing_version':None,'processed_at':None}


def match_view(conn,event_id,event_revision,as_of=None):
    sql='SELECT match_json FROM s03_match_history WHERE event_id=? AND event_revision=?'
    args=[event_id,event_revision]
    if as_of is not None:
        sql+=' AND generated_at<=?';args.append(as_of)
    row=conn.execute(sql+' ORDER BY generated_at DESC,rowid DESC LIMIT 1',args).fetchone()
    return json.loads(row[0]) if row else None


def event_view(conn,event_id,as_of=None):
    row=source_row(conn,event_id)
    if as_of is not None and row['received_at']>as_of:
        raise AppError(404,'RESOURCE_NOT_FOUND','该时点尚未接收此记录')
    revision=revision_row(conn,event_id,as_of)
    match=match_view(conn,event_id,revision['revision'],as_of)
    return {'event_id':event_id,'patient_id':row['patient_id'],'event_kind':row['event_kind'],'source':row['source'],
        'source_event_id':row['source_event_id'],'evidence_type':row['evidence_type'],'occurred_at':revision['occurred_at'],
        'received_at':row['received_at'],'reporter_account_id':row['reporter_account_id'],'device_id':row['device_id'],
        'state':'withdrawn' if revision['change_kind']=='withdrawal' else 'effective','payload':json.loads(revision['payload_json']),
        'quality':quality_view(conn,event_id,revision['revision'],as_of),
        'link_status':match['link_status'] if match else 'not_applicable' if row['event_kind']=='measurement' else 'unmatched',
        'meta':{'created_at':row['received_at'],'updated_at':revision['created_at'],'revision':revision['revision'],
                'contract_version':'A-v0.4','is_simulated':bool(row['is_simulated'])}}


def effective_events(conn,patient,environment,as_of):
    rows=conn.execute('SELECT event_id FROM source_events WHERE patient_id=? AND data_environment=? AND received_at<=? ORDER BY received_at,event_id',
                     (patient,environment,as_of)).fetchall()
    return [event for row in rows if (event:=event_view(conn,row['event_id'],as_of))['state']=='effective']


class S03Records:
    event_view=staticmethod(event_view)
    effective_events=staticmethod(effective_events)
    match_view=staticmethod(match_view)
    quality_view=staticmethod(quality_view)

    def __init__(self,db,auth,receipts,clock):
        self.db,self.auth,self.receipts,self.clock=db,auth,receipts,clock

    def _demo(self,c,patient):
        doc=get(c,'Patient',patient)
        if not doc['meta']['is_simulated']:
            raise AppError(403,'ENVIRONMENT_FORBIDDEN','仅允许明确虚构的演示数据')

    def _admin(self,c,principal,patient=None):
        if not self.auth.account(principal,c)['is_admin']:
            raise AppError(403,'ADMIN_REQUIRED','此入口仅允许受控演示维护身份')
        if patient:
            self._demo(c,patient)

    def _binding(self,c,identifier):
        row=c.execute('SELECT * FROM s03_device_bindings WHERE binding_id=?',(identifier,)).fetchone()
        if not row:
            raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
        return row

    def authorize(self,c,action,principal,params,b):
        if action=='records_device_event':
            raise AppError(503,'DEVICE_ADAPTER_UNAVAILABLE','真实设备认证及签名适配未接入，不接受Cookie自报设备身份')
        self.auth.session(principal,c)
        patient=params.get('p')
        event=None
        if action in {'records_medication','records_measurement','records_correction','records_withdrawal','records_revisions','records_quality','records_reprocess'}:
            event=event_view(c,params['id']);patient=event['patient_id']
            if action=='records_medication' and event['event_kind']!='medication' or action=='records_measurement' and event['event_kind']!='measurement':
                raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
        elif action=='records_device_revoke':
            patient=self._binding(c,params['id'])['patient_id']
        elif action=='records_match_review':
            event=event_view(c,b['event_id']);patient=event['patient_id']
        elif action=='records_demo_device':
            patient=b['patient_id']
        if event and source_row(c,event['event_id'])['data_environment']!='demo':
            raise AppError(403,'ENVIRONMENT_FORBIDDEN','演示身份不能访问真实数据')
        if action in {'records_reprocess','records_match_review','records_demo_device'}:
            self._admin(c,principal,patient)
            if action=='records_match_review' and event['event_kind']!='medication':
                raise AppError(422,'INVALID_EVENT_KIND','只能复核服药证据的关联')
            if action=='records_demo_device':
                device=c.execute('SELECT * FROM s03_devices WHERE device_id=?',(b['device_id'],)).fetchone()
                binding=c.execute("SELECT * FROM s03_device_bindings WHERE device_id=? AND status='active'",(b['device_id'],)).fetchone()
                if b['scenario']=='unbound' or not device or not binding or binding['patient_id']!=patient:
                    raise AppError(403,'DEVICE_NOT_AUTHORIZED','模拟设备尚未有效关联至此患者')
            return patient
        if event and action in {'records_correction','records_withdrawal'} and event['source']!='manual':
            self._admin(c,principal,patient)
            return patient
        guards={'records_medication_create':'records:report','records_medications':'records:read','records_medication':'records:read',
                'records_measurement_create':'measurements:write','records_measurements':'measurements:read','records_measurement':'measurements:read',
                'records_device_bindings':'devices:manage','records_device_revoke':'devices:manage','records_matches':'statistics:read'}
        if action in guards:
            self.auth.require_patient(principal,patient,guards[action],c)
            if action=='records_matches':
                self.auth.require_patient(principal,patient,'records:read',c)
        elif action=='records_device_bind':
            self.auth.require_patient(principal,patient,'',c,self_only=True)
        elif event:
            read='records:read' if event['event_kind']=='medication' else 'measurements:read'
            self.auth.require_patient(principal,patient,read,c)
            if action in {'records_correction','records_withdrawal'}:
                self.auth.require_patient(principal,patient,'records:report' if event['event_kind']=='medication' else 'measurements:write',c)
                if event['source']!='manual':
                    self._admin(c,principal,patient)
                else:
                    if event['reporter_account_id']!=principal.account_id:
                        raise AppError(403,'EVENT_AUTHOR_REQUIRED','只能更正或撤销自己提交的报告')
                    if not self.auth.is_self(principal,patient,c):
                        self.auth.require_patient(principal,patient,'records:correct',c)
        self._demo(c,patient)
        return patient

    def handle(self,action,principal,params,q,body=None,key=None):
        body=body or {};q=dict(q)
        if action in WINDOWS:
            if q['data_environment']!='demo':
                raise AppError(403,'ENVIRONMENT_FORBIDDEN','演示身份不能访问真实数据')
            if 'as_of' not in q:
                q['_implicit_as_of']=True
                if q.get('cursor'):
                    last=self.auth.read_cursor(q['cursor'],self._cursor_context(principal,params['p'],action,q))
                    try:
                        q['as_of']=utc(last[0]);q['_cursor_last']=last[1:]
                    except (ValueError,TypeError,IndexError):
                        raise AppError(422,'INVALID_CURSOR','分页截止时刻无效，请重新读取列表') from None
                else:
                    q['as_of']=stamp(self.clock())
            if q['as_of']>stamp(self.clock()):
                raise AppError(422,'INVALID_AS_OF','统计截止时刻不能晚于服务器当前时间')
        with self.db.connection(readonly=True) as c:
            patient=self.authorize(c,action,principal,params,body)
            if action in READS:
                result=self.read(c,action,principal,params,q)
                self.authorize(c,action,principal,params,body)
                return Result(result)
        scope=['demo','account',principal.account_id,patient or '__none__',action,params]
        return self.receipts.run(scope,key,{'path':params,'query':q,'body':body},
            lambda c:self.authorize(c,action,principal,params,body),
            lambda c:self.write(c,action,principal,params,q,body))

    def _cursor_context(self,principal,patient,action,q):
        return fingerprint({'subject':principal.account_id,'patient':patient,'action':action,
                            'query':{k:v for k,v in q.items() if k not in {'cursor','limit'} and not k.startswith('_')
                                     and not (k=='as_of' and q.get('_implicit_as_of'))}})

    def _paginate(self,principal,patient,action,q,items,order):
        context=self._cursor_context(principal,patient,action,q)
        items=sorted(items,key=order)
        if q.get('cursor'):
            last=q['_cursor_last'] if q.get('_implicit_as_of') else self.auth.read_cursor(q['cursor'],context)
            items=[item for item in items if list(order(item))>last]
        limit=int(q.get('limit',20));page=items[:limit]
        last=([q['as_of']] if q.get('_implicit_as_of') else [])+list(order(page[-1])) if page else []
        cursor=self.auth.cursor(context,last) if len(items)>limit else None
        return {'items':page,'next_cursor':cursor}

    def read(self,c,action,principal,params,q):
        p=params.get('p')
        if action in {'records_medication','records_measurement'}:
            return event_view(c,params['id'])
        if action=='records_quality':
            return event_view(c,params['id'])['quality']
        if action=='records_revisions':
            event=event_view(c,params['id'])
            items=[{'event_id':r['event_id'],'revision':r['revision'],'change_kind':r['change_kind'],'occurred_at':r['occurred_at'],
                    'payload':json.loads(r['payload_json']),'reason':r['reason'],'replaces_revision':r['replaces_revision'],
                    'actor_account_id':r['actor_account_id'],'created_at':r['created_at'],'is_simulated':bool(r['is_simulated'])}
                   for r in c.execute('SELECT * FROM event_revisions WHERE event_id=? ORDER BY revision',(params['id'],))]
            return self._paginate(principal,event['patient_id'],action,q,items,lambda d:(d['revision'],))
        if action=='records_device_bindings':
            items=[self.binding_view(r) for r in c.execute('SELECT * FROM s03_device_bindings WHERE patient_id=?',(p,))]
            return self._paginate(principal,p,action,q,items,lambda d:(d['bound_at'],d['binding_id']))
        if action in WINDOWS:
            items=[]
            for row in c.execute('SELECT event_id FROM source_events WHERE patient_id=? AND data_environment=? AND received_at<=?',(p,q['data_environment'],q['as_of'])):
                event=event_view(c,row['event_id'],q['as_of'])
                if not q['window_start']<=event['occurred_at']<q['window_end']:
                    continue
                kind='measurement' if action=='records_measurements' else 'medication'
                if event['event_kind']!=kind:
                    continue
                if action=='records_matches':
                    match=match_view(c,event['event_id'],event['meta']['revision'],q['as_of'])
                    if not match:
                        match=self._make_match(c,event,event['meta']['updated_at'],'尚未处理明确时段关联')
                        match.update(match_id='pending:'+fingerprint([event['event_id'],event['meta']['revision']]),
                                     dose_slot_id=None,candidate_slot_ids=[],link_status='review_required')
                    if q.get('plan_id') and not self._match_plan(c,match,q['plan_id']):
                        continue
                    items.append(match)
                elif (q.get('state','effective')=='all' or event['state']==q.get('state','effective')) and (not q.get('metric_code') or event['payload']['metric_code']==q['metric_code']):
                    items.append(event)
            order=(lambda d:(d['generated_at'],d['match_id'])) if action=='records_matches' else (lambda d:(d['occurred_at'],d['event_id']))
            return self._paginate(principal,p,action,q,items,order)
        raise RuntimeError('unregistered records read')

    def _match_plan(self,c,match,plan_id):
        if not match['dose_slot_id']:
            return False
        slot=c.execute('SELECT plan_id FROM dose_slots WHERE dose_slot_id=?',(match['dose_slot_id'],)).fetchone()
        return bool(slot and slot[0]==plan_id)

    def binding_view(self,row):
        return {'binding_id':row['binding_id'],'device_id':row['device_id'],'patient_id':row['patient_id'],
                'source':'mock_adapter','status':row['status'],'bound_at':row['bound_at'],'revoked_at':row['revoked_at'],
                'meta':{'created_at':row['bound_at'],'updated_at':row['updated_at'],'revision':row['revision'],
                        'contract_version':'A-v0.4','is_simulated':True}}

    def _binding_audit(self,c,principal,view,at,reason=None):
        operation=uid()
        c.execute('INSERT INTO operation_audit VALUES (?,?,?,?,?,?,?)',
                  (operation,principal.account_id,view['patient_id'],'device_binding',view['status'],at,'demo'))
        c.execute('INSERT INTO s03_device_binding_audit VALUES (?,?,?)',(operation,view['binding_id'],reason))

    def _references(self,c,patient,payload):
        if payload.get('medication_id'):
            medication=get(c,'Medication',payload['medication_id'])
            if medication['patient_id']!=patient:
                raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
        ref=payload.get('plan_ref')
        if ref and get(c,'PlanVersion',ref['plan_id']+':'+str(ref['plan_version']))['patient_id']!=patient:
            raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
        if payload.get('dose_slot_id'):
            slot=c.execute('SELECT * FROM dose_slots WHERE dose_slot_id=?',(payload['dose_slot_id'],)).fetchone()
            if not slot or slot['patient_id']!=patient or slot['data_environment']!='demo':
                raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
            if payload.get('medication_id') and payload['medication_id']!=slot['medication_id'] or ref and (ref['plan_id']!=slot['plan_id'] or ref['plan_version']!=slot['plan_version']):
                raise AppError(422,'INVALID_SLOT_REFERENCE','药品、时段和计划版本引用不一致')

    def _notice(self,c,event,at,tag):
        for kind in ('event_revision_changed','points_source_changed'):
            if kind=='points_source_changed' and event['source']!='manual':
                continue
            key=f'{kind}:{event["event_id"]}:{event["meta"]["revision"]}:{tag}'
            ref={'resource_type':'SourceEvent','resource_id':event['event_id'],'resource_revision':event['meta']['revision']}
            c.execute('INSERT INTO change_notices VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_module,data_environment,business_key) DO NOTHING',
                (uid(),'A',event['patient_id'],'demo',kind,encode(ref),key,event['meta']['updated_at'],at,1))

    def _make_match(self,c,event,at,reason=None):
        payload=event['payload'];slot_id=payload.get('dose_slot_id')
        status='not_applicable' if event['event_kind']=='measurement' or event['state']=='withdrawn' else 'matched' if slot_id else 'unmatched'
        return {'match_id':uid(),'patient_id':event['patient_id'],'event_id':event['event_id'],'event_revision':event['meta']['revision'],
                'dose_slot_id':slot_id if status=='matched' else None,'candidate_slot_ids':[slot_id] if status=='matched' else [],
                'link_status':status,'reason':reason or ('未提供明确合法时段引用；自动时间匹配未启用' if status=='unmatched' else None),
                'rule_version':RULE,'generated_at':at,'is_simulated':True}

    def _save_match(self,c,event,match,actor=None,review=False):
        c.execute('INSERT INTO s03_match_history VALUES (?,?,?,?,?,?,?)',(match['match_id'],event['event_id'],event['meta']['revision'],match['generated_at'],actor,int(review),encode(match)))
        c.execute('DELETE FROM evidence_slot_links WHERE event_id=? AND event_revision=?',(event['event_id'],event['meta']['revision']))
        if match['dose_slot_id']:
            c.execute('INSERT INTO evidence_slot_links VALUES (?,?,?,?,?)',(event['event_id'],event['meta']['revision'],event['patient_id'],'demo',match['dose_slot_id']))

    def _assess_quality(self,event,at):
        """Pure registered rules: no IO, authorization, or mutable source facts."""
        issues=[];normalized=None
        if event['event_kind']=='measurement':
            payload=event['payload'];unit=METRICS.get(payload['metric_code'])
            if unit is None:
                issues.append({'code':'unknown_metric','message':'指标代码尚无已登记的标准单位','field':'metric_code'})
            elif payload['unit'] not in (unit,None) or payload['value'] is not None and payload['unit'] is None:
                issues.append({'code':'unknown_unit','message':'原单位未确认，不猜测或换算数值','field':'unit'})
            normalized=copy.deepcopy(payload)
            if issues:
                normalized.update(value=None,unit=None,missing_reason='指标或原单位尚未确认，原值保留待复核')
        return {'event_id':event['event_id'],'event_revision':event['meta']['revision'],'status':'needs_review' if issues else 'valid',
                'issues':issues,'normalized_measurement':normalized,'processing_version':QUALITY_RULE,'processed_at':at}

    def _process(self,c,event,at):
        # Storage reads stay outside the pure-computation catch. A storage
        # failure rolls back the complete operation and never becomes a saved
        # successful processing result.
        existing=quality_view(c,event['event_id'],event['meta']['revision'])
        match=match_view(c,event['event_id'],event['meta']['revision'])
        review=c.execute('SELECT is_review FROM s03_match_history WHERE event_id=? AND event_revision=? ORDER BY generated_at DESC,rowid DESC LIMIT 1',
                         (event['event_id'],event['meta']['revision'])).fetchone()
        proposed=None
        try:
            quality=self._assess_quality(event,at)
            if match is None or match['link_status']=='review_required' and not (review and review[0]):
                proposed=self._make_match(None,event,at)
        except (sqlite3.Error,AppError):
            raise
        except OSError:
            raise AppError(503,'QUALITY_STORE_UNAVAILABLE','处理所需存储暂不可用，操作已回滚，请核查后用原键重试') from None
        except Exception:
            quality={'event_id':event['event_id'],'event_revision':event['meta']['revision'],'status':'processing_failed',
                     'issues':[{'code':'processing_error','message':'处理程序未完成，原始资料保留；此状态不表示患者数据无效或临床异常','field':None}],
                     'normalized_measurement':None,'processing_version':QUALITY_RULE,'processed_at':at}
            if match is None:
                proposed={'match_id':uid(),'patient_id':event['patient_id'],'event_id':event['event_id'],
                          'event_revision':event['meta']['revision'],'dose_slot_id':None,'candidate_slot_ids':[],
                          'link_status':'review_required' if event['event_kind']=='medication' else 'not_applicable',
                          'reason':'处理未完成，明确关联仍待核查','rule_version':RULE,'generated_at':at,'is_simulated':True}
        signature=lambda q:{k:v for k,v in q.items() if k!='processed_at'}
        changed=signature(existing)!=signature(quality)
        if changed:
            c.execute('INSERT INTO s03_quality_history VALUES (?,?,?,?,?,?)',(uid(),event['event_id'],event['meta']['revision'],at,QUALITY_RULE,encode(quality)))
        if proposed is not None:
            self._save_match(c,event,proposed)
            changed=True
        if changed:
            self._notice(c,event,at,'process:'+fingerprint(signature(quality))[:20])
        return quality_view(c,event['event_id'],event['meta']['revision'])

    def _ingest(self,c,patient,source,subject,source_id,kind,evidence,occurred,payload,at,reporter=None,device=None):
        if kind=='medication':
            self._references(c,patient,payload)
        old=c.execute('SELECT * FROM source_events WHERE patient_id=? AND data_environment=? AND source=? AND source_subject_id=? AND source_event_id=?',
                      (patient,'demo',source,subject,source_id)).fetchone()
        if old:
            if old['event_kind']!=kind or old['occurred_at']!=occurred or old['original_payload_json']!=encode(payload) or old['evidence_type']!=evidence:
                raise AppError(409,'SOURCE_EVENT_CONFLICT','同一来源编号对应不同内容')
            return event_view(c,old['event_id'])
        identifier=uid()
        c.execute('INSERT INTO source_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                  (identifier,patient,'demo',kind,source,subject,source_id,evidence,occurred,at,reporter,device,encode(payload),1))
        c.execute('INSERT INTO event_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                  (identifier,1,'original',occurred,encode(payload),None,None,reporter,at,1))
        event=event_view(c,identifier)
        self._notice(c,event,at,'revision')
        self._process(c,event,at)
        return event_view(c,identifier)

    def write(self,c,action,principal,params,q,b):
        at=stamp(self.clock());patient=params.get('p')
        if action in {'records_medication_create','records_measurement_create'}:
            medication=action=='records_medication_create'
            if medication:
                payload={k:b.get(k) for k in ('reported_status','medication_id','dose_slot_id','plan_ref','raw_text')};payload['observation']=None
            else:
                payload=b['payload']
            event=self._ingest(c,patient,'manual',principal.account_id,b['source_event_id'],'medication' if medication else 'measurement',
                ('self_report' if self.auth.is_self(principal,patient,c) else 'family_report') if medication else None,
                b['occurred_at'],payload,at,reporter=principal.account_id)
            return Result(event,201,resource_type='SourceEvent',resource_id=event['event_id'])
        if action in {'records_correction','records_withdrawal','records_reprocess','records_match_review'}:
            identifier=b['event_id'] if action=='records_match_review' else params['id']
            event=event_view(c,identifier);patient=event['patient_id'];revision=event['meta']['revision']
            if revision!=b['expected_revision']:
                code={'records_reprocess':'PROCESSING_VERSION_CONFLICT','records_match_review':'MATCH_REVIEW_CONFLICT'}.get(action,'REVISION_CONFLICT')
                raise AppError(409,code,'记录已有新修订，请重新核对')
            if action=='records_reprocess':
                quality=self._process(c,event,at)
                if quality['status']=='processing_failed':
                    return Result(None,503,resource_type='SourceEvent',resource_id=identifier,
                                  error={'code':'QUALITY_PROCESSING_FAILED','message':'清洗或关联处理未完成；质量状态已保存，可查询原记录，核查程序后显式重新处理'})
                return Result(quality,resource_type='SourceEvent',resource_id=identifier)
            if event['state']=='withdrawn':
                raise AppError(409,'EVENT_ALREADY_WITHDRAWN','记录已撤销，不能隐式恢复或继续更正')
            if action=='records_match_review':
                payload=copy.deepcopy(event['payload']);payload['dose_slot_id']=b['dose_slot_id']
                self._references(c,patient,payload)
                match=self._make_match(c,event,at)
                match.update(dose_slot_id=b['dose_slot_id'],candidate_slot_ids=[b['dose_slot_id']] if b['dose_slot_id'] else [],
                             link_status='matched' if b['dose_slot_id'] else 'unmatched',reason=b['reason'])
                self._save_match(c,event,match,principal.account_id,True)
                self._notice(c,event,at,'review:'+match['match_id'])
                return Result(match,resource_type='SourceEvent',resource_id=identifier)
            correction=action=='records_correction'
            payload=b['payload'] if correction else event['payload']
            if correction:
                is_medication='reported_status' in payload
                if is_medication!=(event['event_kind']=='medication'):
                    raise AppError(422,'INVALID_EVENT_KIND','更正不能改变原始事件种类')
                if is_medication:
                    if event['source']=='manual' and (payload['reported_status'] is None or payload['observation'] is not None) or event['source']!='manual' and (payload['reported_status'] is not None or payload['observation'] is None):
                        raise AppError(422,'INVALID_EVIDENCE_SOURCE','更正不能改变本人、家人或设备报告来源')
                    if event['evidence_type']=='box_opening' and payload['observation']!='box_opened' or event['evidence_type']=='device_inference' and payload['observation']!='inferred_intake':
                        raise AppError(422,'INVALID_EVIDENCE_SOURCE','开盒与设备推断来源不能互相改写')
                    self._references(c,patient,payload)
            c.execute('INSERT INTO event_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                (identifier,revision+1,'correction' if correction else 'withdrawal',b['occurred_at'] if correction else event['occurred_at'],
                 encode(payload),b['reason'],revision,principal.account_id,at,1))
            updated=event_view(c,identifier)
            self._notice(c,updated,at,'revision');self._process(c,updated,at)
            return Result(event_view(c,identifier),resource_type='SourceEvent',resource_id=identifier)
        if action=='records_device_bind':
            device=c.execute('SELECT * FROM s03_devices WHERE device_id=?',(b['device_id'],)).fetchone()
            if not device:
                raise AppError(404,'DEVICE_NOT_REGISTERED','此设备未可信登记；真实设备协议尚未接入')
            existing=c.execute("SELECT * FROM s03_device_bindings WHERE device_id=? AND status='active'",(b['device_id'],)).fetchone()
            if existing:
                if existing['patient_id']!=patient:
                    raise AppError(409,'DEVICE_BINDING_CONFLICT','设备已有有效关联')
                return Result(self.binding_view(existing),201,resource_type='DeviceBinding',resource_id=existing['binding_id'])
            identifier=uid()
            c.execute('INSERT INTO s03_device_bindings VALUES (?,?,?,?,?,?,?,?)',(identifier,b['device_id'],patient,'active',at,None,1,at))
            view=self.binding_view(self._binding(c,identifier))
            c.execute('INSERT INTO s03_device_binding_history VALUES (?,?,?)',(identifier,1,encode(view)))
            self._binding_audit(c,principal,view,at)
            return Result(view,201,resource_type='DeviceBinding',resource_id=identifier)
        if action=='records_device_revoke':
            row=self._binding(c,params['id'])
            if row['revision']!=b['expected_revision']:
                raise AppError(409,'REVISION_CONFLICT','设备关联已有新修订')
            if row['status']=='revoked':
                raise AppError(409,'DEVICE_ALREADY_REVOKED','设备关联已撤销')
            c.execute("UPDATE s03_device_bindings SET status='revoked',revoked_at=?,revision=revision+1,updated_at=? WHERE binding_id=?",(at,at,params['id']))
            view=self.binding_view(self._binding(c,params['id']))
            c.execute('INSERT INTO s03_device_binding_history VALUES (?,?,?)',(params['id'],view['meta']['revision'],encode(view)))
            self._binding_audit(c,principal,view,at,b['reason'])
            return Result(view,resource_type='DeviceBinding',resource_id=params['id'])
        if action=='records_demo_device':
            patient=b['patient_id']
            device=c.execute('SELECT * FROM s03_devices WHERE device_id=?',(b['device_id'],)).fetchone()
            binding=c.execute("SELECT * FROM s03_device_bindings WHERE device_id=? AND status='active'",(b['device_id'],)).fetchone()
            if b['scenario']=='unbound' or not device or not binding or binding['patient_id']!=patient:
                raise AppError(403,'DEVICE_NOT_AUTHORIZED','模拟设备尚未有效关联至此患者')
            measurement=b['scenario'] in {'measurement_missing','unknown_unit'}
            if measurement and device['kind']!='wearable' or not measurement and device['kind']!='box':
                raise AppError(422,'DEVICE_SCENARIO_MISMATCH','设备种类与固定场景不一致')
            if measurement:
                payload={'metric_code':'sleep_duration','value':None if b['scenario']=='measurement_missing' else 7,
                         'unit':'h' if b['scenario']=='measurement_missing' else 'unregistered_demo_unit','method_code':None,
                         'missing_reason':'演示缺失采集' if b['scenario']=='measurement_missing' else None}
            else:
                payload={'reported_status':None,'observation':'box_opened','medication_id':None,'dose_slot_id':None,'plan_ref':None,'raw_text':None}
            source_id='demo:'+fingerprint([b['device_id'],b['scenario_run_id'],'measurement' if measurement else 'box'])
            event=self._ingest(c,patient,device['kind'],b['device_id'],source_id,'measurement' if measurement else 'medication',
                         None if measurement else 'box_opening',b['occurred_at'],payload,at,device=b['device_id'])
            return Result(event,201,resource_type='SourceEvent',resource_id=event['event_id'])
        raise RuntimeError('unregistered records write')
