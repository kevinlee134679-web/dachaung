import json

from .model import Completion

CRISIS_PHRASES = ("想伤害自己", "紧迫危险", "马上伤害", "自杀", "不想活", "结束生命")
CRISIS_REPLY = "听到你这样说，我很担心你的安全。如果你或他人正面临紧迫危险，请立即拨打 120 或 110，或马上联系身边可以信任的人陪着你。"


def crisis_completion(text: str) -> Completion | None:
    if any(phrase in text for phrase in CRISIS_PHRASES):
        return Completion(
            json.dumps(
                {
                    "assistant_reply": CRISIS_REPLY,
                    "support_focus": "action_support",
                    "communication_strategy": ["autonomy_support"],
                },
                ensure_ascii=False,
            )
        )
    return None
