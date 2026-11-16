CREATE TABLE o_accounts (
    account_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    self_patient_id TEXT,
    is_admin INTEGER NOT NULL CHECK(is_admin IN (0,1)),
    current_patient_id TEXT
) STRICT;
CREATE TABLE o_sessions (
    session_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    csrf_hash TEXT NOT NULL,
    protected_csrf BLOB NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
) STRICT;
CREATE TABLE o_binding_codes (
    code_id TEXT PRIMARY KEY,
    code_hash TEXT NOT NULL UNIQUE,
    patient_id TEXT NOT NULL,
    issuer_session_hash TEXT NOT NULL REFERENCES o_sessions(session_hash),
    expires_at TEXT NOT NULL,
    consumed_at TEXT
) STRICT;
CREATE TABLE s02_documents (
    resource_key TEXT PRIMARY KEY,
    resource_type TEXT NOT NULL CHECK(resource_type IN ('Patient','FamilyBinding','Grant','QuestionnaireResponse','Profile','Medication','Draft','PlanVersion','ReminderPreferences','File')),
    patient_id TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK(json_valid(document_json) AND json_type(document_json)='object')
) STRICT;
CREATE INDEX s02_documents_patient_type ON s02_documents(patient_id, resource_type);
CREATE TABLE s02_document_history (
    resource_key TEXT NOT NULL REFERENCES s02_documents(resource_key),
    revision INTEGER NOT NULL CHECK(revision>0),
    document_json TEXT NOT NULL CHECK(json_valid(document_json) AND json_type(document_json)='object'),
    PRIMARY KEY(resource_key, revision)
) STRICT;
CREATE TABLE s02_source_keys (
    resource_type TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    account_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    resource_key TEXT NOT NULL REFERENCES s02_documents(resource_key),
    PRIMARY KEY(resource_type, patient_id, account_id, source_id)
) STRICT;
CREATE TABLE idempotency_receipts (
    receipt_id TEXT PRIMARY KEY,
    scope_hash TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('processing','committed','rejected','expired')),
    resource_type TEXT,
    resource_id TEXT,
    http_status INTEGER CHECK(http_status BETWEEN 100 AND 599),
    response_ref TEXT,
    protected_response BLOB,
    sensitive_until TEXT,
    created_at TEXT NOT NULL,
    full_receipt_until TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(scope_hash, key_hash)
) STRICT;
CREATE TABLE receipt_responses (
    response_ref TEXT PRIMARY KEY,
    response_json TEXT NOT NULL CHECK(json_valid(response_json) AND json_type(response_json)='object')
) STRICT;
CREATE TABLE change_notices (
    notice_id TEXT PRIMARY KEY,
    source_module TEXT NOT NULL CHECK(source_module IN ('O','A','B','C')),
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real')),
    kind TEXT NOT NULL CHECK(kind IN ('plan_published','event_revision_changed','statistics_changed','summary_changed','b_intervention_changed','c_service_changed','c_feedback_changed','points_source_changed')),
    source_ref TEXT NOT NULL CHECK(json_valid(source_ref) AND json_type(source_ref)='object'),
    business_key TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL CHECK(is_simulated=(data_environment='demo')),
    UNIQUE(source_module, data_environment, business_key)
) STRICT;
CREATE TABLE o_schedule_windows (
    plan_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL CHECK(window_end>window_start),
    PRIMARY KEY(plan_id, plan_version, window_start, window_end)
) STRICT;
CREATE TABLE o_revocation_audit (
    operation_id TEXT PRIMARY KEY REFERENCES operation_audit(operation_id),
    resource_type TEXT NOT NULL CHECK(resource_type IN ('FamilyBinding','Grant')),
    resource_id TEXT NOT NULL,
    reason TEXT NOT NULL
) STRICT;
