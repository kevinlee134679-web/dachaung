"""Validation of model output against the dialogue contracts."""

from typing import get_args

from pydantic import ValidationError

from ..core.strict_json import loads
from . import inputs


def validate_completion(raw, citations):
    try:
        data = loads(raw)
        core = inputs.DialogueCore.model_validate(
            {"assistant_reply": data["assistant_reply"]}
        ).model_dump()
    except TypeError, ValueError, KeyError, ValidationError, RecursionError:
        return None, False

    focus = data.get("support_focus")
    core["support_focus"] = focus if focus in get_args(inputs.SupportFocus) else None
    strategies = data.get("communication_strategy", [])
    if not isinstance(strategies, list):
        strategies = [strategies]
    kept = [s for s in strategies if s in get_args(inputs.Strategy)]
    core["communication_strategy"] = list(dict.fromkeys(kept))[:2]
    degraded = (focus is not None and core["support_focus"] is None) or len(
        core["communication_strategy"]
    ) != len(strategies)

    def verified_list(value, schema, accept):
        if not isinstance(value, list):
            return [], True
        valid = []
        dropped = False
        for item in value:
            parsed = verified(item, schema, accept)
            if parsed is not None and parsed not in valid:
                valid.append(parsed)
            else:
                dropped = True
        return valid, dropped

    cues, lost_cues = verified_list(
        data.get("difficulty_cues", []), inputs.DifficultyCue, bool
    )
    refs, lost_refs = verified_list(
        data.get("knowledge_citations", []), inputs.Citation, citations
    )
    readiness = verified(data.get("change_readiness"), inputs.Readiness, bool)
    action = verified(data.get("suggested_action"), inputs.SuggestedAction, bool)
    degraded |= (
        lost_cues
        or lost_refs
        or readiness is None
        and data.get("change_readiness") is not None
    )
    degraded |= action is None and data.get("suggested_action") is not None
    return dict(
        core,
        difficulty_cues=cues,
        knowledge_citations=refs,
        suggested_action=action,
        change_readiness=readiness,
    ), degraded


def verified(value, schema, accept):
    if value is None:
        return None
    try:
        item = schema.model_validate(value).model_dump()
    except ValidationError:
        return None
    return item if accept(item) else None
