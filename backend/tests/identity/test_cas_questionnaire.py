import json
import unittest
from datetime import timedelta
from pathlib import Path

from fixtures import PA, IdentityFixture
from medplatform.profile import cas_questionnaire as cas


def response_values(values, *, mode="self", same_episode=True):
    return {
        "respondent_mode": mode,
        "same_episode": same_episode,
        "answers": {f"Q{i}": {"value": values.get(f"Q{i}", {})} for i in range(1, 9)},
    }


class QuestionnaireUnitTests(unittest.TestCase):
    def test_scores(self):
        for knowledge, frequency, difficulty, expected in (
            (5, "从不漏服", 1, 15),
            (3, "偶尔漏服（每周1-2次）", 3, 9),
            (1, "极度随性（想起来才吃，经常连续几天不吃）", 5, 3),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(cas.score(knowledge, frequency, difficulty), expected)

    def test_observed_requires_complete_self_report_of_same_episode(self):
        values = {
            "Q1": {"knowledge": 5},
            "Q2": {"adherence_freq": "从不漏服"},
            "Q3": {"difficulty": 1},
        }
        for q3, mode, episode, missing in (
            ({}, "self", True, ["Q3"]),
            ({"difficulty": "unknown"}, "self", True, ["Q3"]),
            ({"difficulty": 1}, "self", False, []),
            ({"difficulty": 1}, "family_assisted", True, []),
        ):
            with self.subTest(q3=q3, mode=mode, episode=episode):
                result = cas.observed_result(
                    response_values(
                        {**values, "Q3": q3}, mode=mode, same_episode=episode
                    )
                )
                self.assertEqual(result["status"], "insufficient")
                self.assertEqual(result["missing_items"], missing)

    def test_cards_show_levels_and_prioritize_main_barrier(self):
        values = {
            "Q1": {"knowledge": 5},
            "Q2": {"adherence_freq": "偶尔漏服（每周1-2次）"},
            "Q3": {"difficulty": 5},
            "Q4": {
                "reported_pattern": "both",
                "barriers": ["forgot_or_habit_disrupted", "execution_or_access"],
                "main_barrier": "execution_or_access",
            },
            "Q6": {"meal_irregular": 4},
            "Q7": {"self_efficacy": 4},
        }
        cards = cas.cards(response_values(values)["answers"])
        self.assertEqual(
            [(card["question_id"], card["level"]) for card in cards],
            [
                ("Q1", "good"),
                ("Q2", "neutral"),
                ("Q3", "attention"),
                ("Q4", "attention"),
                ("Q6", "attention"),
                ("Q7", "good"),
            ],
        )
        self.assertTrue(
            cards[3]["note"].startswith(
                "步骤复杂或取药不便：可以提前备药，并请医生或药师帮忙确认能否简化用药安排。"
            )
        )


class QuestionnaireHTTPTests(IdentityFixture):
    def test_answer_validation_and_unknown(self):
        response = self.response()
        path = f"/questionnaire-responses/{response['response_id']}/answers"
        for answers in (
            {"Q1": {"knowledge": 6}},
            {"Q4": {"reported_pattern": "none_reported", "barriers": ["other"]}},
            {
                "Q4": {
                    "reported_pattern": "both",
                    "barriers": ["other"],
                    "main_barrier": "execution_or_access",
                }
            },
            {"Q5": {"special_requirements": ["req_none", "req_before_meal"]}},
        ):
            with self.subTest(answers=answers):
                error = self.call(
                    self.a,
                    "PUT",
                    path,
                    {"expected_revision": 1, "answers": answers},
                    expected=422,
                )
                self.assertEqual(error["code"], "INVALID_ANSWER")
        saved = self.call(
            self.a,
            "PUT",
            path,
            {"expected_revision": 1, "answers": {"Q1": {"knowledge": "unknown"}}},
        )
        self.assertEqual(saved["answers"]["Q1"]["value"], {"knowledge": "unknown"})

    def test_submission_profile_reuse_and_assisted_restriction(self):
        response = self.response()
        rid = response["response_id"]
        path = f"/questionnaire-responses/{rid}"
        first = self.call(
            self.a,
            "PUT",
            path + "/answers",
            {
                "expected_revision": 1,
                "answers": {
                    "Q1": {"knowledge": 5},
                    "Q2": {"adherence_freq": "从不漏服"},
                },
            },
        )
        saved = self.call(
            self.a,
            "PUT",
            path + "/answers",
            {
                "expected_revision": first["meta"]["revision"],
                "answers": {"Q3": {"difficulty": 1}},
            },
        )
        self.assertEqual(saved["answers"]["Q1"]["value"], {"knowledge": 5})
        self.call(
            self.a,
            "POST",
            path + "/submit",
            {
                "expected_revision": saved["meta"]["revision"],
                "confirmed": True,
                "same_episode": True,
            },
        )
        body = {"response_id": rid}
        profile = self.call(
            self.a, "POST", f"/patients/{PA}/profiles", body, expected=201
        )
        self.assertEqual(profile["cas_observed"]["value"], 15)
        self.assertEqual(
            [card["question_id"] for card in profile["cards"]], ["Q1", "Q2", "Q3"]
        )
        for key in (
            "primary_type",
            "demo_classification",
            "research_group",
            "cas_predicted",
        ):
            self.assertNotIn(key, profile)
        self.assertEqual(
            self.call(self.a, "GET", f"/profiles/{profile['profile_id']}"), profile
        )
        self.assertEqual(
            self.call(self.a, "POST", f"/patients/{PA}/profiles", body, expected=201)[
                "profile_id"
            ],
            profile["profile_id"],
        )
        self.bind(["questionnaire:assist", "questionnaire:read", "profile:read"])
        assisted = self.response(self.f, answers={"Q1": {"knowledge": 5}})
        self.call(
            self.f,
            "POST",
            f"/questionnaire-responses/{assisted['response_id']}/submit",
            {"expected_revision": assisted["meta"]["revision"], "confirmed": True},
        )
        self.call(
            self.f,
            "POST",
            f"/patients/{PA}/profiles",
            {"response_id": assisted["response_id"]},
            expected=403,
        )

    def test_latest_submission_and_blank_superseding_response(self):
        path = f"/patients/{PA}/questionnaire-responses/latest-submitted"
        self.call(self.a, "GET", path, expected=404)
        first = self.submitted({"Q1": {"knowledge": 5}})
        profile = self.call(
            self.a,
            "POST",
            f"/patients/{PA}/profiles",
            {"response_id": first["response_id"]},
            expected=201,
        )
        self.assertEqual(self.call(self.a, "GET", path)["profile"], profile)
        second = self.call(
            self.a,
            "POST",
            f"/patients/{PA}/questionnaire-responses",
            {"supersedes_response_id": first["response_id"]},
            expected=201,
        )
        self.assertTrue(
            all(answer["value"] == {} for answer in second["answers"].values())
        )
        self.time[0] += timedelta(seconds=1)
        submitted = self.call(
            self.a,
            "POST",
            f"/questionnaire-responses/{second['response_id']}/submit",
            {"expected_revision": 1, "confirmed": True},
        )
        latest = self.call(self.a, "GET", path)
        self.assertEqual(latest["response_id"], submitted["response_id"])
        self.assertEqual(latest["submitted_at"], submitted["submitted_at"])
        self.assertIsNone(latest["profile"])
        self.bind(["questionnaire:read", "profile:read"])
        self.call(self.f, "GET", path, expected=403)


class CasModelTests(unittest.TestCase):
    def test_reference_predictions_and_insufficient_inputs(self):
        try:
            import torch  # noqa: F401
        except ImportError:
            self.skipTest("CAS 模型依赖未安装")
        from medplatform.profile.cas_model import MODEL_INPUTS, CasModel

        folder = (
            Path(__file__).resolve().parents[2] / "data/models/cas-dl2-retrain-20261124"
        )
        cases = json.loads((folder / "reference_cases.json").read_text("utf-8"))
        model = CasModel.load(folder)
        for case in cases:
            with self.subTest(case=case["case"]):
                raw = case["input"]
                values = {
                    theme["question_id"]: {
                        field["key"]: raw[MODEL_INPUTS.get(field["key"], field["key"])]
                        for field in theme["fields"]
                    }
                    for theme in cas.SPEC["themes"]
                    if theme["question_id"] in ("Q5", "Q6", "Q7", "Q8")
                }
                response = response_values(values)
                result = model.predict(response)
                self.assertEqual(result["status"], "estimated")
                self.assertAlmostEqual(
                    result["value"], case["expected_prediction"], delta=1e-5
                )
        values["Q8"]["stable_experience"] = "否"
        self.assertEqual(
            model.predict(response_values(values))["status"], "insufficient"
        )
        values["Q8"]["stable_experience"] = "是"
        for question, field in (
            ("Q5", "drug_count"),
            ("Q6", "meal_irregular"),
            ("Q7", "self_efficacy"),
            ("Q8", "income"),
        ):
            with self.subTest(question=question):
                incomplete = {
                    **values,
                    question: {
                        key: value
                        for key, value in values[question].items()
                        if key != field
                    },
                }
                result = model.predict(response_values(incomplete))
                self.assertEqual(result["status"], "insufficient")
                self.assertIn(question, result["reason"])
