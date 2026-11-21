CREATE TABLE s03_devices (
    device_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('box','wearable')),
    data_environment TEXT NOT NULL CHECK(data_environment='demo')
) STRICT;
INSERT INTO s03_devices VALUES ('demo-box-a','box','demo'),('demo-box-b','box','demo'),('demo-wearable-a','wearable','demo');
CREATE TABLE s03_device_bindings (
    binding_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES s03_devices(device_id),
    patient_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','revoked')),
    bound_at TEXT NOT NULL,
    revoked_at TEXT,
    revision INTEGER NOT NULL CHECK(revision>0),
    updated_at TEXT NOT NULL
) STRICT;
CREATE UNIQUE INDEX s03_one_active_device_binding ON s03_device_bindings(device_id) WHERE status='active';
CREATE TABLE s03_device_binding_history (
    binding_id TEXT NOT NULL REFERENCES s03_device_bindings(binding_id),
    revision INTEGER NOT NULL,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    PRIMARY KEY(binding_id,revision)
) STRICT;
CREATE TABLE s03_device_binding_audit (
    operation_id TEXT PRIMARY KEY REFERENCES operation_audit(operation_id),
    binding_id TEXT NOT NULL REFERENCES s03_device_bindings(binding_id),
    reason TEXT
) STRICT;
CREATE TABLE s03_quality_history (
    quality_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    event_revision INTEGER NOT NULL,
    processed_at TEXT NOT NULL,
    processing_version TEXT NOT NULL,
    quality_json TEXT NOT NULL CHECK(json_valid(quality_json)),
    FOREIGN KEY(event_id,event_revision) REFERENCES event_revisions(event_id,revision)
) STRICT;
CREATE INDEX s03_quality_event_time ON s03_quality_history(event_id,event_revision,processed_at);
CREATE TABLE s03_match_history (
    match_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL,
    event_revision INTEGER NOT NULL,
    generated_at TEXT NOT NULL,
    actor_account_id TEXT,
    is_review INTEGER NOT NULL CHECK(is_review IN (0,1)),
    match_json TEXT NOT NULL CHECK(json_valid(match_json)),
    FOREIGN KEY(event_id,event_revision) REFERENCES event_revisions(event_id,revision)
) STRICT;
CREATE INDEX s03_match_event_time ON s03_match_history(event_id,event_revision,generated_at);
