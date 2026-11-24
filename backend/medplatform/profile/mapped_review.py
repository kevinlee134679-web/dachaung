"""Versioned questionnaire and research-only profile from the supplied CAS mapping."""

import json
from pathlib import Path

from ..core.errors import AppError
from .cas_review import observed_result, valid_field
from .questionnaire import unavailable_cas

SPEC = json.loads(
    Path(__file__).with_name("cas_mapping_v1.json").read_text("utf-8-sig")
)
QUESTIONNAIRE = SPEC["questionnaire"]
PROFILE = SPEC["rule_based_profile"]
VERSION = QUESTIONNAIRE["version_candidate"]
INPUT_MAPPING = SPEC["version"]
METHOD = "observed-and-reported-barrier-demo-v1"
RULE = PROFILE["rule_version_candidate"]
TYPES = PROFILE["type_definitions"]
REASON_TYPES = PROFILE["reason_code_to_type"]
EVENT_PATTERNS = {"unintentional", "intentional", "both"}


def form_field(question, spec):
    key = spec["id"]
    options = spec.get("options", {})
    kind = "choice"
    if key == "main_barrier":
        pairs = []
        kind = "selected_choice"
    elif question in {"Q1", "Q3", "Q6", "Q7"}:
        pairs = [(str(code), label) for label, code in options.items()]
        kind = "scale"
    elif question == "Q4" or spec["input"] == "multiple_choice":
        pairs = options.items()
        if spec["input"] == "multiple_choice":
            kind = "multiple"
    else:
        # Store original categorical answers; conversion belongs to the input mapper.
        pairs = [(label, label) for label in options]
    return {
        "key": key,
        "prompt": spec["prompt"],
        "kind": kind,
        "options": [{"code": code, "label": label} for code, label in pairs],
    }


THEMES = [
    {
        "question_id": item["id"],
        "prompt": item["title"],
        "options": [],
        "fields": [form_field(item["id"], field) for field in item["fields"]],
    }
    for item in QUESTIONNAIRE["items"]
]
FIELDS = {t["question_id"]: {f["key"]: f for f in t["fields"]} for t in THEMES}
Q4_LABELS = {
    k: {o["code"]: o["label"] for o in f["options"]} for k, f in FIELDS["Q4"].items()
}


def definition():
    return {
        "questionnaire_id": "initial",
        "version": VERSION,
        "themes": THEMES,
        "purpose": "请就最近同一次规律用药经历回答 Q1–Q4。本人前三题用于问卷自报计分，Q4 的实际经历用于研究演示分型。Q5–Q8 自愿填写，启用研究模型时，完整回答这些题组可获得 CAS 预测值。",
    }


def validate_answers(answers):
    for q, answer in answers.items():
        if answer["state"] == "declined":
            raise AppError(
                422, "INVALID_ANSWER", f"{q} 本版拒答代码为 prefer_not_to_answer"
            )
        if answer["state"] != "answered":
            continue
        fields = answer["value"]
        if not fields or fields.keys() - FIELDS[q].keys():
            raise AppError(422, "INVALID_ANSWER", f"请核对 {q} 的字段")
        for key, value in fields.items():
            if key == "main_barrier":
                continue
            if key == "barriers" and value == []:
                continue
            if not valid_field(FIELDS[q][key], value):
                raise AppError(422, "INVALID_ANSWER", f"请核对 {q} 的选项和取值范围")
        if q == "Q4":
            if "reported_pattern" not in fields:
                raise AppError(422, "INVALID_ANSWER", "请先选择实际用药情况")
            main = fields.get("main_barrier")
            if main is not None and (
                not isinstance(main, str) or main not in fields.get("barriers", [])
            ):
                raise AppError(
                    422, "INVALID_ANSWER", "主要原因须从本次已选的实际原因中选择"
                )
        for key in ("barriers", "special_requirements"):
            if key in fields:
                fields[key] = sorted(fields[key])


