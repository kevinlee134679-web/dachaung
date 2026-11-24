import json
import os
import unittest
from itertools import product
from pathlib import Path
from unittest.mock import Mock

from fixtures import PA, IdentityFixture, unknown_answers
from medplatform.core.errors import AppError
from medplatform.profile import cas_review, mapped_review, retrained
from medplatform.web.app import create_app


class MappedReviewTests(IdentityFixture):
    def submit(
        self, answers, version=mapped_review.VERSION, same_episode=True, actor=None
    ):
        actor = actor or self.a
        response = self.call(
            actor,
            "POST",
            f"/patients/{PA}/questionnaire-responses",
            {"questionnaire_version": version},
            expected=201,
        )
        path = "/questionnaire-responses/" + response["response_id"]
        self.call(
            actor,
            "PUT",
            path + "/answers",
            {"expected_revision": 1, "answers": answers},
        )
        self.call(
            actor,
            "POST",
            path + "/submit",
            {"expected_revision": 2, "confirmed": True, "same_episode": same_episode},
        )
        return {"response_id": response["response_id"]}

    def generate(self, body):
        return self.call(self.a, "POST", f"/patients/{PA}/profiles", body, expected=201)

    def answers(self, fixture):
        target, pattern = fixture["cas_observed"], fixture["reported_pattern"]
        answers = unknown_answers()
        frequency = (
            5 if pattern == "none_reported" or target == 15 else 1 if target == 3 else 3
        )
        label = next(k for k, v in cas_review.FREQUENCY.items() if v == frequency)
        knowledge, difficulty = next(
            (k, d)
            for k, d in product(range(1, 6), repeat=2)
            if target is None or k + frequency + 6 - d == target
        )
        for q, value in [
            ("Q1", {"knowledge": knowledge}),
            ("Q2", {"adherence_freq": label}),
            (
                "Q4",
                {
                    k: fixture[k]
                    for k in ("reported_pattern", "barriers", "main_barrier")
                },
            ),
        ]:
            answers[q] = {"state": "answered", "value": value}
        if target is not None:
            answers["Q3"] = {"state": "answered", "value": {"difficulty": difficulty}}
        return answers

    def test_all_supplied_fixtures_through_o16_to_o22(self):
        cases = mapped_review.PROFILE["fictional_boundary_fixtures"]
        self.assertEqual(len(cases), 17)
        for number, fixture in enumerate(cases, 1):
            with self.subTest(number=number):
                body = self.submit(self.answers(fixture))
                result = self.generate(body)
                demo = result["demo_classification"]
                self.assertEqual(
                    result["cas_observed"]["value"], fixture["cas_observed"]
                )
                self.assertEqual(demo["primary_type"], fixture["primary_type"])
                self.assertEqual(
                    demo["reported_matching_types"], fixture["reported_matching_types"]
                )
                self.assertEqual(demo["needs_review"], number == 14)
                self.assertEqual(result["questionnaire_version"], mapped_review.VERSION)
                self.assertEqual(
                    result["input_mapping_version"], mapped_review.INPUT_MAPPING
                )
                self.assertIsNone(result["primary_type"])
                self.assertEqual(result["additional_types"], [])
                self.assertEqual(result["cas"]["status"], "unavailable")
                self.assertIsNone(result["cas_predicted"]["value"])
                if number == 8:
                    self.assertEqual(
                        demo["entry_codes"], ["reminder", "ai_support", "knowledge"]
                    )
                    self.assertEqual(result, self.generate(body))

    def test_old_versions_and_authorship(self):
        fixture = mapped_review.PROFILE["fictional_boundary_fixtures"][0]
        answers = self.answers(fixture)
        self.bind(["questionnaire:assist", "profile:read"])
        assisted = self.submit(answers, actor=self.f)
        self.call(self.f, "POST", f"/patients/{PA}/profiles", assisted, expected=403)
        p = self.generate(assisted)
        self.assertIsNone(p["demo_classification"]["primary_type"])
        self.assertEqual(p["demo_classification"]["reported_matching_types"], [])
        self.assertIsNone(
            self.generate(self.submit(answers, same_episode=False))["cas_observed"][
                "value"
            ]
        )
        self.call(self.b, "GET", f"/profiles/{p['profile_id']}", expected=404)
        defs = [
            self.call(self.a, "GET", "/questionnaires/initial?version=" + v)
            for v in ("initial-v0.1", cas_review.VERSION, mapped_review.VERSION)
        ]
        self.assertEqual(defs[-1], self.call(self.a, "GET", "/questionnaires/initial"))
        self.assertEqual(defs[1]["themes"][3]["fields"][0]["key"], "behavior")
        current = defs[-1]["themes"]
        self.assertEqual(
            [f["key"] for f in current[3]["fields"]],
            ["reported_pattern", "barriers", "main_barrier"],
        )
        self.assertEqual(current[5]["fields"][0]["options"][0]["label"], "非常不同意")
        answers["Q4"] = {"state": "answered", "value": {"behavior": "unintentional"}}
        old = self.generate(self.submit(answers, cas_review.VERSION))
        self.assertNotIn("demo_classification", old)
        self.generate(self.submit(self.answers(fixture)))
        self.assertEqual(
            self.call(self.a, "GET", f"/profiles/{old['profile_id']}"), old
        )

    def test_profile_for_latest_submission_ignores_drafts_and_older_profiles(self):
        cases = mapped_review.PROFILE["fictional_boundary_fixtures"]
        path = f"/patients/{PA}/profiles/current?source=latest_submission"
        self.call(self.a, "GET", path, expected=404)
        old = self.generate(self.submit(self.answers(cases[0])))
        self.assertEqual(self.call(self.a, "GET", path)["profile"], old)
        submitted = self.submit(self.answers(cases[12]))
        self.call(
            self.a,
            "POST",
            f"/patients/{PA}/questionnaire-responses",
            {"questionnaire_version": mapped_review.VERSION},
            expected=201,
        )
        latest = self.call(self.a, "GET", path)
        self.assertEqual(latest["response_id"], submitted["response_id"])
        self.assertIsNone(latest["profile"])
        new = self.generate(submitted)
        self.assertEqual(old["cas_observed"]["value"], 3)
        self.assertEqual(new["cas_observed"]["value"], 15)
        self.assertEqual(self.call(self.a, "GET", path)["profile"], new)
        self.assertEqual(self.generate(submitted), new)
        self.assertEqual(
            self.call(self.a, "GET", "/profiles/" + old["profile_id"]), old
        )
        self.call(self.b, "GET", path, expected=404)
        self.bind(["profile:read"])
        self.call(self.f, "GET", path, expected=403)
        self.assertEqual(
            self.call(self.f, "GET", f"/patients/{PA}/profiles/current"), new
        )

    def test_invalid_and_optional_fields(self):
        draft = self.call(
            self.a,
            "POST",
            f"/patients/{PA}/questionnaire-responses",
            {"questionnaire_version": mapped_review.VERSION},
            expected=201,
        )
        path = f"/questionnaire-responses/{draft['response_id']}/answers"
        base = self.answers(mapped_review.PROFILE["fictional_boundary_fixtures"][0])
        for q, value in [
            (
                "Q4",
                {
                    "reported_pattern": "both",
                    "barriers": ["other"],
                    "main_barrier": "execution_or_access",
                },
            ),
            ("Q4", {"reported_pattern": "both", "barriers": ["invalid"]}),
            ("Q4", {"reported_pattern": "both", "barriers": ["other", "other"]}),
            (
                "Q4",
                {"reported_pattern": "both", "barriers": ["other"], "main_barrier": []},
            ),
            ("Q5", {"special_requirements": ["req_none", "req_inject"]}),
        ]:
            answers = {**base, q: {"state": "answered", "value": value}}
            self.call(
                self.a,
                "PUT",
                path,
                {"expected_revision": 1, "answers": answers},
                expected=422,
            )
        base["Q1"] = {"state": "prefer_not_to_answer", "value": None}
        base["Q5"] = {
            "state": "answered",
            "value": {"special_requirements": ["req_none"]},
        }
        base["Q8"] = {"state": "answered", "value": {"stable_experience": "否"}}
        self.assertIsNone(self.generate(self.submit(base))["cas_observed"]["value"])

    def test_model_switch_and_insufficient_input(self):
        answers = self.answers(mapped_review.PROFILE["fictional_boundary_fixtures"][7])
        response = self.submit(answers)
        off = self.generate(response)
        predictor = retrained.Predictor({}, None, None)
        self.app.state.identity.cas_predictor = predictor
        on = self.generate(response)
        self.assertEqual(on["cas"]["status"], "insufficient")
        self.assertIn("Q8", on["cas"]["reason"])
        self.assertIsNone(on["cas"]["value"])
        self.assertEqual(on["cas"]["model_version"], retrained.MODEL)
        self.assertEqual(on["cas"]["preprocessing_version"], retrained.PREPROCESSING)
        self.assertEqual(on["cas"], on["cas_predicted"])
        self.assertNotEqual(off["profile_id"], on["profile_id"])
        self.assertEqual(self.generate(response), on)
        self.assertEqual(
            off, self.call(self.a, "GET", "/profiles/" + off["profile_id"])
        )
        self.assertEqual(off["demo_classification"], on["demo_classification"])
        self.assertEqual(off["cas_observed"], on["cas_observed"])
        answers["Q8"] = {"state": "answered", "value": {"stable_experience": "否"}}
        self.assertIn(
            "稳定用药经历", self.generate(self.submit(answers))["cas"]["reason"]
        )
        self.bind(["questionnaire:assist", "profile:read"])
        assisted = self.generate(self.submit(answers, actor=self.f))
        self.assertEqual(assisted["cas"]["status"], "insufficient")
        self.assertIn("本人", assisted["cas"]["reason"])
        self.app.state.identity.cas_predictor = None
        self.assertEqual(off, self.generate(response))

    def test_prediction_failure_can_be_retried_and_bad_bundle_is_rejected(self):
        with self.assertRaises(AppError) as err:
            retrained.Predictor.load(self.path)
        self.assertEqual(err.exception.code, "CAS_BUNDLE_INVALID")
        response = self.submit(
            self.answers(mapped_review.PROFILE["fictional_boundary_fixtures"][0])
        )
        predictor = Mock()
        self.app.state.identity.cas_predictor = predictor
        metadata = {
            "model_version": retrained.MODEL,
            "preprocessing_version": retrained.PREPROCESSING,
        }
        predictor.assess.side_effect = [
            dict(metadata, status="unavailable", value=None, reason="模型计算失败"),
            dict(metadata, status="estimated", value=10.5, reason=None),
        ]
        failed = self.generate(response)
        retried = self.generate(response)
        self.assertEqual(failed["cas"]["status"], "unavailable")
        self.assertEqual(retried["cas"]["value"], 10.5)
        self.assertEqual(self.generate(response), retried)
        self.assertEqual(predictor.assess.call_count, 2)

    @unittest.skipUnless(os.environ.get("CAS_TEST_BUNDLE"), "需要本机重训验收包")
    def test_retrained_release_through_public_endpoints(self):
        folder = Path(os.environ["CAS_TEST_BUNDLE"])
        settings = self.settings.model_copy(update={"CAS_RETRAINED_BUNDLE": folder})
        app = create_app(settings, clock=self.clock)
        self.a = self.login("demo-patient-a", app=app)
        admin = self.login("demo-admin", app=app)
        caps = self.call(admin, "GET", "/config/status")
        self.assertTrue(
            next(c["available"] for c in caps["capabilities"] if c["code"] == "cas")
        )
        cases = json.loads((folder / "reference_cases.json").read_text("utf-8"))
        for case in cases:
            with self.subTest(case=case["case"]):
                answers = unknown_answers()
                for q in ("Q5", "Q6", "Q7", "Q8"):
                    raw = case["input"]
                    values = {
                        key: raw[
                            {
                                "stable_experience": "stable_use",
                                "special_requirements": "requirements",
                            }.get(key, key)
                        ]
                        for key in mapped_review.FIELDS[q]
                    }
                    answers[q] = {"state": "answered", "value": values}
                response = self.submit(answers, same_episode=False)
                profile = self.generate(response)
                self.assertEqual(profile["cas"]["status"], "estimated")
                self.assertAlmostEqual(
                    profile["cas"]["value"], case["expected_prediction"], delta=1e-5
                )
                self.assertIsNone(profile["cas_observed"]["value"])
                self.assertIsNone(profile["demo_classification"]["primary_type"])
                self.assertEqual(
                    self.call(self.a, "GET", f"/patients/{PA}/profiles/current"),
                    profile,
                )
        del answers["Q8"]["value"]["income"]
        partial = self.generate(self.submit(answers))["cas"]
        self.assertEqual(partial["status"], "insufficient")
        self.assertIn("收入", partial["reason"])
