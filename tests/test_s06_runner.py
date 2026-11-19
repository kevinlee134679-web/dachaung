from datetime import timedelta
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import test_s02 as prior
from medplatform import s04_store
from medplatform.documents import stamp
from medplatform.errors import AppError
from medplatform.s06_runner import Runner
from medplatform.web import create_app


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.h = prior.S02Tests()
        self.h.setUp()
        self.addCleanup(self.h.doCleanups)
        self.runner = Runner(self.h.app)
        self.execution = self.h.app.state.s03_execution
        self.env = dict(os.environ, APP_ENV='test', AUTH_MODE='demo', LLM_MODE='mock',
                        DIALOGUE_PIPELINE='single_pass', HOST='127.0.0.1', PORT='8000',
                        DATABASE_PATH=str(self.h.db.path))

    def run_cycle(self):
        with self.runner.exclusive():
            return self.runner.cycle()

    def facts(self):
        with self.h.db.connection(readonly=True) as conn:
            return s04_store.records(conn, 'CheckinNode', prior.PA), s04_store.records(conn, 'Invitation', prior.PA)

    def test_cycle_requires_single_runner_lock(self):
        with self.assertRaises(AppError) as error:
            self.runner.cycle()
        self.assertEqual(error.exception.code, 'RUNNER_LOCK_REQUIRED')

    def test_other_process_cannot_run_same_database_and_release_allows_restart(self):
        command = [sys.executable, '-B', '-X', 'utf8', '-m', 'medplatform', 'run-worker', '--once']
        with self.runner.exclusive():
            result = subprocess.run(command, env=self.env, capture_output=True, text=True, encoding='utf8', timeout=10)
            self.assertEqual(result.returncode, 2)
            self.assertIn('RUNNER_ALREADY_RUNNING', result.stderr)
        result = subprocess.run(command, env=self.env, capture_output=True, text=True, encoding='utf8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('s06-runner-v1', result.stdout)

    def test_periodic_nodes_use_original_enrollment_and_never_duplicate(self):
        self.h.confirm(effective_from=stamp(self.h.clock()))
        self.h.time[0] += timedelta(days=7)
        first = self.run_cycle()
        self.assertEqual(first['completed'], 3)  # All three seeded patients share enrollment.
        nodes, invites = self.facts()
        self.assertEqual((len(nodes), len(invites)), (1, 1))
        self.assertEqual(invites[0]['status'], 'pending')
        self.assertIsNone(invites[0]['displayed_at'])
        self.assertIsNone(invites[0]['resolved_session_id'])
        self.assertEqual(self.run_cycle()['executions'], 0)
        self.assertEqual(self.facts(), (nodes, invites))

    def test_long_downtime_records_missed_nodes_without_sending_stale_invites(self):
        self.h.confirm(effective_from=stamp(self.h.clock()))
        self.h.time[0] += timedelta(days=35)
        self.run_cycle()
        nodes, invites = self.facts()
        self.assertEqual(len(nodes), 2)
        self.assertTrue(all(n['outcome'] == 'missed' for n in nodes))
        self.assertEqual(invites, [])
        self.run_cycle()
        self.assertEqual(len(self.facts()[0]), 2)

    def test_mode_expiry_records_once_without_web_open(self):
        session = self.h.call(self.h.a, 'POST', '/sessions', {'patient_id':prior.PA, 'case_id':None,
                                  'entry_source':'user','invitation_id':None}, expected=201)
        self.h.call(self.h.a, 'PUT', '/sessions/'+session['session_id']+'/ui-mode',
                    {'ui_mode':'simplified','expected_revision':1,'confirmed':True,'source_suggestion_id':None})
        self.h.time[0] += timedelta(hours=2, seconds=1)
        self.assertEqual(self.run_cycle()['completed'], 1)
        self.run_cycle()
        with self.h.db.connection(readonly=True) as conn:
            state = s04_store.by_id(conn, 'UIState', session['session_id'])
            changes = s04_store.records(conn, 'ModeChange', prior.PA)
        self.assertEqual(state['ui_mode'], 'normal')
        self.assertEqual(sum(c['source'] == 'expiry' for c in changes), 1)

    def test_per_cycle_work_is_bounded_and_next_cycle_resumes(self):
        self.h.app.state.settings.RUNNER_MAX_TASKS = 1
        with self.h.db.transaction() as conn:
            for n in range(2):
                self.execution.create_in_transaction(conn, None, dict(patient_id=prior.PA, owner_module='A',
                    kind='refresh_statistics', owner_operation_key='bounded-'+str(n), scheduled_at=stamp(self.h.clock()),
                    valid_until=stamp(self.h.clock()+timedelta(hours=1)), intervention_id=None, rule_version='demo-test',
                    payload={'window_start':stamp(self.h.clock()-timedelta(days=1)), 'window_end':stamp(self.h.clock()), 'data_environment':'demo'}), internal=True)
        self.assertEqual(self.run_cycle()['completed'], 1)
        self.assertEqual(self.run_cycle()['completed'], 1)
        self.assertEqual(self.run_cycle()['executions'], 0)

    def test_interrupted_local_node_recovers_with_original_attempt_history(self):
        self.h.confirm(effective_from=stamp(self.h.clock()))
        self.h.time[0] += timedelta(days=7)
        with self.h.db.transaction() as conn:
            self.h.app.state.s04.state.prepare_checkins(conn, prior.PA)
            tasks = [json.loads(r[0]) for r in conn.execute('SELECT document_json FROM a_tasks')]
        task = min(tasks, key=lambda t:t['scheduled_at'])
        with patch.object(self.execution, '_complete', side_effect=SystemExit('simulated process death')):
            with self.assertRaises(SystemExit):
                self.execution.run_once(None, task['task_id'], 1, 'controlled-crash-original-key')
        self.h.time[0] += timedelta(seconds=91)
        self.assertEqual(self.run_cycle()['executions'], 2)  # Other patients' due nodes, not A's retry.
        with self.h.db.connection(readonly=True) as conn:
            recovered = self.execution._task(conn, task['task_id'])
        self.assertEqual((recovered['status'], recovered['attempt_count']), ('retry_wait', 1))
        self.h.time[0] += timedelta(seconds=61)
        self.assertEqual(self.run_cycle()['completed'], 1)
        self.assertEqual(len(self.facts()[1]), 1)
        with self.h.db.connection(readonly=True) as conn:
            executions = [json.loads(r[0]) for r in conn.execute('SELECT document_json FROM a_executions WHERE task_id=? ORDER BY attempt', (task['task_id'],))]
        self.assertEqual([e['execution_status'] for e in executions], ['failed','completed'])
        self.assertEqual([e['attempt'] for e in executions], [1,2])

    def test_unknown_delivery_never_becomes_pending_again(self):
        self.h.confirm(effective_from=stamp(self.h.clock()))
        settings = prior.defaults();settings['enabled'] = True
        self.h.call(self.h.a, 'PUT', '/patients/'+prior.PA+'/reminder-preferences', {'expected_revision':0, 'settings':settings})
        self.h.time[0] += timedelta(hours=2)  # 20:00 Asia/Shanghai in the fixed fixture.
        self.execution.delivery_adapter = lambda *_: {'outcome_unknown':True}
        self.assertEqual(self.run_cycle()['failed'], 1)
        self.assertEqual(self.run_cycle()['executions'], 0)
        with self.h.db.connection(readonly=True) as conn:
            rows = [json.loads(r[0]) for r in conn.execute("SELECT document_json FROM a_executions")]
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM a_in_app_notifications').fetchone()[0], 0)
        self.assertEqual(rows[0]['execution_status'], 'outcome_unknown')
        self.assertFalse(rows[0]['retryable'])

    def test_app_factory_and_health_do_not_start_worker_or_create_due_tasks(self):
        self.h.confirm(effective_from=stamp(self.h.clock()))
        self.h.time[0] += timedelta(days=7)
        with TestClient(create_app(self.h.settings, clock=self.h.clock), base_url='http://127.0.0.1:8000') as client:
            self.assertEqual(client.get('/api/v1/health').status_code, 200)
        self.assertEqual(self.facts(), ([], []))
        with self.h.db.connection(readonly=True) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM a_tasks').fetchone()[0], 0)

    @unittest.skipUnless(os.name != 'nt', 'POSIX subprocess termination; Windows locking covered by implementation boundary')
    def test_signal_stops_worker_and_releases_lock(self):
        process = subprocess.Popen([sys.executable, '-B', '-m', 'medplatform', 'run-worker'], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        import select
        ready, _, _ = select.select([process.stdout], [], [], 10)
        self.assertTrue(ready)
        self.assertIn('runner_version', process.stdout.readline())
        process.send_signal(signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, stderr)
        with self.runner.exclusive():
            self.assertTrue(self.runner.owns_lock)
