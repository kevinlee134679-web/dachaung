"""Strict inputs for the registered B contracts."""
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator, model_validator

from .errors import AppError
from .s02_inputs import DateTime, ID, Input, Short, Text, Version, utc

TurnCount = Annotated[int, Field(ge=0)]
Reason = Annotated[str, Field(min_length=1, max_length=500)]
UserText = Annotated[str, Field(min_length=1, max_length=4000)]
CueKind = Literal["low_mood", "anxiety_concerns", "treatment_fatigue", "routine_barriers"]
KnowledgeKind = Literal["communication", "medical", "service_information"]
Intention = Literal["small_step", "offer_simplified_mode", "offer_professional_support"]
Mode = Literal["normal", "simplified"]
TagList = list[Short]
INVITATION_STATES = {"pending", "accepted", "declined", "expired", "cancelled"}
PATIENT_QUERY = {"patient_id"}
PAGE = {"cursor", "limit"}


class SessionCreate(Input):
    patient_id: ID
    case_id: ID | None = None
    entry_source: Literal["user", "accepted_invitation"] = "user"
    invitation_id: ID | None = None

    @model_validator(mode="after")
    def entry_matches(self):
        if (self.entry_source == "accepted_invitation") != (self.invitation_id is not None):
            raise ValueError("invitation must match entry source")
        return self


class CloseSession(Input):
    expected_revision: Version
    reason: Reason | None = None


class MessageInput(Input):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=False)

    client_message_id: ID
    content: UserText
    expected_turn_count: TurnCount

    @field_validator("content")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("message is blank")
        return value


class GenerationRetry(Input):
    generation_id: ID
    expected_turn_count: TurnCount


class DifficultyCue(Input):
    category: CueKind
    label: Short
    evidence: Text
    source_message_id: ID


class Readiness(Input):
    state: Literal["not_considering", "ambivalent", "preparing", "acting", "maintaining"]
    evidence: Text
    source_message_id: ID


class SuggestedAction(Input):
    type: Intention
    description: Text


class Citation(Input):
    retrieval_id: ID
    knowledge_id: ID
    version: ID
    fragment_id: ID
    source_locator: Annotated[str, Field(min_length=1, max_length=2000)]
    quote: Text
    review_status_at_use: Literal["reviewed"]


class DialogueCore(Input):
    assistant_reply: Text
    support_focus: Literal["listening", "clarifying", "exploring", "action_support", "closing"]
    communication_strategy: Annotated[list[Literal[
        "reflection", "affirmation", "open_question", "autonomy_support", "permission_based_advice", "summary",
    ]], Field(min_length=1, max_length=2)]


class SelfReportItem(Input):
    dimension: Literal["concerns", "necessity", "burden", "routine", "support_need"]
    description: Text
    source_message_id: ID | None = None


class SelfReport(Input):
    client_report_id: ID
    items: Annotated[list[SelfReportItem], Field(min_length=1)]


class ModePut(Input):
    ui_mode: Mode
    expected_revision: Version
    confirmed: Literal[True]
    source_suggestion_id: ID | None = None


class SuggestionRespond(Input):
    choice: Literal["accepted", "declined", "cancelled"]
    expected_status: Literal["pending"]


class Display(Input):
    client_receipt_id: ID
    displayed_at: DateTime


class InvitationRespond(Input):
    choice: Literal["accepted", "declined"]
    expected_status: Literal["pending"]
    session_id: ID | None = None


class ReferralCreate(Input):
    patient_id: ID
    session_id: ID
    source_suggestion_id: ID | None = None
    resource_id: ID
    service_draft_id: ID
    service_draft_revision: Version
    confirmation_ref_id: ID
    sharing_scope_ref_id: ID


class SummaryRef(Input):
    summary_id: ID
    window_start: DateTime
    window_end: DateTime
    generated_at: DateTime
    valid_until: DateTime
    data_status: Literal["fresh", "stale", "insufficient"]
    schema_version: ID


class StateEvent(Input):
    source_event_id: ID
    patient_id: ID
    event_type: Literal["summary_updated", "plan_changed", "consent_revoked"]
    summary_ref: SummaryRef | None
    occurred_at: DateTime
    rule_version: ID


class ExecutionReceipt(Input):
    source_event_id: ID
    patient_id: ID
    task_id: ID
    execution_id: ID
    intervention_id: ID
    occurred_at: DateTime
    execution: dict


class ReferralReceipt(Input):
    source_event_id: ID
    patient_id: ID
    referral_id: ID
    service_id: ID
    service_status: Literal["submitted", "in_progress", "completed", "cancelled", "failed"]
    occurred_at: DateTime
    source_version: Annotated[str, Field(pattern=r"^[1-9][0-9]*$", max_length=128)]