def classify(value, frequency, q4):
    group = next(
        (
            name
            for name, (low, high) in PROFILE["classification_bands"].items()
            if type(value) is int and low <= value <= high
        ),
        None,
    )
    pattern = q4.get("reported_pattern")
    barriers = q4.get("barriers", [])
    primary = None
    matches = []
    review = False
    if group is None:
        reason = "缺少有效的本人问卷实测分"
    elif pattern not in EVENT_PATTERNS and pattern != "none_reported":
        reason = "实际用药情况未填或不能判断"
    elif frequency is not None and (
        (frequency == "从不漏服") != (pattern == "none_reported")
    ):
        review = True
        reason = "Q2 漏服频率与 Q4 报告的实际行为不一致，请复核原答"
    elif pattern == "none_reported" and barriers:
        review = True
        reason = "Q4 同时报告未发生和实际障碍，请复核原答"
    elif group == "high" and pattern == "none_reported":
        primary = "A"
        reason = "高分组且本人报告未发生漏服或未按时用药"
    elif group == "low":
        gates = (
            {"unintentional", "intentional", "both"} if pattern == "both" else {pattern}
        )
        matches = sorted(
            {
                t
                for b in barriers
                if (t := REASON_TYPES[b]) and TYPES[t]["gate"] in gates
            }
        )
        main = q4.get("main_barrier")
        if main is not None:
            candidate = REASON_TYPES[main]
            primary = candidate if candidate in matches else None
        elif len(matches) == 1:
            primary = matches[0]
        if primary:
            matches.remove(primary)
            reason = "依据本人报告的实际行为与原因匹配"
        elif matches:
            reason = "本次主要原因未确定可匹配的主类型，保留其他符合条件的障碍"
        else:
            reason = "本次未取得与实际行为相符的具体原因"
    else:
        reason = "保留本次研究分组和实际经历"
    tags = ([primary] if primary else []) + matches
    return {
        "research_group": group,
        "primary_type": primary,
        "reported_matching_types": matches,
        "type_labels": {t: TYPES[t]["label"] for t in tags},
        "entry_codes": list(
            dict.fromkeys(code for t in tags for code in TYPES[t]["entry_codes"])
        ),
        "needs_review": review,
        "reason": reason,
        "rule_version": RULE,
    }


def assess(response):
    answers = response["answers"]
    observed = observed_result(response)
    q4 = answers["Q4"]["value"] or {}
    pattern, barriers, main = (
        q4.get("reported_pattern"),
        q4.get("barriers", []),
        q4.get("main_barrier"),
    )
    demo = classify(
        observed["value"], (answers["Q2"]["value"] or {}).get("adherence_freq"), q4
    )
    factors = []
    for label, text in [
        ("本次报告的实际行为", Q4_LABELS["reported_pattern"].get(pattern)),
        (
            "实际导致未按安排用药的原因",
            "、".join(Q4_LABELS["barriers"][b] for b in barriers),
        ),
        ("本人选出的主要原因", Q4_LABELS["barriers"].get(main)),
    ]:
        if text:
            factors.append(
                {"label": label, "source_question_ids": ["Q4"], "source_value": text}
            )
    predicted = unavailable_cas()
    predicted["reason"] = "生成此画像时未启用本机 CAS 研究预测。"
    return {
        "status": "descriptive"
        if any(a["state"] == "answered" for a in answers.values())
        else "insufficient",
        "cas_observed": observed,
        "cas": predicted,
        "cas_predicted": predicted,
        "research_group": demo["research_group"],
        "demo_classification": demo,
        # Product consumers use these fields for downstream matching. The supplied
        # rule is a research/demo rule with enabled_in_product=false.
        "primary_type": None,
        "additional_types": [],
        "support_entry_codes": [],
        "reported_behavior": pattern,
        "factors": factors,
        "missing_items": [],
        "input_mapping_version": INPUT_MAPPING,
        "assessment_method_version": METHOD,
        "classification_rule_version": RULE,
    }
