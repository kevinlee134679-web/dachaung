"""Closed-by-default O adapter seam. No public login/identity CRUD."""

import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from ..core.documents import digest
from ..core.errors import AppError


@dataclass(frozen=True)
class Account:
    account_id: str
    self_patient_id: str | None = None
    admin: bool = False


@dataclass(frozen=True)
class Principal:
    account_id: str
    session_hash: str = field(repr=False)


class DemoAuthority:
    """Trusted code injects virtual accounts/grants; HTTP body/headers cannot."""

    def __init__(self, accounts=(), clock=lambda: datetime.now(UTC)):
        self.accounts = {a.account_id: a for a in accounts}
        self.bindings: set[tuple[str, str]] = set()
        self.grants: dict[tuple[str, str], set[str]] = {}
        self._sessions = {}
        self._lock = threading.RLock()
        self.clock = clock

    def issue(self, account_id: str) -> tuple[str, str]:
        with self._lock:
            if account_id not in self.accounts:
                raise AppError(401, "AUTH_REQUIRED", "身份未就绪")
            token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self._sessions[digest(token)] = (
                account_id,
                digest(csrf),
                self.clock() + timedelta(hours=8),
            )
            return token, csrf

    def resolve(self, token: str | None) -> Principal:
        with self._lock:
            key = digest(token or "")
            row = self._sessions.get(key)
            if not row or self.clock() >= row[2] or row[0] not in self.accounts:
                raise AppError(401, "AUTH_REQUIRED", "请先通过账号模块登录")
            return Principal(row[0], key)

    def revoke_session(self, principal: Principal):
        with self._lock:
            self._sessions.pop(principal.session_hash, None)

    def _account(self, principal: Principal) -> Account:
        row = self._sessions.get(principal.session_hash)
        if (
            not row
            or row[0] != principal.account_id
            or self.clock() >= row[2]
            or row[0] not in self.accounts
        ):
            raise AppError(401, "AUTH_REQUIRED", "会话已失效")
        return self.accounts[row[0]]

    def require_admin(self, principal: Principal):
        with self._lock:
            if not self._account(principal).admin:
                raise AppError(403, "ADMIN_REQUIRED", "当前账号不能查看管理配置")

    def require_patient(self, principal: Principal, patient_id: str, scope: str):
        with self._lock:
            account = self._account(principal)
            if account.self_patient_id == patient_id:
                return
            key = (account.account_id, patient_id)
            if key not in self.bindings:
                raise AppError(404, "RESOURCE_NOT_FOUND", "资源不可访问")
            if scope not in self.grants.get(key, set()):
                raise AppError(403, "SCOPE_REQUIRED", "当前授权不包含此操作")

    def require_write(
        self,
        principal: Principal,
        csrf: str | None,
        origin: str | None,
        allowed_origins: set[str],
    ):
        with self._lock:
            self._account(principal)
            row = self._sessions[principal.session_hash]
            if origin not in allowed_origins or not secrets.compare_digest(
                row[1], digest(csrf or "")
            ):
                raise AppError(403, "CSRF_REJECTED", "写请求来源或防护令牌无效")
