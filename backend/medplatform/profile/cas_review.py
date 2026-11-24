"""Self-reported CAS from the three original items. Research/demo use only."""

import json
from pathlib import Path

from ..core.errors import AppError
from .questionnaire import unavailable_cas

# This revision only exposes Q4 fields whose meanings are specified in the paper.
VERSION = "initial-cas-review-v1-core1"
INPUT_MAPPING = "original-items-v1-core1"
METHOD = "observed-and-group-v1-core1"
RULE = "demo-group-v1-core1"
FREQUENCY = {
    "从不漏服": 5,
    "几乎从不漏服（两三周1次）": 4,
    "偶尔漏服（每周1-2次）": 3,
    "经常漏服（每周3-5次）": 2,
    "极度随性（想起来才吃，经常连续几天不吃）": 1,
}
THEMES = json.loads(
    Path(__file__).with_name("review_questions.json").read_text("utf-8")
)
FIELDS = {t["question_id"]: {f["key"]: f for f in t["fields"]} for t in THEMES}
BEHAVIORS = {o["code"]: o["label"] for o in FIELDS["Q4"]["behavior"]["options"]}


def definition():
    return {
        "questionnaire_id": "initial",
        "version": VERSION,
        "purpose": "请就最近同一次规律用药经历填写 Q1–Q4。Q5–Q8 自愿补充，可直接跳过。本人自报的前三项可用于计算本次问卷 CAS。",
        "themes": THEMES,
    }


def valid_field(field, value):
    codes = [o["code"] for o in field["options"]]
    if field["kind"] == "scale":
        return type(value) is int and str(value) in codes
    if field["kind"] == "multiple":
        return (
            isinstance(value, list)
            and bool(value)
            and all(isinstance(v, str) and v in codes for v in value)
            and len(value) == len(set(value))
            and ("req_none" not in value or len(value) == 1)
        )
    return isinstance(value, str) and value in codes


def validate_answers(answers):
    for q, answer in answers.items():
        if answer["state"] == "prefer_not_to_answer":
            raise AppError(422, "INVALID_ANSWER", "此版本使用 declined 表示拒答")
        if answer["state"] != "answered":
            continue
        fields = answer["value"]
        if not fields or any(
            key not in FIELDS[q] or not valid_field(FIELDS[q][key], value)
            for key, value in fields.items()
        ):
            raise AppError(
                422, "INVALID_ANSWER", f"请核对 {q} 的字段、原选项和取值范围"
            )
        if "requirements" in fields:
            fields["requirements"] = sorted(fields["requirements"])
    return answers


def score(knowledge, adherence_freq, difficulty):
    return knowledge + FREQUENCY[adherence_freq] + (6 - difficulty)


def research_group(value):
    if value <= 9:
        return "low"
    return "middle" if value <= 13 else "high"


def classify(group, frequency, behavior, reason_types=None, main_reason=None):
    """reason_types maps each selected actual cause to its verified type or None.

    The core questionnaire has no verified cause dictionary. Only the offline
    acceptance cases supply this argument until the Q4 mapping is available.
    """
    occurred = behavior in ("unintentional", "intentional", "both")
    if (
        frequency is not None
        and (occurred or behavior == "none")
        and ((FREQUENCY[frequency] == 5) != (behavior == "none"))
    ):
        return None, [], "Q2 的频率与 Q4 报告的实际行为不一致，请复核原答"
    if group == "high":
        if behavior == "none" and not reason_types:
            return "A", [], "高分组且本人明确报告本次未发生漏服或未按时用药"
        return None, [], "本次回答未满足维持型的实际行为条件"
    if group == "middle":
        return None, [], "中间组保留实际障碍描述"
    if group != "low":
        return None, [], "缺少有效的本人问卷实测分"
    if reason_types is None:
        return None, [], "低分组需核对 Q4 具体原因及首要原因映射，暂不分型"
    eligible = {
        "unintentional": {"B1", "B2"},
        "intentional": {"C1", "C2", "C3"},
        "both": {"B1", "B2", "C1", "C2", "C3", "D1"},
    }.get(behavior, set())
    matches = sorted(eligible.intersection(reason_types.values()))
    if main_reason is not None:
        primary = reason_types.get(main_reason)
    else:
        primary = matches[0] if len(matches) == 1 else None
    if primary not in matches:
        return None, [], "缺少可确定主类型的实际障碍或首要原因，保留原报告"
    return (
        primary,
        [t for t in matches if t != primary],
        "按本人报告的实际情况与原因匹配",
    )


def observed_result(response):
    answers = response["answers"]
    missing = [q for q in ("Q1", "Q2", "Q3") if answers[q]["state"] != "answered"]
    reasons = [f"{q} {THEMES[int(q[1:]) - 1]['prompt']}未取得有效回答" for q in missing]
    if response["respondent_mode"] != "self":
        reasons.append("需要患者本人自报，当前为家属协助作答")
    if response.get("same_episode") is not True:
        reasons.append("尚未确认 Q1–Q3 对应同一次用药经历")
    value = (
        None
        if reasons
        else score(
            **{k: v for q in ("Q1", "Q2", "Q3") for k, v in answers[q]["value"].items()}
        )
    )
    return {
        "status": "observed" if value is not None else "insufficient",
        "value": value,
        "missing_items": missing,
        "reasons": reasons,
    }


def assess(response):
    answers = response["answers"]
    observed = observed_result(response)
    value = observed["value"]
    group = research_group(value) if value is not None else None
    behavior = (answers["Q4"]["value"] or {}).get("behavior")
    frequency = (answers["Q2"]["value"] or {}).get("adherence_freq")
    primary, secondary, classification_reason = classify(group, frequency, behavior)
    predicted = unavailable_cas()
    predicted["reason"] = "2.0 模型工件和逐例推理对照尚未验证"
    return {
        "status": "descriptive"
        if any(a["state"] == "answered" for a in answers.values())
        else "insufficient",
        "cas_observed": observed,
        "cas": predicted,
        "cas_predicted": predicted,
        "research_group": group,
        "classification_reason": classification_reason,
        "primary_type": primary,
        "additional_types": secondary,
        "reported_behavior": behavior,
        "factors": [
            {
                "label": "本次问卷报告的实际行为",
                "source_question_ids": ["Q4"],
                "source_value": BEHAVIORS[behavior],
            }
        ]
        if behavior
        else [],
        "missing_items": [],
        "support_entry_codes": [],
        "input_mapping_version": INPUT_MAPPING,
        "classification_rule_version": RULE,
        "assessment_method_version": METHOD,
    }
