"""Versioned mock benefits, with personnel resources registered in the existing C/O catalogs."""

import json
from typing import Literal

from pydantic import model_validator

from ...core.documents import encode, now, stamp
from ...core.errors import AppError
from ...core.migrations import status
from ...identity.sharing import SharingAuthority, install_demo_recipients, load_resource
from ...web.inputs import ID, Input, Short, Text
from ..catalog.service import ResourceFixture, install_catalog

RESOURCE = "resource-reward-companionship-demo"
RESOURCE_VERSION = "resource-demo-v1"
REWARD_VERSION = "reward-demo-v1"
DEMO_RECEIVER = "demo-rewards"
CURRENT = """SELECT v.* FROM c_rewards r JOIN c_reward_versions v
             ON v.reward_id=r.reward_id AND v.reward_version=r.current_version"""


class Reward(Input):
    reward_id: ID
    reward_version: ID
    name: Short
    description: Text
    points_cost: Literal[30, 40, 50, 60, 80]
    kind: Literal["digital_content", "service_appointment"]
    availability: Literal["available", "unavailable", "unknown"]
    resource_id: ID | None
    is_essential: Literal[False] = False
    is_simulated: Literal[True] = True


class RewardFixture(Input):
    reward: Reward
    previous_version: ID | None = None
    template_text: Text | None = None
    resource_version: ID | None = None

    @model_validator(mode="after")
    def delivery(self):
        digital = self.reward.kind == "digital_content"
        if (
            "模拟" not in self.reward.name
            or digital != (self.template_text is not None)
            or digital
            != (self.reward.resource_id is None and self.resource_version is None)
            or not digital
            and not (self.reward.resource_id and self.resource_version)
        ):
            raise ValueError(
                "a mock digital template or a precise personnel resource is required"
            )
        return self


def install_rewards(conn, fixtures, at):
    added = 0
    for fixture in fixtures:
        reward = fixture.reward
        if reward.resource_id is not None:
            resource = load_resource(conn, reward.resource_id, fixture.resource_version)
            if (
                not resource
                or resource["access_mode"] != "reward_only"
                or resource["is_essential"]
            ):
                raise AppError(
                    409,
                    "REWARD_VERSION_CONFLICT",
                    "人员权益必须绑定确切的额外支持资源版本",
                )
        key = (reward.reward_id, reward.reward_version)
        value = (
            fixture.previous_version,
            encode(reward.model_dump()),
            fixture.template_text,
            fixture.resource_version,
        )
        old = conn.execute(
            """SELECT previous_version,reward_json,template_text,resource_version
                              FROM c_reward_versions WHERE reward_id=? AND reward_version=?""",
            key,
        ).fetchone()
        if old is not None:
            if tuple(old) != value:
                raise AppError(
                    409, "REWARD_VERSION_CONFLICT", "该权益版本已登记不同内容"
                )
            continue
        current = conn.execute(
            "SELECT current_version FROM c_rewards WHERE reward_id=?", key[:1]
        ).fetchone()
        if (current[0] if current else None) != fixture.previous_version:
            raise AppError(409, "REWARD_VERSION_CONFLICT", "权益当前版本已变化")
        conn.execute(
            "INSERT INTO c_reward_versions VALUES (?,?,?,?,?,?,?)",
            (*key, value[0], at, *value[1:]),
        )
        conn.execute(
            """INSERT INTO c_rewards VALUES (?,?) ON CONFLICT(reward_id)
                        DO UPDATE SET current_version=excluded.current_version""",
            key,
        )
        added += 1
    return added


def seed_rewards(db, clock=now):
    status(db)
    at = stamp(clock())
    resources = ResourceFixture.model_validate(
        {
            "resource": {
                "resource_id": RESOURCE,
                "resource_version": RESOURCE_VERSION,
                "service_kind": "emotional_companionship",
                "name": "额外志愿陪伴（模拟）",
                "description": "自愿的虚构陪伴预约，仅用于演示。",
                "provider": {
                    "provider_id": "provider-companionship-demo",
                    "provider_type": "volunteer",
                    "display_name": "虚构社区志愿资源（模拟）",
                    "qualification_status": "not_required",
                    "is_simulated": True,
                },
                "availability": "available",
                "access_mode": "reward_only",
                "is_essential": False,
                "required_shared_categories": ["support_question"],
                "optional_shared_categories": [],
                "peer_group_id": None,
                "is_simulated": True,
            },
            "previous_version": None,
            "profile_types": [],
        }
    )
    entries = [
        (
            "reminder",
            30,
            "提醒定制",
            "记录自己常用的提醒方式和偏好。",
            "提醒方式：____\n方便查看的时段：____",
        ),
        (
            "card",
            40,
            "管理卡",
            "整理已有计划的核对事项。",
            "本周准备事项：____\n需要向专业人员核对的问题：____",
        ),
        (
            "routine",
            50,
            "作息清单",
            "按本人作息整理一般管理事项。",
            "我的早间安排：____\n我的晚间安排：____",
        ),
        ("companion", 60, "额外志愿陪伴", "需本人确认服务草稿和共享范围。", None),
        (
            "toolkit",
            80,
            "工具包",
            "提供可保存的管理记录与复盘文本。",
            "本周记录：____\n遇到的问题：____\n下周待核对事项：____",
        ),
    ]
    fixtures = [
        RewardFixture.model_validate(
            {
                "reward": {
                    "reward_id": "reward-" + key + "-demo",
                    "reward_version": REWARD_VERSION,
                    "name": name + "（模拟）",
                    "description": description,
                    "points_cost": cost,
                    "kind": "service_appointment"
                    if template is None
                    else "digital_content",
                    "availability": "available",
                    "resource_id": RESOURCE if template is None else None,
                },
                "template_text": (
                    template + "\n请以已有正式用药安排及专业人员指导为准。"
                    if template
                    else None
                ),
                "resource_version": RESOURCE_VERSION if template is None else None,
            }
        )
        for key, cost, name, description, template in entries
    ]
    with db.transaction() as conn:
        install_catalog(conn, [resources], at)
        install_demo_recipients(
            conn,
            [
                {
                    "resource_id": RESOURCE,
                    "resource_version": RESOURCE_VERSION,
                    "recipient_id": "provider-companionship-demo",
                    "recipient_type": "volunteer",
                    "purpose_code": "emotional_companionship",
                }
            ],
        )
        return install_rewards(conn, fixtures, at)


def reward_view(conn, row):
    data = json.loads(row["reward_json"])
    if data["resource_id"] is not None:
        from ..catalog.service import current_resource

        resource = current_resource(
            conn,
            {
                "resource_id": data["resource_id"],
                "resource_version": row["resource_version"],
            },
        )
        if (
            resource is None
            or resource["access_mode"] != "reward_only"
            or not SharingAuthority.registered(conn, resource)
        ) and data["availability"] == "available":
            data["availability"] = "unknown"
    return data
