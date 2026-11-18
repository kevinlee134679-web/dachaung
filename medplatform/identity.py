import base64
import json
import secrets
from contextlib import contextmanager
from datetime import datetime

from .auth import Account, Principal, digest
from .documents import all_docs, get, stamp, encode
from .errors import AppError
from .protection import protect, unprotect
from .s02_inputs import SCOPES


class PersistentAuthority:
    def __init__(self, db, clock):
        self.db, self.clock = db, clock

    @contextmanager
    def connection(self, conn=None):
        if conn is not None:
            yield conn
        else:
            with self.db.connection(readonly=True) as connection:
                yield connection

    def session(self, principal, conn, *, logout_receipt=False):
        row = conn.execute('SELECT * FROM o_sessions WHERE session_hash=? AND account_id=?',
                           (principal.session_hash, principal.account_id)).fetchone()
        if not row or stamp(self.clock()) >= row['expires_at'] or (row['revoked_at'] and not logout_receipt):
            raise AppError(401,'AUTH_REQUIRED','会话已失效，请重新选择演示身份')
        return row

    def resolve(self, token, *, logout_receipt=False):
        with self.connection() as conn:
            row = conn.execute('SELECT account_id FROM o_sessions WHERE session_hash=?',(digest(token or ''),)).fetchone()
            if not row:
                raise AppError(401,'AUTH_REQUIRED','请先选择本地演示身份')
            principal = Principal(row['account_id'],digest(token or ''))
            self.session(principal,conn,logout_receipt=logout_receipt)
            return principal

    def account(self, principal, conn):
        self.session(principal,conn)
        return conn.execute('SELECT * FROM o_accounts WHERE account_id=?',(principal.account_id,)).fetchone()

    def require_admin(self, principal):
        with self.connection() as conn:
            if not self.account(principal,conn)['is_admin']:
                raise AppError(403,'ADMIN_REQUIRED','当前账号不能查看管理配置')

    def scopes(self, principal, patient, conn):
        account = self.account(principal,conn)
        return self._scopes_for_account(account,patient,conn)

    def source_actor_scopes(self, conn, account_id, patient):
        """Use current O scopes for a historical source actor without a session."""
        account = conn.execute('SELECT * FROM o_accounts WHERE account_id=?',(account_id,)).fetchone()
        return self._scopes_for_account(account,patient,conn) if account is not None else []

    def _scopes_for_account(self, account, patient, conn):
        if account['self_patient_id'] == patient:
            return sorted(SCOPES - {'demo:manage','knowledge:manage','knowledge:review'})
        bindings = {d['binding_id'] for d in all_docs(conn,'FamilyBinding',patient)
                    if d['family_account_id']==account['account_id'] and d['status']=='active'}
        scopes = set()
        for grant in all_docs(conn,'Grant',patient):
            if grant['binding_id'] in bindings and grant['status']=='active' and (grant['valid_until'] is None or grant['valid_until']>stamp(self.clock())):
                scopes.update(grant['scopes'])
        return sorted(scopes)

    def is_self(self, principal, patient, conn):
        return self.account(principal,conn)['self_patient_id'] == patient

    def require_patient(self, principal, patient_id, scope, conn=None, *, self_only=False):
        with self.connection(conn) as c:
            if self.is_self(principal,patient_id,c):
                get(c,'Patient',patient_id)
                return
            relation = any(d['family_account_id']==principal.account_id and d['status']=='active'
                           for d in all_docs(c,'FamilyBinding',patient_id))
            if not relation:
                raise AppError(404,'RESOURCE_NOT_FOUND','资源不可访问')
            if self_only:
                raise AppError(403,'PATIENT_CONFIRMATION_REQUIRED','此操作需要患者本人明确完成')
            if scope not in self.scopes(principal,patient_id,c):
                raise AppError(403,'SCOPE_REQUIRED','当前授权不包含此操作')

    def require_write(self, principal, csrf, origin, allowed_origins, *, logout_receipt=False):
        with self.connection() as conn:
            row = self.session(principal,conn,logout_receipt=logout_receipt)
            if origin not in allowed_origins or not secrets.compare_digest(row['csrf_hash'],digest(csrf or '')):
                raise AppError(403,'CSRF_REJECTED','写请求来源或防护令牌无效')

    def context(self, principal, conn):
        account = self.account(principal,conn)
        session = self.session(principal,conn)
        patients = []
        for patient in sorted(all_docs(conn,'Patient'),key=lambda d:d['patient_id']):
            own = patient['patient_id']==account['self_patient_id']
            scopes = self.scopes(principal,patient['patient_id'],conn)
            if own or scopes:
                patients.append({'patient':patient,'relationship':'self' if own else 'family','effective_scopes':scopes})
        current = account['current_patient_id']
        if current not in {p['patient']['patient_id'] for p in patients}:
            current = None
        csrf = unprotect(session['protected_csrf'],'session:'+principal.session_hash).decode('utf8')
        return {'account':{'account_id':account['account_id'],'display_name':account['display_name'],'auth_mode':'demo','is_simulated':True},
                'current_patient_id':current,'patients':patients,'csrf_token':csrf,'expires_at':session['expires_at']}

    def cursor(self, context, last):
        return base64.urlsafe_b64encode(protect(encode({'context':context,'last':last}).encode('utf8'),'cursor-v1')).decode('ascii')

    def read_cursor(self, token, context):
        try:
            if len(token)>8192:
                raise ValueError()
            value=json.loads(unprotect(base64.b64decode(token,altchars=b'-_',validate=True),'cursor-v1'))
            if value['context'] != context or not isinstance(value['last'],list):
                raise ValueError()
            return value['last']
        except (ValueError,KeyError,TypeError,AppError):
            raise AppError(422,'INVALID_CURSOR','分页位置无效，请重新读取列表') from None