class Trigger(Input):
    case_id: ID
    session_id: ID | None = None
    scenario: Literal[
        "state_event", "periodic_node", "llm_timeout", "empty_response", "invalid_json",
        "knowledge_empty", "star_mid_failure", "receipt_late",
    ]
    scenario_run_id: ID
    occurred_at: DateTime


class CaseReset(Input):
    case_template_version: ID
    confirmed: Literal[True]


class KnowledgeCreate(Input):
    kind: KnowledgeKind
    title: Short
    body: Annotated[str, Field(min_length=1, max_length=20000)]
    source_locator: Annotated[str, Field(min_length=1, max_length=2000)]
    applicability_tags: TagList
    language: Literal["zh-CN"] = "zh-CN"
    effective_from: DateTime
    effective_until: DateTime | None = None

    @field_validator("source_locator")
    @classmethod
    def safe_locator(cls, value):
        locator = urlsplit(value)
        if locator.scheme in ("http", "https") and locator.hostname and not (
            locator.username or locator.password or locator.query
        ):
            return value
        if locator.scheme == "project" and locator.path and not (
            locator.netloc or locator.query or "\\" in value or ".." in locator.path
        ):
            return value
        raise ValueError("use a public URL or logical project source")

    @model_validator(mode="after")
    def valid_window(self):
        if self.effective_until is not None and self.effective_until <= self.effective_from:
            raise ValueError("knowledge life cycle is empty")
        return self


class KnowledgeVersion(Input):
    expected_current_version: ID
    content: KnowledgeCreate


class KnowledgeReview(Input):
    version: ID
    expected_revision: Version
    decision: Literal["approve", "reject"]
    note: Text


class KnowledgeWithdraw(Input):
    version: ID
    expected_revision: Version
    reason: Reason


class KnowledgeSearch(Input):
    patient_id: ID
    query: Text
    applicability_tags: TagList
    limit: Annotated[int, Field(ge=1, le=10)] = 5
    purpose: Literal["medical_support", "communication", "service_explanation"] = "medical_support"


class ModelProbe(Input):
    profile_id: ID
    expected_config_version: ID
    allow_external_call: bool


class ModelProfile(Input):
    profile_id: ID
    expected_config_version: ID
    confirmed: Literal[True]


QUERY_KEYS = {
    "cases": PAGE,
    "sessions": PAGE | PATIENT_QUERY | {"case_id"},
    "messages": PAGE | {"client_message_id"},
    "assessments": PAGE,
    "mode_get": PAGE | {"include_history"},
    "session_invitations": PAGE | {"status"},
    "patient_invitations": PAGE | {"status"},
    "feedback": PAGE | {"window_start", "window_end"},
    "export": PAGE | PATIENT_QUERY | {"window_start", "window_end", "format"},
    "knowledge_list": PAGE | {"kind", "include_unreviewed"},
    "knowledge_version": {"session_id"},
}


def query_input(action, pairs):
    query = dict(pairs)
    try:
        if len(pairs) != len(query) or set(query) - QUERY_KEYS.get(action, set()):
            raise ValueError()
        if "limit" in query:
            value = query["limit"]
            if not value.isascii() or not value.isdigit() or not 1 <= int(value) <= 100:
                raise ValueError()
            query["limit"] = int(value)
        for name in ("cursor", "case_id", "client_message_id", "session_id", "patient_id"):
            if name in query and not 1 <= len(query[name]) <= (4096 if name == "cursor" else 128):
                raise ValueError()
        for name in ("include_history", "include_unreviewed"):
            if name in query:
                if query[name] not in ("true", "false"):
                    raise ValueError()
                query[name] = query[name] == "true"
        if action in {"sessions", "export"} and "patient_id" not in query:
            raise ValueError()
        if action in {"feedback", "export"}:
            query["window_start"] = utc(query["window_start"])
            query["window_end"] = utc(query["window_end"])
            interval = datetime.fromisoformat(query["window_end"]) - datetime.fromisoformat(query["window_start"])
            if not 0 < interval.total_seconds() <= 31 * 86400:
                raise ValueError()
        if ("status" in query and query["status"] not in INVITATION_STATES
                or "format" in query and query["format"] != "json"
                or "kind" in query and query["kind"] not in {"communication", "medical", "service_information"}):
            raise ValueError()
    except (KeyError, ValueError, OverflowError):
        raise AppError(422, "VALIDATION_ERROR", "B 查询参数、时区或窗口不合法") from None
    return query
