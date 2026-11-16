"""S03 execution tests use only a fresh isolated database and fictional fixtures."""
import copy
import json
import threading
import unittest
from datetime import timedelta

import test_s02 as baseline
from medplatform.documents import stamp
from medplatform.errors import AppError
from medplatform.s03_execution import S03Execution, ROUTES
from medplatform.s03_execution_inputs import TaskCreateInput, query_input


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=baseline.S02Tests(methodName='runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture;self.s=self.f.app.state.s03_execution
        self.admin_client=self.f.login('demo-admin')
        self.admin=self.s.auth.resolve(self.admin_client.cookies.get('session'))
        self.patient=self.s.auth.resolve(self.f.a.cookies.get('session'))

    def plan(self,*,strict=False,meal=None,minimum=None,times=None):
        draft=self.f.draft(schedule={'kind':'daily','times':times or ['08:00','20:00'],'weekdays':[]})
        entries=copy.deepcopy(draft['entries']);entries[0].update(strict_timing=strict,meal_requirement=meal,min_interval_minutes=minimum)
        draft=self.f.call(self.f.a,'PUT','/drafts/'+draft['draft_id'],{'expected_revision':1,'source_file_ids':[],'entries':entries})
        pending=self.f.pending(draft)
        plan=self.f.confirm(pending,effective_from=stamp(self.f.clock()))
        self.plan_doc=plan
        return plan

    def reminders(self,*,repeats=0,anchors=None,privacy=False,notify_family=False):
        settings=baseline.defaults();settings.update(enabled=True,max_repeats=repeats,
                  repeat_interval_minutes=30 if repeats else None,anchors=anchors or [],privacy_enabled=privacy,notify_family=notify_family)
        return self.f.call(self.f.a,'PUT',f'/patients/{baseline.PA}/reminder-preferences',{'expected_revision':0,'settings':settings})

    def maintain(self,days=1):
        start=self.f.clock();end=start+timedelta(days=days)
        return self.s.maintenance(self.patient,baseline.PA,stamp(start),stamp(end))

    def tasks(self):
        return self.f.call(self.f.a,'GET',f'/patients/{baseline.PA}/tasks')['items']

    def ready(self,**plan):
        self.plan(**plan);self.reminders();self.maintain()
        task=self.tasks()[0]
        from datetime import datetime
        self.f.time[0]=datetime.fromisoformat(task['scheduled_at'])
        return task

    def execute_task(self,task,key=None,expected=200):
        return self.f.call(self.admin_client,'POST','/tasks/'+task['task_id']+'/run',
                           {'expected_revision':task['meta']['revision']},operation=key,expected=expected)

    def test_registered_routes_inputs_query_and_no_browser_creation(self):
        self.assertEqual(len(ROUTES),9)
        self.assertEqual(query_input('tasks',[('limit','1')]),{'limit':'1'})
        for q in ([('limit','1'),('limit','2')],[('unknown','x')],[('limit','101')]):
            with self.assertRaises(AppError):query_input('tasks',q)
        body={'patient_id':baseline.PA,'kind':'refresh_statistics','owner_module':'A','owner_operation_key':'demo:stats',
              'scheduled_at':stamp(self.f.clock()),'valid_until':stamp(self.f.clock()+timedelta(hours=1)),
              'payload':{'window_start':stamp(self.f.clock()),'window_end':stamp(self.f.clock()+timedelta(hours=1)),'data_environment':'demo'},'rule_version':'A-v0.4'}
        self.f.call(self.f.a,'POST','/tasks',body,expected=403)
        created=self.f.call(self.admin_client,'POST','/tasks',body,expected=201)
        same=self.f.call(self.admin_client,'POST','/tasks',body,expected=201)
        self.assertEqual(created['task_id'],same['task_id'])
        body['valid_until']=stamp(self.f.clock()+timedelta(hours=2))
        self.assertEqual(self.f.call(self.admin_client,'POST','/tasks',body,expected=409)['code'],'TASK_CONTENT_CONFLICT')
        self.f.call(self.f.b,'GET','/tasks/'+created['task_id'],expected=404)

    def test_explicit_maintenance_stable_slots_and_private_neutral_content(self):
        self.plan();self.reminders(privacy=True)
        first=self.maintain();before=self.tasks();second=self.maintain()
        self.assertGreater(first['created_tasks'],0);self.assertEqual(second['created_tasks'],0)
        self.assertEqual(before,self.tasks())
        with self.f.db.connection(readonly=True) as c:
            self.assertTrue(all(r[0]=='今日事项待确认。' for r in c.execute('SELECT text_content FROM a_reminder_contents')))
            count=c.execute('SELECT count(*) FROM dose_slots').fetchone()[0]
        self.f.call(self.f.a,'GET',f'/patients/{baseline.PA}/tasks')
        with self.f.db.connection(readonly=True) as c:
            self.assertEqual(count,c.execute('SELECT count(*) FROM dose_slots').fetchone()[0])
        with self.assertRaises(ValueError):self.s.maintenance(self.patient,baseline.PA,stamp(self.f.clock()),stamp(self.f.clock()+timedelta(days=32)))

    def test_run_submitted_replay_restart_and_no_real_delivery(self):
        task=self.ready();operation=baseline.key();executed=self.execute_task(task,operation)
        self.assertEqual(executed['execution_status'],'completed');self.assertEqual(executed['delivery_status'],'submitted')
        self.assertIsNone(executed['delivered_at']);self.assertTrue(executed['is_simulated'])
        restarted=S03Execution(self.f.db,self.s.auth,self.s.receipts,self.f.clock,self.s.analytics)
        replay=restarted.run_once(self.admin,task['task_id'],task['meta']['revision'],operation).data
        self.assertEqual(executed,replay)
        self.execute_task(task,expected=409)
        with self.f.db.connection(readonly=True) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM a_executions').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM a_in_app_notifications').fetchone()[0],1)

    def test_adapter_outside_lock_concurrency_and_cancel_safepoint(self):
        task=self.ready();started=threading.Event();release=threading.Event();out=[]
        def adapter(t,e):
            with self.f.db.transaction() as c:c.execute('SELECT 1')
            started.set();release.wait(5)
            return {'delivery_status':'submitted'}
        self.s.delivery_adapter=adapter
        operation=baseline.key()
        def worker():
            try:out.append(self.s.run_once(self.admin,task['task_id'],task['meta']['revision'],operation))
            except BaseException as e:out.append(e)
        thread=threading.Thread(target=worker);thread.start();self.assertTrue(started.wait(5))
        try:
            with self.assertRaises(AppError) as ctx:self.s.run_once(self.admin,task['task_id'],task['meta']['revision'],operation)
            self.assertEqual(ctx.exception.code,'OPERATION_IN_PROGRESS')
            running=self.f.call(self.f.a,'GET','/tasks/'+task['task_id'])
            cancelled=self.f.call(self.admin_client,'POST','/tasks/'+task['task_id']+'/cancel',{'expected_revision':running['meta']['revision'],'reason':'隔离在途取消'})
            self.assertEqual(cancelled['status'],'running');self.assertTrue(cancelled['cancellation_requested'])
        finally:
            release.set();thread.join(8)
        self.assertFalse(thread.is_alive());self.assertFalse(isinstance(out[0],BaseException),out)
        self.assertEqual(out[0].data['execution_status'],'cancelled')
        with self.f.db.connection(readonly=True) as c:self.assertEqual(c.execute('SELECT count(*) FROM a_in_app_notifications').fetchone()[0],0)

    def test_retry_three_attempts_sixty_seconds_and_unknown_no_retry(self):
        task=self.ready();self.s.delivery_adapter=lambda *a:{'error_code':'MOCK_FAILURE','error_message':'明确未提交','retryable':True}
        for attempt in range(3):
            current=self.f.call(self.f.a,'GET','/tasks/'+task['task_id'])
            result=self.execute_task(current);self.assertEqual(result['attempt'],attempt+1)
            if attempt<2:
                current=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);self.assertEqual(current['status'],'retry_wait')
                self.execute_task(current,expected=409);self.f.time[0]+=timedelta(seconds=60)
        final=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);self.assertEqual(final['status'],'failed');self.execute_task(final,expected=409)

    def test_unknown_and_lease_loss_are_not_resent(self):
        task=self.ready();self.s.delivery_adapter=lambda *a:{'outcome_unknown':True}
        result=self.execute_task(task);self.assertEqual(result['execution_status'],'outcome_unknown');self.assertFalse(result['retryable'])
        self.s.maintain_due(self.admin,baseline.PA)
        final=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);self.assertEqual(final['status'],'failed')
        self.execute_task(final,expected=409)

    def test_lease_fencing_recovery_and_old_result_rejected(self):
        task=self.ready()
        def adapter(t,e):
            self.f.time[0]+=timedelta(seconds=91)
            self.s.maintain_due(self.admin,baseline.PA)
            return {}
        self.s.delivery_adapter=adapter
        error=self.execute_task(task,expected=409);self.assertEqual(error['code'],'TASK_LEASE_LOST')
        current=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);self.assertEqual(current['status'],'retry_wait')
        with self.f.db.connection(readonly=True) as c:self.assertEqual(c.execute('SELECT count(*) FROM a_in_app_notifications').fetchone()[0],0)
        self.f.time[0]+=timedelta(seconds=60);self.s.delivery_adapter=lambda *a:{}
        second=self.execute_task(current);self.assertEqual(second['attempt'],2)

    def test_expiry_and_preference_change_stop_pending(self):
        task=self.ready();self.f.time[0]+=timedelta(minutes=30)
        self.assertEqual(self.s.maintain_due(self.admin,baseline.PA)['expired'],1)
        self.execute_task(task,expected=409)
        settings=baseline.defaults()
        self.f.call(self.f.a,'PUT',f'/patients/{baseline.PA}/reminder-preferences',{'expected_revision':1,'settings':settings})
        self.assertGreaterEqual(self.s.maintain_due(self.admin,baseline.PA)['cancelled'],1)

    def test_snooze_same_source_different_keys_total_three_and_no_event(self):
        task=self.ready();self.execute_task(task)
        source=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);body={'source_task_id':task['task_id'],'expected_task_revision':source['meta']['revision'],'snooze_minutes':5}
        child=self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,expected=201)
        same=self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,expected=200)
        self.assertEqual(child['task_id'],same['task_id'])
        from datetime import datetime
        self.f.time[0]=datetime.fromisoformat(child['scheduled_at']);self.execute_task(child)
        child=self.f.call(self.f.a,'GET','/tasks/'+child['task_id']);body.update(source_task_id=child['task_id'],expected_task_revision=child['meta']['revision'])
        grandchild=self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,expected=201)
        self.f.time[0]=datetime.fromisoformat(grandchild['scheduled_at']);self.execute_task(grandchild)
        last=self.f.call(self.f.a,'GET','/tasks/'+grandchild['task_id']);body.update(source_task_id=last['task_id'],expected_task_revision=last['meta']['revision'])
        self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,expected=409)
        with self.f.db.connection(readonly=True) as c:self.assertEqual(c.execute('SELECT count(*) FROM source_events').fetchone()[0],0)

    def test_snooze_replay_revalidates_configuration_and_cross_patient(self):
        task=self.ready();self.execute_task(task);source=self.f.call(self.f.a,'GET','/tasks/'+task['task_id'])
        body={'source_task_id':task['task_id'],'expected_task_revision':source['meta']['revision'],'snooze_minutes':5};operation=baseline.key()
        self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,operation=operation,expected=201)
        self.f.call(self.f.b,'POST',f'/patients/{baseline.PB}/reminder-snoozes',body,expected=404)
        self.f.call(self.f.a,'PUT',f'/patients/{baseline.PA}/reminder-preferences',{'expected_revision':1,'settings':baseline.defaults()})
        for key in (operation,baseline.key()):self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,operation=key,expected=409)

    def test_strict_meal_and_minimum_prevent_shift(self):
        task=self.ready(meal='餐后（无可靠餐时数据）');self.execute_task(task);source=self.f.call(self.f.a,'GET','/tasks/'+task['task_id'])
        body={'source_task_id':task['task_id'],'expected_task_revision':source['meta']['revision'],'snooze_minutes':5}
        self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,expected=409)
        with self.f.db.connection(readonly=True) as c:
            slot,_,entry=self.s._slot_context(c,baseline.PA,task['payload']['dose_slot_id'])
            for changes in ({'meal_requirement':None,'strict_timing':None},{'meal_requirement':None,'strict_timing':False,'min_interval_minutes':720}):
                altered={**entry,**changes}
                with self.assertRaises(AppError):self.s._validate_shift(c,slot,altered,self.f.clock()+timedelta(minutes=5))

    def test_delivery_receipt_future_expiry_conflict_and_no_delivered(self):
        task=self.ready();result=self.execute_task(task);body={'provider_event_id':baseline.key(),'execution_id':result['execution_id'],'occurred_at':stamp(self.f.clock()),'status':'delivered'}
        receipt=self.s.receive_delivery_receipt('demo-mock-channel',body);self.assertFalse(receipt['applied']);self.assertIsNone(receipt['execution']['delivered_at'])
        same=self.s.receive_delivery_receipt('demo-mock-channel',body);self.assertEqual(receipt,same)
        body['status']='submitted'
        with self.assertRaises(AppError):self.s.receive_delivery_receipt('demo-mock-channel',body)
        body['provider_event_id']=baseline.key();body['occurred_at']=stamp(self.f.clock()+timedelta(seconds=1))
        with self.assertRaises(AppError):self.s.receive_delivery_receipt('demo-mock-channel',body)
        self.f.time[0]+=timedelta(minutes=31);body.update(provider_event_id=baseline.key(),occurred_at=stamp(self.f.clock()))
        receipt=self.s.receive_delivery_receipt('demo-mock-channel',body);self.assertFalse(receipt['applied'])
        self.f.call(self.admin_client,'POST','/integrations/delivery-receipts',body,expected=503)

    def test_analytics_task_and_failure_rolls_back_then_settles(self):
        self.plan();window={'window_start':stamp(self.f.clock()),'window_end':stamp(self.f.clock()+timedelta(hours=2)),'data_environment':'demo'}
        body={'patient_id':baseline.PA,'kind':'refresh_statistics','owner_module':'A','owner_operation_key':'fixture-compute',
              'scheduled_at':stamp(self.f.clock()),'valid_until':stamp(self.f.clock()+timedelta(hours=1)),
              'payload':window,'rule_version':'A-v0.4'}
        task=self.f.call(self.admin_client,'POST','/tasks',body,expected=201)
        old=self.s.analytics.refresh_statistics_in_transaction
        def fail(*args):raise AppError(503,'INJECTED_COMPUTE_FAILURE','隔离计算依赖失败')
        self.s.analytics.refresh_statistics_in_transaction=fail
        first=self.execute_task(task);self.assertEqual(first['execution_status'],'failed');self.assertTrue(first['retryable'])
        current=self.f.call(self.f.a,'GET','/tasks/'+task['task_id']);self.assertEqual(current['status'],'retry_wait')
        self.s.analytics.refresh_statistics_in_transaction=old;self.f.time[0]+=timedelta(seconds=60)
        result=self.execute_task(current);self.assertEqual(result['execution_status'],'completed');self.assertIsNotNone(result['result_ref']);self.assertEqual(result['delivery_status'],'not_applicable')

    def test_rolling_materialization_stable_slots_and_notice_consumption(self):
        plan=self.plan();self.reminders();self.maintain()
        self.f.time[0]+=timedelta(days=31)
        start=stamp(self.f.clock());end=stamp(self.f.clock()+timedelta(days=2))
        first=self.s.maintenance(None,baseline.PA,start,end)
        self.assertGreater(first['materialized_slots'],0)
        with self.f.db.connection(readonly=True) as c:
            ids=[tuple(r) for r in c.execute('SELECT dose_slot_id,scheduled_at FROM dose_slots WHERE scheduled_at>=? ORDER BY scheduled_at',(start,))]
        second=self.s.maintenance(None,baseline.PA,start,end);self.assertEqual(second['materialized_slots'],0)
        with self.f.db.connection(readonly=True) as c:
            self.assertEqual(ids,[tuple(r) for r in c.execute('SELECT dose_slot_id,scheduled_at FROM dose_slots WHERE scheduled_at>=? ORDER BY scheduled_at',(start,))])
            self.assertEqual(c.execute("SELECT count(*) FROM a_notice_consumptions WHERE consumer='A' AND status='applied'").fetchone()[0],1)
            self.assertEqual(c.execute('SELECT count(*) FROM s03_invalidations').fetchone()[0],1)

    def test_family_notification_requires_live_grant_and_retains_exact_reference(self):
        binding,grant=self.f.bind(['notify:receive'])
        self.plan();self.reminders(notify_family=True);self.maintain();task=self.tasks()[0]
        from datetime import datetime
        self.f.time[0]=datetime.fromisoformat(task['scheduled_at']);result=self.execute_task(task)
        with self.f.db.connection(readonly=True) as c:
            recipients=[dict(r) for r in c.execute('SELECT * FROM a_notification_recipients WHERE notification_id=?',(result['result_ref'],))]
        self.assertEqual(len(recipients),2)
        family=next(r for r in recipients if r['grant_id'])
        self.assertEqual(family['grant_id'],grant['grant_id']);self.assertEqual(family['grant_version'],1)
        self.f.call(self.f.a,'POST','/grants/'+grant['grant_id']+'/revoke',{'expected_revision':1,'reason':'隔离演示撤销'})
        self.assertGreater(self.s.maintain_due(self.admin,baseline.PA)['cancelled'],0)

    def test_snooze_transaction_failure_preserves_key_and_budget(self):
        task=self.ready();self.execute_task(task);source=self.f.call(self.f.a,'GET','/tasks/'+task['task_id'])
        body={'source_task_id':task['task_id'],'expected_task_revision':source['meta']['revision'],'snooze_minutes':5};operation=baseline.key()
        with self.f.db.transaction() as c:
            c.execute("CREATE TRIGGER fixture_fail_snooze BEFORE INSERT ON a_reminder_snooze_links BEGIN SELECT RAISE(ABORT,'isolated failure'); END")
            count=c.execute('SELECT count(*) FROM a_tasks').fetchone()[0]
        self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,operation=operation,expected=503)
        with self.f.db.transaction() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM a_tasks').fetchone()[0],count)
            self.assertEqual(c.execute('SELECT count(*) FROM a_reminder_snooze_links').fetchone()[0],0)
            c.execute('DROP TRIGGER fixture_fail_snooze')
        self.f.call(self.f.a,'POST',f'/patients/{baseline.PA}/reminder-snoozes',body,operation=operation,expected=201)


if __name__=='__main__':unittest.main()
