import json
from datetime import UTC, datetime, time, timedelta
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from ..core.config import Settings
from ..core.documents import stamp, uid
from ..dialogue.model import Completion
from ..web.app import create_app
from .client import ScenarioClients

PATIENT = "demo-patient-a-self"
ZONE = ZoneInfo("Asia/Shanghai")

CONVERSATIONS = [
    [
        (
            "这两天吃二甲双胍胃有点不舒服，有点不想吃了。",
            "胃不舒服确实让人难受，会想先停一停也很正常。这种不适一般在什么时候出现？",
        ),
        (
            "多数是早上吃完以后。",
            "谢谢你说得这么具体。要不要调整服药时间，需要医生或药师根据你的情况来定。要不要我帮你把想问的问题列一下？",
        ),
        (
            "好，帮我列一下吧。",
            "可以这样问：1. 二甲双胍随餐或饭后吃会不会好一些？2. 胃不舒服的时候还要继续吃吗？3. 有没有其他减轻不适的办法？在问清楚之前，先别自己停药。",
        ),
    ],
    [
        (
            "昨晚又忘了吃降脂药，总是记不住晚上那一顿。",
            "晚上那一顿容易被别的事打断，很多人都会遇到。你睡前一般会固定做什么事吗？",
        ),
        (
            "一般会刷牙，再看会儿手机。",
            "那可以试试把药盒放在牙刷旁边，刷牙时顺手吃；也可以在“提醒设置”里给 21:00 设一个提醒。你觉得哪个更适合你？",
        ),
    ],
]

ANSWERS = {
    "Q1": {"knowledge": 4},
    "Q2": {"adherence_freq": "偶尔漏服（每周1-2次）"},
    "Q3": {"difficulty": 3},
    "Q4": {
        "reported_pattern": "unintentional",
        "barriers": ["forgot_or_habit_disrupted", "mood_or_treatment_fatigue"],
        "main_barrier": "forgot_or_habit_disrupted",
    },
    "Q5": {
        "drug_duration": "1-3年",
        "drug_count": "2-3种",
        "drug_freq": "2次",
        "special_requirements": ["req_after_meal"],
        "drug_type": "心血管类药物（降压、降脂、抗凝等）",
        "followup": "大部分时候会去",
        "social_support": "单纯口头提醒我用药",
    },
    "Q6": {
        "meal_irregular": 3,
        "life_unstable": 4,
        "side_effect": 3,
        "worry_worsen": 4,
        "fatigue": 4,
        "cost_burden": 2,
        "skip_belief": 3,
        "stop_control": 2,
        "emotion_impact": 3,
        "lose_confidence": 1,
        "public_pressure": 2,
    },
    "Q7": {"self_efficacy": 4, "tech_accept": 5, "health_literacy": 4},
    "Q8": {
        "stable_experience": "是",
        "age": "46-64岁",
        "gender": "男",
        "income": "5000-10000元",
        "living": "与伴侣/家人同住",
    },
}


class ScriptedModel:
    mode = "mock"
    provider_label = model_label = "demo-script"

    def __init__(self):
        self.replies = iter(
            (reply, index == len(conversation) - 1)
            for conversation in CONVERSATIONS
            for index, (_, reply) in enumerate(conversation)
        )

    def complete(self, messages, *, scenario=None):
        reply, last = next(self.replies)
        return Completion(
            json.dumps(
                {
                    "assistant_reply": reply,
                    "support_focus": "action_support" if last else "exploring",
                    "communication_strategy": [
                        "permission_based_advice" if last else "reflection"
                    ],
                },
                ensure_ascii=False,
            )
        )


