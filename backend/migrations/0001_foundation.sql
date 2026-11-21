CREATE TABLE operation_audit (
    operation_id TEXT PRIMARY KEY,
    account_id TEXT,
    patient_id TEXT,
    operation TEXT NOT NULL,
    outcome TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real'))
) STRICT;
CREATE TABLE dose_slots (
    dose_slot_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real')),
    plan_id TEXT NOT NULL,
    plan_version INTEGER NOT NULL CHECK(plan_version > 0),
    plan_entry_id TEXT NOT NULL,
    medication_id TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','superseded','cancelled')),
    source_rule_version TEXT NOT NULL,
    is_simulated INTEGER NOT NULL CHECK(is_simulated = (data_environment = 'demo')),
    UNIQUE(patient_id, data_environment, dose_slot_id),
    UNIQUE(patient_id, data_environment, plan_id, plan_version, plan_entry_id, scheduled_at)
) STRICT;
CREATE TABLE source_events (
    event_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real')),
    event_kind TEXT NOT NULL CHECK(event_kind IN ('medication','measurement')),
    source TEXT NOT NULL CHECK(source IN ('manual','box','wearable')),
    source_subject_id TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    evidence_type TEXT,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    reporter_account_id TEXT,
    device_id TEXT,
    original_payload_json TEXT NOT NULL CHECK(json_valid(original_payload_json) AND json_type(original_payload_json)='object'),
    is_simulated INTEGER NOT NULL CHECK(is_simulated = (data_environment = 'demo')),
    CHECK((source='manual' AND reporter_account_id IS NOT NULL AND device_id IS NULL)
       OR (source IN ('box','wearable') AND reporter_account_id IS NULL AND device_id IS NOT NULL)),
    CHECK(source_subject_id = COALESCE(reporter_account_id, device_id)),
    CHECK((event_kind='measurement' AND evidence_type IS NULL)
       OR (event_kind='medication' AND evidence_type IS NOT NULL AND source='manual' AND evidence_type IN ('self_report','family_report'))
       OR (event_kind='medication' AND evidence_type IS NOT NULL AND source IN ('box','wearable') AND evidence_type IN ('box_opening','device_inference'))),
    UNIQUE(patient_id, data_environment, event_id),
    UNIQUE(event_id, is_simulated),
    UNIQUE(patient_id, data_environment, source, source_subject_id, source_event_id)
) STRICT;
CREATE INDEX source_events_patient_time ON source_events(patient_id, data_environment, occurred_at, event_id);
