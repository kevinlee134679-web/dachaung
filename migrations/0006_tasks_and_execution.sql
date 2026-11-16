CREATE TABLE a_tasks (
    task_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real')),
    owner_module TEXT NOT NULL CHECK(owner_module IN ('O','A','B','C')),
    owner_operation_key TEXT NOT NULL,
    creator_account_id TEXT,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    UNIQUE(data_environment,owner_module,owner_operation_key)
) STRICT;
CREATE INDEX a_tasks_patient ON a_tasks(patient_id,data_environment);
CREATE TABLE a_task_history (
    task_id TEXT NOT NULL REFERENCES a_tasks(task_id),
    revision INTEGER NOT NULL CHECK(revision>0),
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    PRIMARY KEY(task_id,revision)
) STRICT;
CREATE TABLE a_executions (
    execution_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES a_tasks(task_id),
    attempt INTEGER NOT NULL CHECK(attempt>0),
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    UNIQUE(task_id,attempt)
) STRICT;
CREATE TABLE a_task_leases (
    task_id TEXT PRIMARY KEY REFERENCES a_tasks(task_id),
    owner_instance_id TEXT NOT NULL,
    claim_token INTEGER NOT NULL CHECK(claim_token>0),
    claimed_at TEXT NOT NULL,
    lease_until TEXT NOT NULL,
    phase TEXT NOT NULL CHECK(phase IN ('claimed','side_effect_started','result_saved'))
) STRICT;
CREATE TABLE a_delivery_receipts (
    receipt_id TEXT PRIMARY KEY,
    provider_subject TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    UNIQUE(provider_subject,provider_event_id)
) STRICT;
CREATE TABLE a_reminder_contents (
    content_ref TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    dose_slot_id TEXT NOT NULL REFERENCES dose_slots(dose_slot_id),
    reminder_revision INTEGER NOT NULL CHECK(reminder_revision>0),
    text_content TEXT NOT NULL,
    privacy_enabled INTEGER NOT NULL CHECK(privacy_enabled IN (0,1)),
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE a_in_app_notifications (
    notification_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL UNIQUE REFERENCES a_tasks(task_id),
    execution_id TEXT NOT NULL REFERENCES a_executions(execution_id),
    patient_id TEXT NOT NULL,
    content_ref TEXT NOT NULL REFERENCES a_reminder_contents(content_ref),
    submitted_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL CHECK(is_simulated=1)
) STRICT;
CREATE TABLE a_notification_recipients (
    notification_id TEXT NOT NULL REFERENCES a_in_app_notifications(notification_id),
    account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    grant_id TEXT,
    grant_version INTEGER,
    submission_status TEXT NOT NULL CHECK(submission_status='submitted'),
    PRIMARY KEY(notification_id,account_id)
) STRICT;
CREATE TABLE a_reminder_snooze_links (
    source_task_id TEXT NOT NULL REFERENCES a_tasks(task_id),
    source_task_revision INTEGER NOT NULL CHECK(source_task_revision>0),
    child_task_id TEXT NOT NULL UNIQUE REFERENCES a_tasks(task_id),
    dose_slot_id TEXT NOT NULL REFERENCES dose_slots(dose_slot_id),
    created_at TEXT NOT NULL,
    PRIMARY KEY(source_task_id,source_task_revision)
) STRICT;
CREATE TABLE a_notice_consumptions (
    notice_id TEXT NOT NULL REFERENCES change_notices(notice_id),
    consumer TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','applied','ignored','failed')),
    result_ref TEXT,
    reason TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(notice_id,consumer)
) STRICT;
CREATE TABLE a_task_run_receipt_links (
    receipt_id TEXT PRIMARY KEY REFERENCES idempotency_receipts(receipt_id),
    execution_id TEXT NOT NULL REFERENCES a_executions(execution_id)
) STRICT;
