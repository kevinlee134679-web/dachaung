"""Atomic receipts for local database effects; protected sensitive responses."""
import json
import threading
from dataclasses import dataclass
from datetime import timedelta

from .auth import digest
from .documents import encode, fingerprint, stamp, uid
from .errors import AppError
from .protection import protect, unprotect


@dataclass
class Result:
    data: dict | None
    status: int = 200
    token: str | None = None
    sensitive_until: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    error: dict | None = None


class Receipts:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock
        self._lock = threading.Lock()
        self._running = set()

    def run(self, scope, key, canonical, authorize, operation, replay=None):
        scope_hash, key_hash = fingerprint(scope), digest(key)
        fp = fingerprint(canonical)
        running = (scope_hash,key_hash)
        with self._lock:
            if running in self._running:
                raise AppError(409,'OPERATION_IN_PROGRESS','同一操作正在处理，请稍后用原键核查')
            self._running.add(running)
        try:
            with self.db.transaction() as conn:
                authorize(conn)  # Current rights, including the underlying data, before replay.
                row=conn.execute('SELECT * FROM idempotency_receipts WHERE scope_hash=? AND key_hash=?',running).fetchone()
                at=stamp(self.clock())
                if row:
                    if row['request_fingerprint'] != fp:
                        raise AppError(409,'IDEMPOTENCY_CONFLICT','同一操作键对应不同内容')
                    if row['full_receipt_until']<=at or row['state']=='expired':
                        raise AppError(409,'IDEMPOTENCY_EXPIRED','原操作键已过期，请先查询原资源再决定新操作')
                    if row['state']=='processing':
                        raise AppError(409,'OPERATION_IN_PROGRESS','原操作正在处理，请核查原结果')
                    if row['sensitive_until'] is not None and row['sensitive_until']<=at:
                        raise AppError(409,'SENSITIVE_RECEIPT_EXPIRED','敏感回执已过期，不能用旧键创建新事实')
                    if row['protected_response'] is not None:
                        if row['sensitive_until']<=at:
                            raise AppError(409,'SENSITIVE_RECEIPT_EXPIRED','敏感回执已过期，不能用旧键创建新事实')
                        body=json.loads(unprotect(row['protected_response'],'receipt:'+row['receipt_id']))
                    else:
                        saved=conn.execute('SELECT response_json FROM receipt_responses WHERE response_ref=?',(row['response_ref'],)).fetchone()
                        if not saved:
                            raise AppError(503,'RECEIPT_UNAVAILABLE','原回执不可用，请核查原资源')
                        body=json.loads(saved[0])
                    result=Result(**body)
                    return replay(conn,result) if replay else result
                result=operation(conn)
                receipt_id=uid()
                body={'data':result.data,'status':result.status,'token':result.token,'sensitive_until':result.sensitive_until,
                      'resource_type':result.resource_type,'resource_id':result.resource_id,'error':result.error}
                protected = protect(encode(body).encode('utf8'),'receipt:'+receipt_id) if result.sensitive_until else None
                response_ref = None if protected else uid()
                if response_ref:
                    conn.execute('INSERT INTO receipt_responses VALUES (?,?)',(response_ref,encode(body)))
                conn.execute('INSERT INTO idempotency_receipts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (receipt_id,scope_hash,key_hash,fp,'rejected' if result.error else 'committed',result.resource_type,result.resource_id,result.status,
                     response_ref,protected,result.sensitive_until,at,stamp(self.clock()+timedelta(days=7)),stamp(self.clock())))
                return result
        finally:
            with self._lock:
                self._running.discard(running)


def expire_receipts(db, clock):
    """Explicit maintenance only: remove expired payloads, retain tombstones/facts."""
    at=stamp(clock());ordinary=0;sensitive=0
    with db.transaction() as c:
        for row in c.execute('SELECT * FROM idempotency_receipts').fetchall():
            if row['full_receipt_until']<=at:
                if row['response_ref']:
                    c.execute('DELETE FROM receipt_responses WHERE response_ref=?',(row['response_ref'],))
                c.execute("UPDATE idempotency_receipts SET state='expired',response_ref=NULL,protected_response=NULL WHERE receipt_id=?",(row['receipt_id'],))
                ordinary+=1
            elif row['sensitive_until'] is not None and row['sensitive_until']<=at and row['protected_response'] is not None:
                c.execute('UPDATE idempotency_receipts SET protected_response=NULL WHERE receipt_id=?',(row['receipt_id'],))
                sensitive+=1
    return {'expired_tombstones':ordinary,'cleared_sensitive_payloads':sensitive}
