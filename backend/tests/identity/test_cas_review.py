from itertools import product
from unittest.mock import patch

from fixtures import PA, IdentityFixture, unknown_answers
from medplatform.profile import cas_review as review


class ReviewTests(IdentityFixture):
    def create(self, actor=None, **kwargs):
        return self.call(
            actor or self.a,
            "POST",
            f"/patients/{PA}/questionnaire-responses",
            {"questionnaire_version": review.VERSION, **kwargs},
            expected=201,
        )

    def submitted_review(self, answers, actor=None, episode=True):
        actor = actor or self.a
        rid = self.create(actor)["response_id"]
        path = f"/questionnaire-responses/{rid}"
        self.call(
            actor,
            "PUT",
            path + "/answers",
            {"answers": answers, "expected_revision": 1},
        )
        return self.call(
            actor,
            "POST",
            path + "/submit",
            {"confirmed": True, "same_episode": episode, "expected_revision": 2},
        )

    def generate(self, rid):
        return self.call(
            self.a,
            "POST",
            f"/patients/{PA}/profiles",
            {"response_id": rid},
            expected=201,
        )

    @staticmethod
    def sample():
        answers = unknown_answers()
        for q, key, value in [
            ("Q1", "knowledge", 4),
            ("Q2", "adherence_freq", "偶尔漏服（每周1-2次）"),
            ("Q3", "difficulty", 2),
            ("Q4", "behavior", "unintentional"),
        ]:
            answers[q] = {"state": "answered", "value": {key: value}}
        for q in ("Q5", "Q6", "Q7", "Q8"):
            answers[q] = {"state": "not_answered", "value": None}
        return answers

    def test_example_permissions_versioned_reuse_and_legacy_reassessment(self):
        legacy = self.submitted()
        old = self.generate(legacy["response_id"])
        new_draft = self.create(supersedes_response_id=legacy["response_id"])
        self.assertTrue(
            all(a["state"] == "not_answered" for a in new_draft["answers"].values())
        )
        legacy_definition = self.call(
            self.a, "GET", "/questionnaires/initial?version=initial-v0.1"
        )
        self.assertNotEqual(
            legacy_definition["themes"][0]["prompt"],
            review.definition()["themes"][0]["prompt"],
        )
        new = self.submitted_review(self.sample())
        rid = new["response_id"]
        self.assertEqual(new["answers"]["Q3"]["value"], {"difficulty": 2})
        result = self.generate(rid)
        self.assertEqual(
            result["cas_observed"],
            {"status": "observed", "value": 11, "missing_items": [], "reasons": []},
        )
        self.assertEqual(result["research_group"], "middle")
        self.assertIsNone(result["primary_type"])
        self.assertEqual(result["cas_predicted"], result["cas"])
        self.assertIsNone(result["cas"]["value"])
        self.assertEqual(result, self.generate(rid))
        with patch.object(review, "METHOD", "test-revised"):
            revised = self.generate(rid)
            self.assertNotEqual(revised["profile_id"], result["profile_id"])
            self.assertEqual(
                revised, self.call(self.a, "GET", f"/patients/{PA}/profiles/current")
            )
        for row in [old, result]:
            self.assertEqual(
                row, self.call(self.a, "GET", f"/profiles/{row['profile_id']}")
            )
        self.call(self.b, "GET", f"/profiles/{result['profile_id']}", expected=404)
        self.bind(["profile:read", "questionnaire:assist"])
        self.assertEqual(
            result, self.call(self.f, "GET", f"/profiles/{result['profile_id']}")
        )
        self.call(
            self.f,
            "POST",
            f"/patients/{PA}/profiles",
            {"response_id": rid},
            expected=403,
        )
        assisted = self.submitted_review(self.sample(), self.f)
        self.assertIsNone(
            self.generate(assisted["response_id"])["cas_observed"]["value"]
        )
        own_draft = self.create(supersedes_response_id=assisted["response_id"])
        self.assertTrue(all(a["value"] is None for a in own_draft["answers"].values()))

    def test_all_scores_group_edges_and_behavior_conflicts(self):
        frequency = list(review.FREQUENCY)
        for knowledge, position, difficulty in product(
            range(1, 6), range(5), range(1, 6)
        ):
            score = review.score(knowledge, frequency[position], difficulty)
            self.assertEqual(score, knowledge + 5 - position + 6 - difficulty)
            self.assertEqual(
                review.research_group(score),
                "low" if score < 10 else "middle" if score < 14 else "high",
            )
        for choice, behavior, primary, conflict in [
            (0, "none", "A", False),
            (0, "unintentional", None, True),
            (1, "none", None, True),
            (1, "both", None, False),
            (0, "uncertain", None, False),
        ]:
            answers = self.sample()
            answers["Q1"]["value"]["knowledge"] = 5
            answers["Q2"]["value"]["adherence_freq"] = frequency[choice]
            answers["Q3"]["value"]["difficulty"] = 1
            answers["Q4"]["value"]["behavior"] = behavior
            profile = review.assess(
                {"answers": answers, "same_episode": True, "respondent_mode": "self"}
            )
            self.assertEqual(profile["primary_type"], primary)
            self.assertEqual("复核" in profile["classification_reason"], conflict)

    def test_missing_episode_and_all_missing_states(self):
        for state in ["unknown", "declined", "not_applicable", "not_answered"]:
            answers = self.sample()
            answers["Q3"] = {"state": state, "value": None}
            submitted = self.submitted_review(answers)
            result = self.generate(submitted["response_id"])["cas_observed"]
            self.assertEqual(result["missing_items"], ["Q3"])
            self.assertEqual(result["status"], "insufficient")
            self.assertIsNone(result["value"])
        response = self.submitted_review(self.sample(), episode=False)
        self.assertIsNone(
            self.generate(response["response_id"])["cas_observed"]["value"]
        )

    def test_versions_raw_input_validation_and_optional_groups(self):
        response = self.create()
        path = f"/questionnaire-responses/{response['response_id']}/answers"
        for q, v in [
            ("Q1", {"knowledge": True}),
            ("Q1", {"knowledge": 6}),
            ("Q3", {"difficulty": "1"}),
            ("Q2", {"adherence_freq": "偶尔"}),
            ("Q4", {"behavior": "B1"}),
            ("Q5", {"requirements": ["req_none", "req_inject"]}),
            ("Q7", {"tech_accept": 7}),
            ("Q8", {"gender": {}}),
        ]:
            answers = self.sample()
            answers[q] = {"state": "answered", "value": v}
            self.call(
                self.a,
                "PUT",
                path,
                {"answers": answers, "expected_revision": 1},
                expected=422,
            )
        answers = self.sample()
        answers["Q5"] = {
            "state": "answered",
            "value": {"drug_type": "其他", "requirements": ["req_none"]},
        }
        answers["Q7"] = {"state": "answered", "value": {"health_literacy": 5}}
        stored = self.call(
            self.a, "PUT", path, {"answers": answers, "expected_revision": 1}
        )
        self.assertEqual(stored["answers"]["Q5"]["value"], answers["Q5"]["value"])
        self.assertEqual(stored["answers"]["Q7"]["value"], answers["Q7"]["value"])

    def test_synthetic_classification_cases_with_normalized_cause_evidence(self):
        # New, fictional cases at the evidence boundary, not the absent JSON fixtures.
        cases = [
            ("high", 5, "none", {}, None, "A", []),
            ("high", 5, "none", {"忘记": "B1"}, None, None, []),
            ("high", 4, "none", {}, None, None, []),
            ("middle", 3, "unintentional", {"忘记": "B1"}, None, None, []),
            ("low", 2, "unintentional", {"忘记": "B1"}, None, "B1", []),
            ("low", 2, "unintentional", {"补药困难": "B2"}, None, "B2", []),
            ("low", 2, "intentional", {"没理解用法而略过": "C1"}, None, "C1", []),
            ("low", 2, "intentional", {"因顾虑略过": "C2"}, None, "C2", []),
            ("low", 2, "intentional", {"因疲惫略过": "C3"}, None, "C3", []),
            ("low", 2, "both", {"外出冲突": "D1"}, None, "D1", []),
            ("low", 2, "unintentional", {"外出冲突": "D1"}, None, None, []),
            ("low", 2, "both", {"忘记": "B1", "因顾虑略过": "C2"}, None, None, []),
            (
                "low",
                2,
                "both",
                {"忘记": "B1", "因顾虑略过": "C2"},
                "因顾虑略过",
                "C2",
                ["B1"],
            ),
            ("low", 2, "unintentional", {"忘记": "B1", "其他": None}, "其他", None, []),
            ("low", 2, "uncertain", {"其他": None}, None, None, []),
            ("low", 2, "intentional", {}, None, None, []),
            (None, None, None, None, None, None, []),
        ]
        by_score = {v: k for k, v in review.FREQUENCY.items()}
        for group, freq, behavior, causes, main, primary, additional in cases:
            with self.subTest(group=group, behavior=behavior, causes=causes, main=main):
                result = review.classify(
                    group, by_score.get(freq), behavior, causes, main
                )
                self.assertEqual(result[:2], (primary, additional))
