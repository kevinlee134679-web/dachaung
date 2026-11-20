import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from httpx2 import Response

from medplatform.core.config import ROOT, Settings
from medplatform.core.database import Database
from medplatform.core.documents import stamp
from medplatform.core.migrations import migrate
from medplatform.demo.client import SessionClient
from medplatform.identity.service import seed_demo
from medplatform.web.app import create_app

BASE = "http://127.0.0.1:8000"
PA = "demo-patient-a-self"
PB = "demo-patient-b-self"


class Client(SessionClient):
    login_response: Response


def key():
    return str(uuid.uuid4())


def unknown_answers():
    return {f"Q{i}": {"state": "unknown", "value": None} for i in range(1, 9)}


def defaults():
    return {
        "enabled": False,
        "channels": ["in_app"],
        "sound_enabled": False,
        "vibration_enabled": False,
        "routine_mode": "regular",
        "anchors": [],
        "privacy_enabled": False,
        "custom_text": None,
        "privacy_windows": [],
        "repeat_interval_minutes": None,
        "max_repeats": 0,
        "snooze_minutes": None,
        "notify_family": False,
    }


class IdentityFixture(unittest.TestCase):
    def setUp(self):
        (ROOT / "test-output").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "test-output")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.db = Database(self.path / "demo.sqlite3")
        migrate(self.db, initialize=True)
        self.time = [datetime(2026, 11, 16, 10, tzinfo=UTC)]
        self.clock = lambda: self.time[0]
        seed_demo(self.db, self.clock)
        self.settings = Settings(
            _env_file=None, APP_ENV="test", DATABASE_PATH=self.db.path
        )
        self.app = create_app(self.settings, clock=self.clock)
        self.clients = []
        self.a = self.login("demo-patient-a")
        self.b = self.login("demo-patient-b")
        self.f = self.login("demo-family")

    def login(self, account, app=None, operation=None):
        c = Client(app or self.app, base_url=BASE, raise_server_exceptions=False)
        self.clients.append(c)
        self.addCleanup(c.close)
        r = c.post(
            "/api/v1/auth/demo-session",
            json={"demo_account_id": account},
            headers={"Origin": BASE, "Idempotency-Key": operation or key()},
        )
        self.assertEqual(r.status_code, 201, r.text)
        c.csrf = r.json()["data"]["csrf_token"]
        c.login_response = r
        return c

    def call(
        self, c, method, path, body=None, *, operation=None, expected=200, **kwargs
    ):
        headers = {
            "Origin": BASE,
            "X-CSRF-Token": c.csrf,
            "Idempotency-Key": operation or key(),
        }
        r = c.request(method, "/api/v1" + path, json=body, headers=headers, **kwargs)
        self.assertEqual(r.status_code, expected, r.text)
        data = r.json()
        self.assertEqual(set(data), {"request_id", "status", "data", "error"})
        self.assertEqual(data["request_id"], r.headers["X-Request-ID"])
        return data["data"] if expected < 400 else data["error"]

    def bind(self, scopes):
        code = self.call(
            self.a, "POST", f"/patients/{PA}/family-binding-codes", {}, expected=201
        )
        binding = self.call(
            self.f,
            "POST",
            "/family-bindings/redeem",
            {"binding_code": code["binding_code"]},
            expected=201,
        )
        grant = self.call(
            self.a,
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": 0,
                "scopes": scopes,
                "valid_until": None,
                "confirmed": True,
            },
        )
        return binding, grant

    def response(self, c=None, patient=PA, answers=None):
        c = c or self.a
        result = self.call(
            c,
            "POST",
            f"/patients/{patient}/questionnaire-responses",
            {"questionnaire_version": "initial-v0.1"},
            expected=201,
        )
        rid = result["response_id"]
        if answers is not None:
            result = self.call(
                c,
                "PUT",
                f"/questionnaire-responses/{rid}/answers",
                {"expected_revision": 1, "answers": answers},
            )
        return result

    def submitted(self, answers=None):
        response = self.response(answers=answers or unknown_answers())
        return self.call(
            self.a,
            "POST",
            f"/questionnaire-responses/{response['response_id']}/submit",
            {"expected_revision": response["meta"]["revision"], "confirmed": True},
        )

    def medication(self):
        return self.call(
            self.a,
            "POST",
            f"/patients/{PA}/medications",
            {"name": "虚构药品资料（非医疗指令）"},
            expected=201,
        )

    def draft(self, *, count=1, schedule=None, files=None):
        entries = []
        for i in range(count):
            med = self.medication()
            entries.append(
                {
                    "draft_entry_id": key(),
                    "medication_id": med["medication_id"],
                    "dose_value": "1.00",
                    "dose_unit": "虚构单位",
                    "start_date": "2026-11-16",
                    "end_date": None,
                    "schedule": schedule
                    or {"kind": "daily", "times": ["08:00", "20:00"], "weekdays": []},
                    "meal_requirement": None,
                    "medical_notes": "虚构资料，不用于服药",
                    "strict_timing": None,
                    "min_interval_minutes": None,
                    "source_file_ids": files or [],
                }
            )
        return self.call(
            self.a,
            "POST",
            f"/patients/{PA}/drafts",
            {"entries": entries, "source_file_ids": files or []},
            expected=201,
        )

    def pending(self, draft=None):
        draft = draft or self.draft()
        return self.call(
            self.a,
            "POST",
            f"/drafts/{draft['draft_id']}/submit",
            {
                "expected_revision": draft["meta"]["revision"],
                "content_revision": draft["content_revision"],
            },
        )

    def confirm(self, draft=None, **changes):
        draft = draft or self.pending()
        body = {
            "draft_id": draft["draft_id"],
            "draft_revision": draft["content_revision"],
            "existing_plan_id": None,
            "expected_plan_version": None,
            "effective_from": stamp(self.clock() + timedelta(hours=1)),
            "confirmed": True,
        }
        body.update(changes)
        return self.call(
            self.a, "POST", f"/patients/{PA}/plan-confirmations", body, expected=201
        )

    def upload(
        self,
        c=None,
        patient=PA,
        source=None,
        raw=b"%PDF-1.4\n% Fictional test only\n%%EOF\n",
        filename="fictional.pdf",
        operation=None,
    ):
        c = c or self.a
        return c.post(
            f"/api/v1/patients/{patient}/files",
            data={"source_event_id": source or key()},
            files={"file": (filename, raw, "application/pdf")},
            headers={
                "Origin": BASE,
                "X-CSRF-Token": c.csrf,
                "Idempotency-Key": operation or key(),
            },
        )
