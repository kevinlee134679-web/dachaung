"""Validation of model output against the public dialogue core and its evidence."""

from pydantic import ValidationError

from ..core.strict_json import loads
from . import inputs


def validate_completion(raw, allowed_user_messages, citations):
    """Reject an invalid core. Keep only structured auxiliary data with actual evidence."""
    try:
        data = loads(raw)
        fields = inputs.DialogueCore.model_fields
        if set(data) != set(fields) | {
            "difficulty_cues",
            "suggested_action",
            "knowledge_citations",
            "change_readiness",
        }:
            raise ValueError("unexpected core structure")
        core = inputs.DialogueCore.model_validate(
            {key: data[key] for key in fields}
        ).model_dump()
    except TypeError, ValueError, ValidationError, RecursionError:
        return None, False

    def evidence(item):
        return item["evidence"] in allowed_user_messages.get(
            item["source_message_id"], ""
        )

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
        data["difficulty_cues"], inputs.DifficultyCue, evidence
    )
    refs, lost_refs = verified_list(
        data["knowledge_citations"], inputs.Citation, citations
    )
    readiness = verified(data["change_readiness"], inputs.Readiness, evidence)
    action = verified(data["suggested_action"], inputs.SuggestedAction, bool)
    degraded = (
        lost_cues
        or lost_refs
        or readiness is None
        and data["change_readiness"] is not None
    )
    degraded |= action is None and data["suggested_action"] is not None
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
