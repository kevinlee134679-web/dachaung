import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import ROOT
from .database import Database
from .errors import SchemaError

DIRECTORY = ROOT / "migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


def catalog(directory: Path = DIRECTORY) -> list[Migration]:
    items = []
    for path in sorted(Path(directory).glob("*.sql")):
        match = re.fullmatch(r"(\d{4})_[a-z0-9_]+\.sql", path.name)
        if not match:
            raise SchemaError("迁移文件名不合法")
        raw = path.read_bytes()
        items.append(Migration(int(match[1]), path.name, hashlib.sha256(raw).hexdigest(), raw.decode("utf-8")))
    if not items or [m.version for m in items] != list(range(1, len(items) + 1)):
        raise SchemaError("迁移必须从0001连续且唯一")
    return items


def _applied(conn, items):
    rows = conn.execute("SELECT * FROM schema_migrations ORDER BY version").fetchall()
    if len(rows) > len(items):
        raise SchemaError("数据库版本比当前工程新")
    for index, row in enumerate(rows):
        item = items[index]
        if (row["version"], row["name"], row["checksum"], row["parent_version"]) != (
            item.version, item.name, item.checksum, index or None
        ):
            raise SchemaError("已执行迁移的校验和、顺序或父版本不匹配")
    return len(rows)


def status(db: Database, directory: Path = DIRECTORY) -> int:
    items = catalog(directory)
    with db.connection(readonly=True) as conn:
        conn.execute("SELECT 1").fetchone()
        current = _applied(conn, items)
        if current != len(items):
            raise SchemaError("数据库需要显式迁移")
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"schema_migrations", "operation_audit", "source_events", "dose_slots", "event_revisions", "evidence_slot_links"} <= tables:
            raise SchemaError("必要数据表缺失")
        if current>=3 and not {'o_accounts','o_sessions','o_binding_codes','s02_documents','s02_document_history',
                               's02_source_keys','idempotency_receipts','receipt_responses','change_notices','o_schedule_windows','o_revocation_audit'} <= tables:
            raise SchemaError('S02必要数据表缺失')
        if current >= 7 and not {
            'b_sessions', 'b_messages', 'b_generations', 'b_generation_runs', 'b_records',
            'b_intervention_revisions', 'b_knowledge', 'b_knowledge_history', 'b_model_selection',
        } <= tables:
            raise SchemaError('S04必要数据表缺失')
        if current >= 8 and not {'c_support_resources', 'c_support_resource_versions'} <= tables:
            raise SchemaError('S05资源目录表缺失')
        if current >= 9 and not {
            'o_demo_support_recipients', 'o_sharing_scopes', 'o_sharing_scope_history',
            'c_service_drafts', 'c_service_draft_revisions', 'c_service_confirmations',
            'c_draft_confirmations', 'c_confirmation_revocations',
        } <= tables:
            raise SchemaError('S05草稿或共享范围表缺失')
        if current >= 10 and not {
            'c_services', 'c_service_history', 'c_service_dispatches', 'c_service_provider_receipts',
        } <= tables:
            raise SchemaError('S05正式服务或派发记录表缺失')
        if current >= 11 and 'c_service_feedback' not in tables:
            raise SchemaError('S05服务反馈表缺失')
        return current


def migrate(db: Database, *, initialize: bool = False, target: int | None = None,
            directory: Path = DIRECTORY) -> int:
    items = catalog(directory)
    target = len(items) if target is None else target
    if not 1 <= target <= len(items):
        raise SchemaError("目标迁移版本不合法")
    if initialize:
        db.path.parent.mkdir(parents=True, exist_ok=True)
    with db.connection(create=initialize) as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if "schema_migrations" not in tables:
                if tables or not initialize:
                    raise SchemaError("不是已管理数据库；请核对路径并显式初始化空库")
                conn.execute("""CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY, parent_version INTEGER,
                    name TEXT NOT NULL, checksum TEXT NOT NULL,
                    applied_at TEXT NOT NULL, app_version TEXT NOT NULL) STRICT""")
            current = _applied(conn, items)
            if current > target:
                raise SchemaError("不支持降级或重建旧迁移")
            for item in items[current:target]:
                # executescript implicitly commits: execute complete statements ourselves.
                statement = ""
                for line in item.sql.splitlines(keepends=True):
                    statement += line
                    if sqlite3.complete_statement(statement):
                        conn.execute(statement)
                        statement = ""
                if statement.strip():
                    raise SchemaError("迁移存在未结束语句")
                conn.execute("INSERT INTO schema_migrations VALUES (?,?,?,?,?,?)", (
                    item.version, item.version - 1 or None, item.name, item.checksum,
                    datetime.now(timezone.utc).isoformat(), __version__))
            conn.commit()
            return target
        except BaseException:
            conn.rollback()
            raise
