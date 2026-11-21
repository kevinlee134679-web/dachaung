"""Explicit installation of group fixtures and exact O demo recipient records."""

import json
from typing import Literal

from pydantic import TypeAdapter

from ...core.config import ROOT
from ...core.documents import encode, now, stamp
from ...core.errors import AppError
from ...core.migrations import status
from ...identity.sharing import install_demo_recipients
from ...web.inputs import ID, Input, Short, Text
from ..catalog.service import ResourceFixture, install_catalog

FIXTURE = "data/demo/peer_groups.json"


class PeerGroup(Input):
    group_id: ID
    resource_id: ID
    title: Short
    description: Text
    matching_tags: list[Short]
    moderator_label: Short
    availability: Literal["available", "unavailable", "unknown"]
    is_simulated: Literal[True]


class GroupFixture(Input):
    group: PeerGroup
    provider_id: ID
    moderator_account_id: ID | None
    resource_version: ID

    def resource(self):
        group = self.group
        return ResourceFixture.model_validate(
            {
                "resource": {
                    "resource_id": group.resource_id,
                    "resource_version": self.resource_version,
                    "service_kind": "peer_support",
                    "name": group.title,
                    "description": group.description,
                    "provider": {
                        "provider_id": self.provider_id,
                        "provider_type": "volunteer",
                        "display_name": "虚构同辈服务主体（模拟）",
                        "qualification_status": "not_required",
                        "is_simulated": True,
                    },
                    "availability": group.availability,
                    "access_mode": "support_free",
                    "is_essential": False,
                    "required_shared_categories": ["support_question"],
                    "optional_shared_categories": [],
                    "peer_group_id": group.group_id,
                    "is_simulated": True,
                },
                "previous_version": None,
                "profile_types": [],
            }
        )


def seed_peer_groups(db, clock=now):
    status(db)
    fixtures = TypeAdapter(list[GroupFixture]).validate_json(
        (ROOT / FIXTURE).read_bytes()
    )
    recipients = json.loads((ROOT / "data/demo/o_peer_recipients.json").read_bytes())
    counts = {"groups_added": 0, "moderators_added": 0}
    with db.transaction() as conn:
        counts["resources_added"] = install_catalog(
            conn, [f.resource() for f in fixtures], stamp(clock())
        )
        counts["recipients_added"] = install_demo_recipients(conn, recipients)
        for fixture in fixtures:
            group = fixture.group
            raw = encode(group.model_dump())
            old = conn.execute(
                "SELECT document_json FROM c_peer_groups WHERE group_id=?",
                (group.group_id,),
            ).fetchone()
            if old and old[0] != raw:
                raise AppError(
                    409, "RESOURCE_VERSION_CONFLICT", "演示小组与原登记不一致"
                )
            if not old:
                conn.execute(
                    "INSERT INTO c_peer_groups VALUES (?,?,?)",
                    (group.group_id, group.resource_id, raw),
                )
                counts["groups_added"] += 1
            account = fixture.moderator_account_id
            if account:
                inserted = conn.execute(
                    """
                    INSERT INTO c_peer_moderators (group_id,account_id)
                    SELECT ?,account_id FROM o_accounts WHERE account_id=? AND is_admin=1
                    ON CONFLICT DO NOTHING
                """,
                    (group.group_id, account),
                ).rowcount
                if not conn.execute(
                    "SELECT 1 FROM c_peer_moderators WHERE group_id=? AND account_id=?",
                    (group.group_id, account),
                ).fetchone():
                    raise AppError(
                        503, "PEER_GROUPS_UNAVAILABLE", "请先初始化受控演示审核身份"
                    )
                counts["moderators_added"] += inserted
    return counts
