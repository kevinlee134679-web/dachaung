import json
from pathlib import Path

from ..core.errors import AppError

SPEC = json.loads(Path(__file__).with_name("cas_questionnaire.json").read_text("utf-8"))
VERSION = SPEC["version"]
METHOD = "cas-questionnaire-v2"
THEMES = SPEC["themes"]
FIELDS = {
    theme["question_id"]: {field["key"]: field for field in theme["fields"]}
    for theme in THEMES
}
FREQUENCY = {
    option["code"]: 5 - i
    for i, option in enumerate(FIELDS["Q2"]["adherence_freq"]["options"][:-1])
}


def definition():
    return {key: value for key, value in SPEC.items() if key != "result_notes"}


def validate_answers(answers):
    for question, values in answers.items():
        fields = FIELDS[question]
        if values.keys() - fields.keys():
            raise AppError(422, "INVALID_ANSWER", f"请核对 {question} 的字段")
        for key, value in values.items():
            field = fields[key]
            condition = field.get("visible_when")
            if condition and values.get(condition["field"]) not in condition["in"]:
                raise AppError(422, "INVALID_ANSWER", f"请核对 {question} 的字段")
            codes = [option["code"] for option in field["options"]]
            if field["kind"] == "selected_choice":
                valid = isinstance(value, str) and value in values.get(
                    field["source"], []
                )
            elif field["kind"] == "multiple":
                valid = (
                    isinstance(value, list)
                    and all(isinstance(v, str) and v in codes for v in value)
                    and len(value) == len(set(value))
                )
                if valid:
                    valid = len(value) <= 1 or not any(
                        v in field.get("exclusive", []) for v in value
                    )
                    value.sort()
            elif field["kind"] == "scale":
                valid = (type(value) is int or value == "unknown") and value in codes
            else:
                valid = isinstance(value, str) and value in codes
            if not valid:
                raise AppError(
                    422, "INVALID_ANSWER", f"请核对 {question} 的选项和取值范围"
                )


def score(knowledge, adherence_freq, difficulty):
    return knowledge + FREQUENCY[adherence_freq] + 6 - difficulty


def observed_result(response):
    answers = response["answers"]
    keys = {"Q1": "knowledge", "Q2": "adherence_freq", "Q3": "difficulty"}
    missing = [
        q
        for q, key in keys.items()
        if answers[q]["value"].get(key) in (None, "unknown")
    ]
    reasons = [f"{q} {THEMES[int(q[1:]) - 1]['title']}未取得有效回答" for q in missing]
    if response["respondent_mode"] != "self":
        reasons.append("需要患者本人自报，当前为家属协助作答")
    if response.get("same_episode") is not True:
        reasons.append("尚未确认 Q1–Q3 对应同一次用药经历")
    value = (
        None
        if reasons
        else score(*(answers[q]["value"][key] for q, key in keys.items()))
    )
    return {
        "status": "observed" if value is not None else "insufficient",
        "value": value,
        "missing_items": missing,
        "reasons": reasons,
    }


def factors(answers):
    q4 = answers["Q4"]["value"]
    labels = {
        key: {option["code"]: option["label"] for option in field["options"]}
        for key, field in FIELDS["Q4"].items()
    }
    items = [
        (
            "本次报告的实际行为",
            labels["reported_pattern"].get(q4.get("reported_pattern")),
        ),
        (
            "实际导致未按安排用药的原因",
            "、".join(labels["barriers"][b] for b in q4.get("barriers", [])),
        ),
        ("本人选出的主要原因", labels["barriers"].get(q4.get("main_barrier"))),
    ]
    return [
        {"label": label, "source_question_ids": ["Q4"], "source_value": text}
        for label, text in items
        if text
    ]


def cards(answers):
    result = []
    notes = SPEC["result_notes"]
    for q in ("Q1", "Q2", "Q3", "Q4", "Q6", "Q7"):
        values = answers[q]["value"]
        valid = {
            key: value
            for key, value in values.items()
            if value is not None and value != "unknown" and value != []
        }
        if not valid:
            continue
        labels = {
            key: {option["code"]: option["label"] for option in field["options"]}
            for key, field in FIELDS[q].items()
        }
        if q in ("Q1", "Q2", "Q3"):
            key = next(iter(FIELDS[q]))
            value = valid[key]
            rank = FREQUENCY[value] if q == "Q2" else value
            if q == "Q3":
                rank = 6 - rank
            level = "good" if rank >= 4 else "neutral" if rank == 3 else "attention"
            lines = [labels[key][value]]
            note = notes[q][level]
        elif q == "Q4":
            pattern = valid.get("reported_pattern")
            if pattern is None:
                continue
            barriers = valid.get("barriers", [])
            main = valid.get("main_barrier")
            level = (
                "good"
                if pattern == "none_reported"
                else "neutral"
                if pattern == "uncertain"
                else "attention"
            )
            lines = [labels["reported_pattern"][pattern]] + [
                labels["barriers"][b] for b in barriers
            ]
            ordered = ([main] if main else []) + [b for b in barriers if b != main]
            note = (
                "\n".join(notes[q]["barriers"][b] for b in ordered)
                if barriers
                else notes[q][pattern]
            )
        else:
            lines = [
                FIELDS[q][key]["prompt"]
                for key, value in valid.items()
                if (value >= 4 if q == "Q6" else value <= 2)
            ]
            level = "attention" if lines else "good"
            note = notes[q][level]
        result.append(
            {
                "question_id": q,
                "title": THEMES[int(q[1:]) - 1]["title"],
                "answers": lines,
                "level": level,
                "note": note,
            }
        )
    return result


def unavailable_cas():
    return {
        "status": "unavailable",
        "value": None,
        "model_version": None,
        "reason": "未配置 CAS 模型",
    }


def assess(response, model):
    answers = response["answers"]
    return {
        "status": "descriptive"
        if any(answer["value"] for answer in answers.values())
        else "insufficient",
        "cas_observed": observed_result(response),
        "cas": model.predict(response) if model else unavailable_cas(),
        "cards": cards(answers),
        "factors": factors(answers),
        "assessment_method_version": METHOD,
        "questionnaire_version": VERSION,
    }
