"""Bundled local technical support profiles; no clinical scores or medical review."""

import json

from ..core.errors import AppError
from . import store

DEFAULT_PROFILE = "support-default"
STATE_EVENTS = {"support-default": False, "support-explicit-needs": True}
MODE_SECONDS = 7200
INVITATION_SECONDS = 86400
OFFER_COOLDOWN_SECONDS = 86400
NODE_WINDOW_SECONDS = 86400
CHECKIN_OFFSETS = {"week_1": 7, "week_4": 28}
CHECKIN_DAYS = tuple(CHECKIN_OFFSETS.values())


def active(conn):
    row = conn.execute(
        "SELECT profile_id FROM b_support_rule WHERE singleton=1"
    ).fetchone()
    return row[0] if row else DEFAULT_PROFILE


def select(db, profile_id):
    if profile_id not in STATE_EVENTS:
        raise AppError(404, "RULE_PROFILE_UNREGISTERED", "规则配置未登记")
    with db.transaction() as conn:
        previous = active(conn)
        cancelled = 0
        if previous != profile_id and not STATE_EVENTS[profile_id]:
            for row in conn.execute(
                "SELECT record_id,document_json FROM b_records WHERE kind='Invitation'"
            ).fetchall():
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
        conn.execute(
            "INSERT INTO b_support_rule VALUES (1,?) ON CONFLICT(singleton) DO UPDATE SET profile_id=excluded.profile_id",
            (profile_id,),
        )
    return {
        "profile_id": profile_id,
        "changed": previous != profile_id,
        "cancelled_invitations": cancelled,
        "is_simulated": True,
    }
