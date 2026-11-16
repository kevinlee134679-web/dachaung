"""Strict A7/O5 inputs. Registered payloads are data, never executable commands."""
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .s02_inputs import Input, ID, Version, DateTime, Short, utc
from .errors import AppError


class WindowTaskPayload(Input):
    window_start: DateTime
    window_end: DateTime
    data_environment: Literal['demo', 'real']

    @model_validator(mode='after')
    def interval(self):
        if not 0 < (datetime.fromisoformat(self.window_end)-datetime.fromisoformat(self.window_start)).total_seconds() <= 31*86400:
            raise ValueError('window must be positive and at most 31 days')
        return self


class ReminderTaskPayload(Input):
    dose_slot_id: ID
    reminder_revision: Version
    content_ref: ID


class CheckinTaskPayload(Input):
    cycle_id: ID
    node_code: Short
    rule_version: Short


class InterventionTaskPayload(Input):
    intervention_id: ID
    content_ref: ID
    channel: Literal['mock']


class BExpiryTaskPayload(Input):
    session_id: ID
    target_kind: Literal['ui_mode', 'invitation', 'suggestion']
    target_id: ID
    expected_revision: Version


class ServiceDispatchTaskPayload(Input):
    service_id: ID
    service_revision: Version
    confirmation_ref_id: ID
    sharing_scope_ref_id: ID


class RewardFulfillmentTaskPayload(Input):
    redemption_id: ID
    fulfillment_id: ID
    reward_id: ID
    reward_version: Short


PAYLOADS = {'refresh_statistics': WindowTaskPayload, 'refresh_summary': WindowTaskPayload,
            'deliver_reminder': ReminderTaskPayload, 'check_in_node': CheckinTaskPayload,
            'deliver_intervention': InterventionTaskPayload, 'expire_b_state': BExpiryTaskPayload,
            'dispatch_service': ServiceDispatchTaskPayload, 'fulfill_reward': RewardFulfillmentTaskPayload}


class TaskCreateInput(Input):
    patient_id: ID
    kind: Literal['refresh_statistics', 'refresh_summary', 'deliver_reminder', 'check_in_node',
                  'deliver_intervention', 'expire_b_state', 'dispatch_service', 'fulfill_reward']
    owner_module: Literal['O', 'A', 'B', 'C']
    owner_operation_key: Short
    scheduled_at: DateTime
    valid_until: DateTime
    payload: dict
    intervention_id: ID | None = None
    rule_version: Short

    @model_validator(mode='after')
    def registered(self):
        if self.valid_until <= self.scheduled_at:
            raise ValueError('valid_until must exceed scheduled_at')
        owners = {'refresh_statistics': 'A', 'refresh_summary': 'A', 'deliver_reminder': 'O',
                  'check_in_node': 'B', 'deliver_intervention': 'B', 'expire_b_state': 'B',
                  'dispatch_service': 'C', 'fulfill_reward': 'C'}
        if self.owner_module != owners[self.kind]:
            raise ValueError('owner does not own this capability')
        self.payload = PAYLOADS[self.kind].model_validate(self.payload).model_dump()
        if self.kind == 'deliver_intervention' and self.intervention_id != self.payload['intervention_id']:
            raise ValueError('intervention references differ')
        if self.owner_module != 'B' and self.intervention_id is not None:
            raise ValueError('intervention is a B reference')
        return self


class TaskRunInput(Input):
    expected_revision: Version


class TaskCancelInput(TaskRunInput):
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class ReminderSnoozeInput(Input):
    source_task_id: ID
    expected_task_revision: Version
    snooze_minutes: Annotated[int, Field(ge=5, le=120)]


class DeliveryReceiptInput(Input):
    provider_event_id: ID
    execution_id: ID
    occurred_at: DateTime
    status: Literal['submitted', 'delivered', 'failed']
    failure_code: Short | None = None
    failure_message: Annotated[str, Field(min_length=1, max_length=2000)] | None = None

    @model_validator(mode='after')
    def failure(self):
        if self.status == 'failed' and self.failure_code is None:
            raise ValueError('failed receipt requires failure_code')
        return self


def query_input(action, raw_query):
    pairs = list(raw_query.multi_items()) if hasattr(raw_query, 'multi_items') else list(raw_query.items()) if hasattr(raw_query, 'items') else list(raw_query)
    query = dict(pairs)
    allowed = {'cursor', 'limit', 'status'} if action == 'tasks' else {'cursor', 'limit'} if action == 'executions' else set()
    try:
        if len(pairs) != len(query) or set(query)-allowed:
            raise ValueError()
        if 'limit' in query and (not str(query['limit']).isascii() or not str(query['limit']).isdigit() or not 1 <= int(query['limit']) <= 100):
            raise ValueError()
        if 'cursor' in query and not query['cursor']:
            raise ValueError()
        if 'status' in query and query['status'] not in ('pending','running','retry_wait','succeeded','failed','cancelled','expired'):
            raise ValueError()
    except (ValueError, TypeError):
        raise AppError(422, 'VALIDATION_ERROR', '任务查询字段或值不合法') from None
    return query
