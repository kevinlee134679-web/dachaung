import copy
import json
import unittest
from datetime import datetime, timedelta, timezone

import test_s02 as support
from medplatform.documents import stamp


class S03AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.s = support.S02Tests()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)
        self.window = {'window_start':'2026-11-16T00:00:00+08:00',
                       'window_end':'2026-11-23T00:00:00+08:00','data_environment':'demo'}

    def api(self, method, path, body=None, client=None, expected=200, operation=None):
        return self.s.call(client or self.s.a,method,path,body,expected=expected,operation=operation)

    def prepare(self):
        self.s.time[0] = datetime(2026,11,16,tzinfo=timezone.utc)
        self.s.a = self.s.login('demo-patient-a')
        plan = self.s.confirm(effective_from=stamp(self.s.clock()))
        self.s.time[0] = datetime(2026,11,23,tzinfo=timezone.utc)
        self.s.a = self.s.login('demo-patient-a')
        self.s.b = self.s.login('demo-patient-b')
        self.s.f = self.s.login('demo-family')
        with self.s.db.connection(readonly=True) as c:
            self.slots = [dict(row) for row in c.execute('SELECT * FROM dose_slots WHERE scheduled_at>=? AND scheduled_at<? ORDER BY scheduled_at',
                         ('2026-11-15T16:00:00.000000+00:00','2026-11-22T16:00:00.000000+00:00'))]
        self.assertEqual(len(self.slots),14)
        return plan

    def report(self, index, status='taken', client=None, source=None):
        slot = self.slots[index]
        return self.api('POST',f'/patients/{support.PA}/medication-events',
            {'source_event_id':source or support.key(),'occurred_at':slot['scheduled_at'],'reported_status':status,
             'medication_id':slot['medication_id'],'dose_slot_id':slot['dose_slot_id'],
             'plan_ref':{'plan_id':slot['plan_id'],'plan_version':slot['plan_version']}},client,expected=201)

    def refresh(self, **changes):
        return self.api('POST',f'/patients/{support.PA}/summary-refresh',{**self.window,**changes})

    def get_result(self, kind='medication-statistics',as_of=None,client=None,expected=200):
        from urllib.parse import urlencode
        query = {**self.window}
        if as_of is not None:
            query['as_of']=as_of
        return self.api('GET',f'/patients/{support.PA}/{kind}?'+urlencode(query),client=client,expected=expected)

    def counts(self, stats, expected):
        names = ['patient_confirmed_count','reported_not_taken_count','postponed_count','unconfirmed_evidence_count','unknown_count']
        self.assertEqual([stats[k] for k in names],expected)
        self.assertEqual(sum(stats[k] for k in names),stats['planned_dose_count'])

    def boxes(self, indices):
        self.api('POST',f'/patients/{support.PA}/device-bindings',{'device_id':'demo-box-a','confirmed':True},expected=201)
        admin = self.s.login('demo-admin')
        for i in indices:
            event = self.api('POST','/demo/device-events',{'patient_id':support.PA,'device_id':'demo-box-a','scenario':'normal_box',
                'scenario_run_id':'fixed-box-'+str(i),'occurred_at':self.slots[i]['scheduled_at']},client=admin,expected=201)
            self.api('POST','/dose-matches/review',{'event_id':event['event_id'],'expected_revision':1,
                'dose_slot_id':self.slots[i]['dose_slot_id'],'reason':'虚构固定场景精确核对设备事件与单药时段'},client=admin)

    def test_fourteen_slots_10_then_11_and_old_snapshot_is_immutable(self):
        self.prepare()
        events = [self.report(i) for i in range(10)]
        self.boxes([10,11])
        before = self.refresh()['record_overview'];cutoff = before['as_of']
        self.counts(before,[10,0,0,2,2])
        self.assertEqual(before['patient_confirmation_ratio'],10/14)
        with self.s.db.connection(readonly=True) as c:
            stored = c.execute('SELECT result_json FROM s03_results WHERE result_id=?',(before['statistics_id'],)).fetchone()[0]
        self.s.time[0] += timedelta(seconds=1)
        self.report(12)
        self.api('POST',f'/patients/{support.PA}/medication-events',{
            'source_event_id':self.api('GET','/medication-events/'+events[0]['event_id'])['source_event_id'],
            'occurred_at':self.slots[0]['scheduled_at'],'reported_status':'taken',
            'medication_id':self.slots[0]['medication_id'],'dose_slot_id':self.slots[0]['dose_slot_id'],
            'plan_ref':{'plan_id':self.slots[0]['plan_id'],'plan_version':self.slots[0]['plan_version']}},expected=201)
        after = self.refresh()['record_overview']
        self.counts(after,[11,0,0,2,1]);self.assertNotEqual(before['statistics_id'],after['statistics_id'])
        historical = self.get_result(as_of=cutoff)
        self.assertEqual(historical,before)
        with self.s.db.connection(readonly=True) as c:
            self.assertEqual(stored,c.execute('SELECT result_json FROM s03_results WHERE result_id=?',(before['statistics_id'],)).fetchone()[0])

    def test_five_categories_postponed_followed_by_later_self_final(self):
        self.prepare()
        for i in range(9): self.report(i)
        self.report(9,'not_taken');postponed = self.report(10,'postponed');self.boxes([11,12])
        self.counts(self.refresh()['record_overview'],[9,1,1,2,1])
        self.s.time[0]+=timedelta(seconds=1)
        body={'source_event_id':support.key(),'occurred_at':stamp(datetime.fromisoformat(postponed['occurred_at'])+timedelta(minutes=1)),
              'reported_status':'taken','dose_slot_id':self.slots[10]['dose_slot_id']}
        self.api('POST',f'/patients/{support.PA}/medication-events',body,expected=201)
        self.counts(self.refresh()['record_overview'],[10,1,0,2,1])

    def test_conflict_is_unknown_and_correction_preserves_old_cutoff(self):
        self.prepare();first=self.report(0);second=self.report(0,'not_taken')
        previous=self.refresh()['record_overview'];self.counts(previous,[0,0,0,0,14])
        self.assertIn('conflicting_reports',[x['code'] for x in previous['issues']])
        self.s.time[0]+=timedelta(seconds=1)
        self.api('POST',f"/events/{second['event_id']}/withdrawals",{'expected_revision':1,'reason':'演示撤销相反报告'})
        self.counts(self.refresh()['record_overview'],[1,0,0,0,13])
        self.counts(self.get_result(as_of=previous['as_of']),[0,0,0,0,14])

    def test_read_does_not_materialize_compute_or_rewrite_and_default_is_honestly_stale(self):
        self.prepare()
        self.get_result(expected=409)
        snapshot=self.refresh();cutoff=snapshot['record_overview']['as_of']
        before=self.s.db.path.read_bytes()
        self.get_result(as_of=cutoff)
        self.get_result('medication-trends',as_of=cutoff)
        self.get_result('summary',as_of=cutoff)
        self.assertEqual(before,self.s.db.path.read_bytes())
        self.s.time[0]+=timedelta(seconds=1)
        self.assertEqual(self.get_result()['data_status'],'stale')
        self.assertEqual(self.get_result()['as_of'],cutoff)
        self.assertEqual(before,self.s.db.path.read_bytes())

    def test_summary_expiry_projection_does_not_write(self):
        self.prepare();snapshot=self.refresh();cutoff=snapshot['record_overview']['as_of']
        self.s.time[0]+=timedelta(minutes=15)
        before=self.s.db.path.read_bytes()
        summary=self.get_result('summary',as_of=cutoff)
        self.assertEqual(summary['data_status'],'stale');self.assertEqual(before,self.s.db.path.read_bytes())

    def test_summary_with_legacy_a_signature_keeps_projection_and_expiry(self):
        from unittest.mock import patch

        self.prepare()
        self.report(0)
        analytics = self.s.app.state.s03_analytics
        with patch.object(analytics, 'support_feedback', None):
            snapshot = self.refresh()
        cutoff = snapshot['record_overview']['as_of']
        before = self.s.db.path.read_bytes()
        self.assertEqual(snapshot['feedback_overview']['sources'][0]['availability'], 'not_integrated')
        self.s.time[0] += timedelta(minutes=14, seconds=59)
        self.assertEqual(self.get_result('summary', as_of=cutoff), snapshot)
        self.s.time[0] += timedelta(seconds=1)
        expired = self.get_result('summary', as_of=cutoff)
        self.assertEqual(expired['data_status'], 'stale')
        self.assertEqual(expired['valid_until'], snapshot['valid_until'])
        self.assertEqual(expired['missing_items'][-1]['code'], 'refresh_required')
        self.assertEqual(self.s.db.path.read_bytes(), before)

    def test_empty_plan_is_zero_but_unmaterialized_window_is_not(self):
        empty=self.refresh()['record_overview']
        self.assertEqual(empty['planned_dose_count'],0);self.assertIsNone(empty['patient_confirmation_ratio'])
        self.prepare()
        self.s.time[0]+=timedelta(days=40);self.s.a=self.s.login('demo-patient-a')
        error=self.api('POST',f'/patients/{support.PA}/summary-refresh',{
            'window_start':'2026-12-25T00:00:00+08:00','window_end':'2026-12-26T00:00:00+08:00','data_environment':'demo'},expected=409)
        self.assertEqual(error['code'],'SCHEDULE_WINDOW_NOT_READY')

    def test_invalid_cutoff_environment_query_and_patient_isolation(self):
        self.prepare();self.refresh()
        self.get_result(client=self.s.b,expected=404)
        self.get_result(as_of=stamp(self.s.clock()+timedelta(seconds=1)),expected=422)
        self.api('POST',f'/patients/{support.PA}/summary-refresh',{**self.window,'as_of':None},expected=422)
        self.api('POST',f'/patients/{support.PA}/summary-refresh',{**self.window,'data_environment':'real'},expected=403)
        self.api('GET',f'/patients/{support.PA}/medication-statistics?window_start=x&window_start=y',expected=422)

    def test_family_summary_permission_does_not_expand_components_and_replay_rechecks(self):
        self.prepare();binding,grant=self.s.bind(['summary:read'])
        operation=support.key()
        summary=self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,client=self.s.f,operation=operation)
        self.assertIsNone(summary['record_overview']);self.assertEqual(summary['measurement_overview'],[])
        self.assertIn('restricted',[x['code'] for x in summary['missing_items']])
        self.api('POST',f"/grants/{grant['grant_id']}/revoke",{'expected_revision':1,'reason':'演示撤销摘要权限'})
        self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,client=self.s.f,operation=operation,expected=403)

    def test_replay_after_component_scope_removed_does_not_return_old_body(self):
        self.prepare();binding,grant=self.s.bind(['summary:read','statistics:read','measurements:read'])
        operation=support.key()
        summary=self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,client=self.s.f,operation=operation)
        self.assertIsNotNone(summary['record_overview'])
        self.api('PUT',f"/family-bindings/{binding['binding_id']}/grant",{'expected_revision':1,
            'scopes':['summary:read'],'valid_until':None,'confirmed':True})
        error=self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,client=self.s.f,operation=operation,expected=403)
        self.assertEqual(error['code'],'SOURCE_ACCESS_CHANGED')

    def test_summary_references_a6_and_no_b_c_effects(self):
        self.prepare();self.report(0)
        summary=self.refresh();stats=self.get_result(as_of=summary['record_overview']['as_of'])
        self.assertEqual(summary['record_overview'],stats)
        sources=summary['feedback_overview']['sources']
        self.assertEqual([(s['source_module'],s['availability']) for s in sources],
                         [('B','not_collected'),('C','not_collected')])
        for source in sources:
            self.assertEqual(source['records'],[])
            self.assertTrue(source['reason'])
        self.assertEqual(summary['data_status'],'insufficient')

    def test_measurement_zero_missing_unit_and_method_groups(self):
        from urllib.parse import urlencode
        for value,unit,reason,method in [(0,'count',None,'manual_entry'),(None,'count','未采集','manual_entry'),
                                        (8,'mystery',None,'manual_entry'),(44,'count',None,'other_method')]:
            self.api('POST',f'/patients/{support.PA}/measurements',{'source_event_id':support.key(),'occurred_at':stamp(self.s.clock()),
                'payload':{'metric_code':'step_count','value':value,'unit':unit,'method_code':method,'missing_reason':reason}},expected=201)
        window={**self.window,'window_end':'2026-11-17T00:00:00+08:00','metric_code':'step_count','unit':'count','method_code':'manual_entry'}
        trend=self.api('GET',f'/patients/{support.PA}/measurement-trends?'+urlencode(window))
        self.assertEqual(sorted([p['value'] for p in trend['points']],key=lambda x:x is None),[0,None])
        self.assertIn('unknown_unit',[x['code'] for x in trend['issues']])
        summary=self.refresh(window_end='2026-11-17T00:00:00+08:00')
        overview=[m for m in summary['measurement_overview'] if m['metric_code']=='step_count' and m['method_code']=='manual_entry'][0]
        self.assertEqual(overview['latest_value'],0)
        self.assertTrue(overview['missing_items'])

    def test_failed_refresh_rolls_back_results_notices_and_receipt(self):
        from unittest.mock import patch
        self.prepare()
        analytics=self.s.app.state.s03_analytics
        operation=support.key()
        with self.s.db.connection(readonly=True) as c:
            before=c.execute('SELECT COUNT(*) FROM s03_results').fetchone()[0]
        with patch.object(analytics,'feedback',side_effect=RuntimeError('fictional fault')):
            self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,operation=operation,expected=500)
        with self.s.db.connection(readonly=True) as c:
            self.assertEqual(before,c.execute('SELECT COUNT(*) FROM s03_results').fetchone()[0])
        self.assertIsNotNone(self.api('POST',f'/patients/{support.PA}/summary-refresh',self.window,operation=operation)['summary_id'])


if __name__=='__main__':
    unittest.main()