def seed_story(db):
    current = datetime.now(UTC)
    start = current.astimezone(ZONE).date() - timedelta(days=14)
    clock = [datetime.combine(start, time(7, 30), ZONE)]
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_PATH=db.path),
        clock=lambda: clock[0],
    )
    with ScenarioClients(app, "Story login failed", "Story API failed: ") as clients:
        call = clients.call
        client = clients.login("demo-patient-a")
        if call(client, "GET", f"/patients/{PATIENT}/plans")["items"]:
            return

        entries = []
        medications = {}
        for name, notes, dose, unit, times, meal in (
            ("氨氯地平片", "降压", "5", "mg", ["08:00"], None),
            ("二甲双胍片", "降糖，饭后服", "0.5", "g", ["08:00", "20:00"], "饭后"),
            ("阿托伐他汀钙片", "降脂，睡前服", "20", "mg", ["21:00"], None),
        ):
            med = call(
                client,
                "POST",
                f"/patients/{PATIENT}/medications",
                {"name": name, "notes": notes},
            )
            medications[name] = med["medication_id"]
            entries.append(
                {
                    "draft_entry_id": uid(),
                    "medication_id": med["medication_id"],
                    "dose_value": dose,
                    "dose_unit": unit,
                    "start_date": str(start),
                    "end_date": None,
                    "schedule": {"kind": "daily", "times": times, "weekdays": []},
                    "meal_requirement": meal,
                    "medical_notes": None,
                    "strict_timing": False,
                    "min_interval_minutes": None,
                    "source_file_ids": [],
                }
            )
        draft = call(
            client,
            "POST",
            f"/patients/{PATIENT}/drafts",
            {"entries": entries, "source_file_ids": []},
        )
        draft = call(
            client,
            "POST",
            f"/drafts/{draft['draft_id']}/submit",
            {
                "expected_revision": draft["meta"]["revision"],
                "content_revision": draft["content_revision"],
            },
        )
        call(
            client,
            "POST",
            f"/patients/{PATIENT}/plan-confirmations",
            {
                "draft_id": draft["draft_id"],
                "draft_revision": draft["content_revision"],
                "existing_plan_id": None,
                "expected_plan_version": None,
                "effective_from": stamp(clock[0]),
                "confirmed": True,
            },
        )

        window_start = stamp(clock[0])
        window_end = stamp(current)
        app.state.execution.maintenance(None, PATIENT, window_start, window_end)
        slots = call(
            client,
            "GET",
            f"/patients/{PATIENT}/dose-slots?"
            + urlencode(
                {"window_start": window_start, "window_end": window_end, "limit": 100}
            ),
        )["items"]
        for slot in slots:
            scheduled = datetime.fromisoformat(slot["scheduled_at"]).astimezone(ZONE)
            day = (scheduled.date() - start).days + 1
            hour = scheduled.strftime("%H:%M")
            medication = slot["medication_id"]
            if day == 13 and hour == "21:00":
                continue
            status, reason, text = "taken", None, None
            if medication == medications["二甲双胍片"] and (day, hour) == (3, "20:00"):
                status, reason = "not_taken", "forgot"
            elif medication == medications["阿托伐他汀钙片"] and (day, hour) == (
                6,
                "21:00",
            ):
                status, reason, text = (
                    "not_taken",
                    "not_with_me",
                    "晚上在外面吃饭，药没带",
                )
            elif medication == medications["二甲双胍片"] and (day, hour) == (
                9,
                "08:00",
            ):
                status = "unknown"
            elif medication == medications["二甲双胍片"] and (day, hour) == (
                11,
                "20:00",
            ):
                status, reason, text = (
                    "not_taken",
                    "unwell_or_side_effects",
                    "胃有点不舒服",
                )
            clock[0] = scheduled + timedelta(minutes=10)
            # demo logins expire after 8 hours of clock time
            client = clients.login("demo-patient-a")
            call(
                client,
                "POST",
                f"/patients/{PATIENT}/medication-events",
                {
                    "source_event_id": uid(),
                    "occurred_at": stamp(clock[0]),
                    "reported_status": status,
                    "missed_reason": reason,
                    "raw_text": text,
                    "dose_slot_id": slot["dose_slot_id"],
                    "medication_id": medication,
                    "plan_ref": {
                        "plan_id": slot["plan_id"],
                        "plan_version": slot["plan_version"],
                    },
                },
            )

        app.state.dialogue.dialogue.adapter = ScriptedModel()
        for offset, at, conversation in (
            (10, time(21), CONVERSATIONS[0]),
            (13, time(8, 30), CONVERSATIONS[1]),
        ):
            clock[0] = datetime.combine(start + timedelta(days=offset), at, ZONE)
            client = clients.login("demo-patient-a")
            session = call(
                client,
                "POST",
                "/sessions",
                {"patient_id": PATIENT, "entry_source": "user"},
            )
            for turn, (message, _) in enumerate(conversation):
                call(
                    client,
                    "POST",
                    f"/sessions/{session['session_id']}/messages",
                    {
                        "client_message_id": uid(),
                        "content": message,
                        "expected_turn_count": turn,
                    },
                )

        clock[0] = current
        client = clients.login("demo-patient-a")
        response = call(
            client, "POST", f"/patients/{PATIENT}/questionnaire-responses", {}
        )
        path = f"/questionnaire-responses/{response['response_id']}"
        for question, answer in ANSWERS.items():
            response = call(
                client,
                "PUT",
                path + "/answers",
                {
                    "expected_revision": response["meta"]["revision"],
                    "answers": {question: answer},
                },
            )
        call(
            client,
            "POST",
            path + "/submit",
            {
                "expected_revision": response["meta"]["revision"],
                "confirmed": True,
                "same_episode": True,
            },
        )
        call(
            client,
            "POST",
            f"/patients/{PATIENT}/profiles",
            {"response_id": response["response_id"]},
        )
