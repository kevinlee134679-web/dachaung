"""Versioned local technical support policies; no clinical scores or medical review."""

import json

from ..core.config import ROOT
from ..core.documents import encode, fingerprint, stamp, uid
from ..core.errors import AppError
from . import store

FIELDS = {
    "profile_id",
    "version",
    "mode_seconds",
    "invitation_seconds",
    "offer_cooldown_seconds",
    "node_offsets",
    "node_window_seconds",
    "state_events",
    "is_simulated",
}


def _stored(row):
    p = json.loads(row["document_json"])
    if (
        set(p) != FIELDS
        or p["version"] != row["version"]
        or p["profile_id"] != row["profile_id"]
        or fingerprint(p) != row["content_hash"]
    ):
        raise AppError(503, "RULE_VERSION_CONFLICT", "已登记规则完整性校验失败")
    return p


def catalog():
    profiles = json.loads(
        (ROOT / "data/demo/support_rules.json").read_text(encoding="utf8")
    )["profiles"]
    seen = set()
    for p in profiles:
        if set(p) != FIELDS:
            raise AppError(503, "RULE_CONFIG_INVALID", "规则字段不符合登记格式")
        if (
            not isinstance(p["profile_id"], str)
            or not isinstance(p["version"], str)
            or not 1 <= len(p["profile_id"]) <= 128
            or not 1 <= len(p["version"]) <= 128
            or any(
                not value.isascii() or not all(c.isalnum() or c in "-_." for c in value)
                for value in (p["profile_id"], p["version"])
            )
            or p["version"] in seen
            or p["mode_seconds"] != 7200
            or p["invitation_seconds"] != 86400
            or p["offer_cooldown_seconds"] != 86400
            or p["node_offsets"] != [7, 28]
            or p["node_window_seconds"] != 86400
            or type(p["state_events"]) is not bool
            or p["is_simulated"] is not True
        ):
            raise AppError(503, "RULE_CONFIG_INVALID", "规则未登记或超出现有确认范围")
        seen.add(p["version"])
    return profiles


def reference(policy):
    if policy.get("_reference") == "s04-support-v1":
        return "s04-support-v1"
    return policy["version"] + ":" + fingerprint(policy)[:16]


def seed(db, clock):
    added = 0
    with db.transaction() as conn:
        for p in catalog():
            row = conn.execute(
                "SELECT * FROM b_rule_versions WHERE version=?", (p["version"],)
            ).fetchone()
            if row:
                _stored(row)
                if row["content_hash"] != fingerprint(p):
                    raise AppError(
                        409, "RULE_VERSION_CONFLICT", "已登记规则版本内容不可覆盖"
                    )
                continue
            ordinal = conn.execute(
                "SELECT coalesce(max(ordinal),0)+1 FROM b_rule_versions WHERE profile_id=?",
                (p["profile_id"],),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO b_rule_versions VALUES (?,?,?,?,?,?)",
                (
                    p["version"],
                    p["profile_id"],
                    ordinal,
                    fingerprint(p),
                    encode(p),
                    stamp(clock()),
                ),
            )
            added += 1
    return {"versions_added": added, "is_simulated": True}


def policy(conn, profile_id="support-default"):
    selected = conn.execute(
        "SELECT version FROM b_rule_selection WHERE singleton=1"
    ).fetchone()
    if selected:
        row = conn.execute(
            "SELECT * FROM b_rule_versions WHERE version=?", (selected["version"],)
        ).fetchone()
        if row is None:
            raise AppError(503, "RULE_VERSION_UNAVAILABLE", "原规则版本不可用")
        return _stored(row)
    candidate = next((p for p in catalog() if p["profile_id"] == profile_id), None)
    if candidate is None:
        raise AppError(503, "RULE_CONFIG_INVALID", "默认规则配置未登记")
    row = conn.execute(
        "SELECT content_hash FROM b_rule_versions WHERE version=?",
        (candidate["version"],),
    ).fetchone()
    if row and row["content_hash"] != fingerprint(candidate):
        raise AppError(503, "RULE_VERSION_CONFLICT", "默认规则内容与原登记不一致")
    return candidate


def by_reference(conn, ref):
    if ref == "s04-support-v1":
        return dict(
            next(p for p in catalog() if p["profile_id"] == "support-default"),
            _reference=ref,
        )
    version = ref.split(":", 1)[0]
    row = conn.execute(
        "SELECT * FROM b_rule_versions WHERE version=?", (version,)
    ).fetchone()
    candidates = [_stored(row)] if row else catalog()
    found = next((p for p in candidates if reference(p) == ref), None)
    if found is None:
        raise AppError(409, "RULE_VERSION_UNAVAILABLE", "任务的原规则版本不可核验")
    return found


def select(
    db,
    clock,
    profile_id,
    expected_revision,
    *,
    confirmed=False,
    default_profile="support-default",
    version=None,
):
    if not confirmed:
        raise AppError(422, "CONFIRMATION_REQUIRED", "须明确确认选择已登记规则")
    with db.transaction() as conn:
        previous_policy = policy(conn, default_profile)
        old = conn.execute(
            "SELECT * FROM b_rule_selection WHERE singleton=1"
        ).fetchone()
        revision = old["revision"] if old else 0
        if expected_revision != revision:
            raise AppError(
                409, "RULE_REVISION_CONFLICT", "规则选择已变化，请先读取当前版本"
            )
        target = conn.execute(
            "SELECT * FROM b_rule_versions WHERE profile_id=? AND (? IS NULL OR version=?) ORDER BY ordinal DESC LIMIT 1",
            (profile_id, version, version),
        ).fetchone()
        if target is None:
            raise AppError(404, "RULE_PROFILE_UNREGISTERED", "须先显式登记规则版本")
        p = _stored(target)
        if old and old["version"] == p["version"]:
            return dict(old, changed=False, is_simulated=True)
        cancelled = 0
        if reference(previous_policy) != reference(p) and not p["state_events"]:
            rows = conn.execute(
                "SELECT record_id,document_json FROM b_records WHERE kind='Invitation'"
            ).fetchall()
            for row in rows:
                invite = json.loads(row["document_json"])
                if (
                    invite["trigger_type"] == "state_event"
                    and invite["status"] == "pending"
                ):
                    store.update(
                        conn,
                        "Invitation",
                        row["record_id"],
                        dict(invite, status="cancelled"),
                    )
                    cancelled += 1
        at = stamp(clock())
        conn.execute(
            "INSERT INTO b_rule_selection VALUES (1,?,?,?) ON CONFLICT(singleton) DO UPDATE SET version=excluded.version,revision=excluded.revision,selected_at=excluded.selected_at",
            (p["version"], revision + 1, at),
        )
        conn.execute(
            "INSERT INTO b_rule_selection_history VALUES (?,?,?,?,?,?,?)",
            (
                uid(),
                old["version"] if old else None,
                p["version"],
                revision + 1,
                cancelled,
                "explicit-local-operator",
                at,
            ),
        )
        return {
            "version": p["version"],
            "revision": revision + 1,
            "changed": True,
            "cancelled_invitations": cancelled,
            "is_simulated": True,
        }
