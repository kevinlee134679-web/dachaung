"""Session-bound logout receipts and independently granted questionnaire reads.

All state is generated in the original fixture's isolated TemporaryDirectory.
Import the fixture module, not its TestCase class, to avoid duplicate discovery.
"""

import json
import unittest

import fixtures
from medplatform.core.documents import digest, fingerprint


class AuthRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.IdentityFixture()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def logout(self, client, token, operation):
        return client.post(
            "/api/v1/auth/logout",
            json={},
            headers={
                "Cookie": "session=" + token,
                "Origin": fixtures.BASE,
                "X-CSRF-Token": client.csrf,
                "Idempotency-Key": operation,
            },
        )

    def assert_token_invalid(self, client, token):
        response = client.get("/api/v1/auth/me", headers={"Cookie": "session=" + token})
        self.assertEqual(response.status_code, 401, response.text)

    def make_legacy_logout(self, client, token, operation):
        """Turn a generated receipt into the exact pre-fix unbound layout.

        The old ordinary response/audit has no session identity; its account,
        empty path and timestamp cannot prove which session owns the receipt.
        No old application database or tracked evidence is changed here.
        """
        response = self.logout(client, token, operation)
        self.assertEqual(response.status_code, 200, response.text)
        legacy_scope = fingerprint(
            [
                "demo",
                "account",
                "demo-patient-a",
                "__none__",
                "logout",
                {},
            ]
        )
        with self.fixture.db.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM idempotency_receipts WHERE key_hash=?",
                (digest(operation),),
            ).fetchone()
            self.assertIsNotNone(row)
            body = json.loads(
                conn.execute(
                    "SELECT response_json FROM receipt_responses WHERE response_ref=?",
                    (row["response_ref"],),
                ).fetchone()[0]
            )
            body["resource_type"] = None
            body["resource_id"] = None
            conn.execute(
                "UPDATE receipt_responses SET response_json=? WHERE response_ref=?",
                (json.dumps(body), row["response_ref"]),
            )
            conn.execute(
                "UPDATE idempotency_receipts SET scope_hash=?,resource_type=NULL,resource_id=NULL WHERE receipt_id=?",
                (legacy_scope, row["receipt_id"]),
            )
            saved = dict(
                conn.execute(
                    "SELECT * FROM idempotency_receipts WHERE receipt_id=?",
                    (row["receipt_id"],),
                ).fetchone()
            )
        return saved

    def test_same_account_same_key_logs_out_each_session_and_replays_only_its_own_result(
        self,
    ):
        first = self.fixture.a
        second = self.fixture.login("demo-patient-a")
        first_token = first.cookies.get("session")
        second_token = second.cookies.get("session")
        operation = fixtures.key()

        one = self.logout(first, first_token, operation)
        two = self.logout(second, second_token, operation)
        self.assertEqual(one.status_code, 200, one.text)
        self.assertEqual(two.status_code, 200, two.text)
        self.assertNotEqual(
            one.json()["data"]["operation_id"], two.json()["data"]["operation_id"]
        )
        self.assert_token_invalid(first, first_token)
        self.assert_token_invalid(second, second_token)

        replay_one = self.logout(first, first_token, operation)
        replay_two = self.logout(second, second_token, operation)
        self.assertEqual(replay_one.status_code, 200, replay_one.text)
        self.assertEqual(replay_two.status_code, 200, replay_two.text)
        self.assertEqual(replay_one.json()["data"], one.json()["data"])
        self.assertEqual(replay_two.json()["data"], two.json()["data"])
        self.assert_token_invalid(first, first_token)
        self.assert_token_invalid(second, second_token)

    def test_unbound_legacy_receipt_is_preserved_and_cannot_replace_an_active_session_logout(
        self,
    ):
        first = self.fixture.a
        first_token = first.cookies.get("session")
        operation = fixtures.key()
        saved = self.make_legacy_logout(first, first_token, operation)

        # No session binding exists in this historical receipt. Even its former
        # credential cannot be matched by guessing from account/timestamp.
        refused = self.logout(first, first_token, operation)
        self.assertEqual(refused.status_code, 401, refused.text)
        self.assert_token_invalid(first, first_token)
        with self.fixture.db.connection(readonly=True) as conn:
            retained = dict(
                conn.execute(
                    "SELECT * FROM idempotency_receipts WHERE receipt_id=?",
                    (saved["receipt_id"],),
                ).fetchone()
            )
        self.assertEqual(saved, retained)

        second = self.fixture.login("demo-patient-a")
        second_token = second.cookies.get("session")
        own_result = self.logout(second, second_token, operation)
        self.assertEqual(own_result.status_code, 200, own_result.text)
        self.assert_token_invalid(second, second_token)
        with self.fixture.db.connection(readonly=True) as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) FROM idempotency_receipts WHERE key_hash=?",
                    (digest(operation),),
                ).fetchone()[0],
                2,
            )

    def test_same_time_legacy_sessions_are_not_associated_by_account_and_timestamp(
        self,
    ):
        first = self.fixture.a
        second = self.fixture.login("demo-patient-a")
        first_token = first.cookies.get("session")
        second_token = second.cookies.get("session")
        first_key, second_key = fixtures.key(), fixtures.key()
        one = self.make_legacy_logout(first, first_token, first_key)
        two = self.make_legacy_logout(second, second_token, second_key)
        self.assertEqual(one["completed_at"], two["completed_at"])
        with self.fixture.db.connection(readonly=True) as conn:
            rows = conn.execute(
                "SELECT revoked_at FROM o_sessions WHERE account_id=? AND revoked_at IS NOT NULL",
                ("demo-patient-a",),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["revoked_at"], rows[1]["revoked_at"])
        for client, token, operation in (
            (first, first_token, first_key),
            (first, first_token, second_key),
            (second, second_token, first_key),
            (second, second_token, second_key),
        ):
            response = self.logout(client, token, operation)
            self.assertEqual(response.status_code, 401, response.text)
            self.assert_token_invalid(client, token)

    def replace_with_read(self, binding, revision=1):
        return self.fixture.call(
            self.fixture.a,
            "PUT",
            f"/family-bindings/{binding['binding_id']}/grant",
            {
                "expected_revision": revision,
                "scopes": ["questionnaire:read"],
                "valid_until": None,
                "confirmed": True,
            },
        )

    def test_author_can_read_own_draft_after_assist_revoked_but_read_retained(self):
        binding, _ = self.fixture.bind(["questionnaire:assist"])
        response = self.fixture.response(self.fixture.f, patient=fixtures.PA)
        self.replace_with_read(binding)
        read = self.fixture.call(
            self.fixture.f,
            "GET",
            f"/questionnaire-responses/{response['response_id']}",
        )
        self.assertEqual(read, response)
        self.fixture.call(
            self.fixture.f,
            "PUT",
            f"/questionnaire-responses/{response['response_id']}/answers",
            {
                "expected_revision": response["meta"]["revision"],
                "answers": fixtures.unknown_answers(),
            },
            expected=403,
        )

    def test_author_can_read_own_submitted_response_with_read_only_grant(self):
        binding, _ = self.fixture.bind(["questionnaire:assist"])
        response = self.fixture.response(
            self.fixture.f, patient=fixtures.PA, answers=fixtures.unknown_answers()
        )
        submitted = self.fixture.call(
            self.fixture.f,
            "POST",
            f"/questionnaire-responses/{response['response_id']}/submit",
            {"expected_revision": response["meta"]["revision"], "confirmed": True},
        )
        self.replace_with_read(binding)
        actual = self.fixture.call(
            self.fixture.f,
            "GET",
            f"/questionnaire-responses/{response['response_id']}",
        )
        self.assertEqual(actual, submitted)

    def test_assist_only_draft_exception_does_not_grant_other_author_or_submitted_reads(
        self,
    ):
        self.fixture.bind(["questionnaire:assist"])
        own_draft = self.fixture.response(
            self.fixture.f, patient=fixtures.PA, answers=fixtures.unknown_answers()
        )
        self.assertEqual(
            self.fixture.call(
                self.fixture.f,
                "GET",
                f"/questionnaire-responses/{own_draft['response_id']}",
            ),
            own_draft,
        )
        patients_draft = self.fixture.response(self.fixture.a, patient=fixtures.PA)
        self.fixture.call(
            self.fixture.f,
            "GET",
            f"/questionnaire-responses/{patients_draft['response_id']}",
            expected=403,
        )
        error = self.fixture.call(
            self.fixture.f,
            "PUT",
            f"/questionnaire-responses/{patients_draft['response_id']}/answers",
            {"expected_revision": 1, "answers": fixtures.unknown_answers()},
            expected=403,
        )
        self.assertEqual(error["code"], "RESPONSE_AUTHOR_REQUIRED")
        self.fixture.call(
            self.fixture.f,
            "POST",
            f"/questionnaire-responses/{own_draft['response_id']}/submit",
            {"expected_revision": own_draft["meta"]["revision"], "confirmed": True},
        )
        self.fixture.call(
            self.fixture.f,
            "GET",
            f"/questionnaire-responses/{own_draft['response_id']}",
            expected=403,
        )
