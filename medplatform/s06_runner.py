"""Explicit single runner per canonical database; web startup never launches it."""
from contextlib import contextmanager
from datetime import datetime, time, timedelta
import json
import os
import signal
import stat
import threading

from .documents import all_docs, stamp
from .errors import AppError
from .journal import locked
from .s02_service import SHANGHAI

VERSION = 's06-runner-v1'


class Runner:
    def __init__(self, app, *, stop=None):
        self.app = app
        self.execution = app.state.s03_execution
        self.support = app.state.s04.state
        self.db, self.clock = self.execution.db, self.execution.clock
        self.stop = stop or threading.Event()
        self.owns_lock = False

    @contextmanager
    def exclusive(self):
        path = self.db.path.with_name(self.db.path.name + '.runner.lock')
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        with os.fdopen(descriptor, 'r+b') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or (os.name != 'nt' and
                    (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o022)):
                raise AppError(503, 'RUNNER_LOCK_UNAVAILABLE', '运行器锁文件不可安全使用')
            if info.st_size == 0:
                stream.write(b'0')
                stream.flush()
            try:
                lock = locked(stream, 1)
                lock.__enter__()
            except OSError:
                raise AppError(409, 'RUNNER_ALREADY_RUNNING', '该数据库已有运行器；请核对原进程') from None
            try:
                self.owns_lock = True
                yield self
            finally:
                self.owns_lock = False
                lock.__exit__(None, None, None)

    def cycle(self):
        if not self.owns_lock:
            raise AppError(409, 'RUNNER_LOCK_REQUIRED', '运行器须先取得单实例锁')
        result = dict(patients=0, executions=0, completed=0, failed=0, races=0, prepared_nodes=0, issues=[])
        with self.db.connection(readonly=True) as conn:
            patients = [p['patient_id'] for p in all_docs(conn, 'Patient') if p['meta']['is_simulated']]
        today = self.clock().astimezone(SHANGHAI).date()
        start = datetime.combine(today, time(), SHANGHAI)
        end = start + timedelta(days=31)
        for patient in patients:
            if self.stop.is_set():
                break
            self.execution.maintenance(None, patient, stamp(start), stamp(end))
            with self.db.transaction() as conn:
                result['prepared_nodes'] += self.support.prepare_checkins(conn, patient)
            result['patients'] += 1
        at = stamp(self.clock())
        with self.db.connection(readonly=True) as conn:
            tasks = [json.loads(r[0]) for r in conn.execute('''
                SELECT document_json FROM a_tasks
                WHERE json_extract(document_json,'$.status') IN ('pending','retry_wait')
                  AND json_extract(document_json,'$.scheduled_at') <= ?
                  AND json_extract(document_json,'$.valid_until') > ?
                  AND coalesce(json_extract(document_json,'$.next_attempt_at'), '') <= ?
                ORDER BY json_extract(document_json,'$.scheduled_at'),task_id LIMIT ?
            ''', (at, at, at, self.app.state.settings.RUNNER_MAX_TASKS))]
        for task in tasks:
            if self.stop.is_set():
                break
            try:
                outcome = self.execution.run_once(None, task['task_id'], task['meta']['revision'],
                         f"runner:{task['task_id']}:{task['attempt_count']+1}").data
                result['executions'] += 1
                result['completed' if outcome['execution_status'] == 'completed' else 'failed'] += 1
            except AppError as error:
                if error.status not in (403, 404, 409, 503):
                    raise
                result['failed' if error.status >= 500 else 'races'] += 1
                result['issues'].append({'status':error.status, 'code':error.code})
        return result

    def run(self, *, once=False):
        handlers = {}
        if threading.current_thread() is threading.main_thread():
            for code in (signal.SIGINT, signal.SIGTERM):
                handlers[code] = signal.getsignal(code)
                signal.signal(code, lambda *_: self.stop.set())
        try:
            with self.exclusive():
                while not self.stop.is_set():
                    result = self.cycle()
                    print(json.dumps(dict(runner_version=VERSION, **result)), flush=True)
                    if once:
                        return result
                    self.stop.wait(self.app.state.settings.RUNNER_POLL_SECONDS)
        finally:
            for code, handler in handlers.items():
                signal.signal(code, handler)
