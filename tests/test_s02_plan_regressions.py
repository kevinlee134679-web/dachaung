"""S02 storage errors and recurrence validation outside the slot window."""
from datetime import timedelta
import unittest

import test_s02 as support
from medplatform.documents import stamp


class S02PlanRegressionTests(unittest.TestCase):
    def setUp(self):
        # Reuse the isolated virtual fixture without rediscovering its test class.
        self.case=support.S02Tests('test_no_later_phase_routes_or_background_tasks')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def prepare(self, schedule, start, end, interval):
        case=self.case
        draft=case.draft(schedule=schedule)
        entry=draft['entries'][0]
        entry.update(start_date=start,end_date=end,min_interval_minutes=interval)
        draft=case.call(case.a,'PUT',f"/drafts/{draft['draft_id']}",
                        {'expected_revision':1,'source_file_ids':[],'entries':[entry]})
        return case.pending(draft)

    def confirm(self, draft, expected):
        case=self.case
        body=dict(draft_id=draft['draft_id'],draft_revision=draft['content_revision'],
                  existing_plan_id=None,expected_plan_version=None,
                  effective_from=stamp(case.clock()+timedelta(hours=1)),confirmed=True)
        return case.call(case.a,'POST',f'/patients/{support.PA}/plan-confirmations',body,expected=expected)

    def test_file_root_creation_failure_is_a_storage_503(self):
        case=self.case
        case.app.state.s02.file_root.write_bytes(b'isolated blocker, not patient data')
        response=case.upload()
        self.assertEqual(response.status_code,503,response.text)
        self.assertEqual(response.json()['error']['code'],'FILE_STORE_UNAVAILABLE')
        self.assertEqual(case.call(case.a,'GET',f'/patients/{support.PA}/files')['items'],[])
        with case.db.connection(readonly=True) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM s02_source_keys').fetchone()[0],0)

    def test_far_future_daily_entry_cannot_bypass_declared_interval(self):
        draft=self.prepare({'kind':'daily','times':['00:10','23:50'],'weekdays':[]},
                           '2027-01-01',None,60)
        error=self.confirm(draft,422)
        self.assertEqual(error['code'],'MEDICAL_CONSTRAINT_CONFLICT')
        current=self.case.call(self.case.a,'GET',f"/drafts/{draft['draft_id']}")
        self.assertEqual(current['status'],'pending_confirmation')
        self.assertIsNone(current['formal_plan'])
        with self.case.db.connection(readonly=True) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM dose_slots').fetchone()[0],0)
            self.assertEqual(conn.execute('SELECT count(*) FROM change_notices').fetchone()[0],0)

    def test_far_future_weekly_entry_checks_its_full_recurrence(self):
        draft=self.prepare({'kind':'weekly','times':['09:00'],'weekdays':[1]},
                           '2027-01-04',None,10081)
        error=self.confirm(draft,422)
        self.assertEqual(error['code'],'MEDICAL_CONSTRAINT_CONFLICT')

    def test_finite_single_occurrence_does_not_invent_a_later_dose(self):
        draft=self.prepare({'kind':'weekly','times':['09:00'],'weekdays':[1]},
                           '2027-01-04','2027-01-04',10081)
        plan=self.confirm(draft,201)
        self.assertEqual(plan['entries'][0]['end_date'],'2027-01-04')
        with self.case.db.connection(readonly=True) as conn:
            # Publication still materializes only its confirmed 31-day window.
            self.assertEqual(conn.execute('SELECT count(*) FROM dose_slots WHERE plan_id=?',
                                          (plan['plan_id'],)).fetchone()[0],0)
