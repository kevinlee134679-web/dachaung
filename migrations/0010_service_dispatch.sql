CREATE TABLE c_services (
    service_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    service_draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    confirmation_ref_id TEXT NOT NULL,
    sharing_scope_ref_id TEXT NOT NULL,
    dispatch_task_id TEXT NOT NULL UNIQUE REFERENCES a_tasks(task_id) DEFERRABLE INITIALLY DEFERRED,
    submitted_at TEXT NOT NULL,
    UNIQUE (patient_id, service_draft_id, draft_revision),
    FOREIGN KEY (service_draft_id, patient_id) REFERENCES c_service_drafts(service_draft_id, patient_id),
    FOREIGN KEY (service_draft_id, draft_revision, confirmation_ref_id)
        REFERENCES c_draft_confirmations(service_draft_id, draft_revision, confirmation_ref_id),
    FOREIGN KEY (sharing_scope_ref_id, patient_id) REFERENCES o_sharing_scopes(sharing_scope_ref_id, patient_id)
) STRICT;

CREATE INDEX c_services_patient ON c_services (patient_id, submitted_at, service_id);
CREATE INDEX c_services_sharing ON c_services (sharing_scope_ref_id);

ALTER TABLE c_service_drafts ADD COLUMN status TEXT NOT NULL DEFAULT 'preparing'
    CHECK (status IN ('preparing','submitted','abandoned'));
ALTER TABLE c_service_drafts ADD COLUMN service_id TEXT REFERENCES c_services(service_id);

CREATE TABLE c_service_history (
    service_id TEXT NOT NULL REFERENCES c_services(service_id),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    status TEXT NOT NULL CHECK (status IN ('submitted','in_progress','completed','cancelled','failed')),
    source_kind TEXT NOT NULL CHECK (source_kind IN ('patient_submit','b_referral','patient_cancel','demo_transition','provider_receipt')),
    actor_id TEXT NOT NULL,
    source_event_id TEXT,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK (json_valid(document_json) AND json_type(document_json)='object'
        AND json_extract(document_json,'$.service_id') IS service_id
        AND json_extract(document_json,'$.status') IS status
        AND json_extract(document_json,'$.meta.revision') IS revision),
    PRIMARY KEY (service_id, revision)
) STRICT;

CREATE TRIGGER c_service_history_legal_insert
BEFORE INSERT ON c_service_history
WHEN NOT (
    NEW.revision = COALESCE((SELECT MAX(revision) FROM c_service_history WHERE service_id=NEW.service_id),0)+1
    AND (
        (NEW.revision=1 AND NEW.status='submitted')
        OR EXISTS (
            SELECT 1 FROM c_service_history AS prior
            WHERE prior.service_id=NEW.service_id AND prior.revision=NEW.revision-1
            AND NEW.occurred_at>=prior.occurred_at
            AND ((prior.status='submitted' AND NEW.status IN ('in_progress','cancelled','failed'))
              OR (prior.status='in_progress' AND NEW.status IN ('completed','cancelled','failed')))
        )
    )
)
BEGIN
    SELECT RAISE(ABORT, 'invalid service state or revision');
END;

CREATE TRIGGER c_service_history_no_update
BEFORE UPDATE ON c_service_history
BEGIN
    SELECT RAISE(ABORT, 'service history is immutable');
END;

CREATE TRIGGER c_service_history_no_delete
BEFORE DELETE ON c_service_history
BEGIN
    SELECT RAISE(ABORT, 'service history is immutable');
END;

CREATE TABLE c_service_dispatches (
    dispatch_id TEXT PRIMARY KEY NOT NULL,
    service_id TEXT NOT NULL UNIQUE REFERENCES c_services(service_id),
    task_id TEXT NOT NULL UNIQUE REFERENCES a_tasks(task_id),
    execution_id TEXT NOT NULL UNIQUE REFERENCES a_executions(execution_id),
    provider_id TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('mock_submission','mock_provider_receipt')),
    recorded_at TEXT NOT NULL
) STRICT;

CREATE TABLE c_service_provider_receipts (
    provider_id TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    service_id TEXT NOT NULL REFERENCES c_services(service_id),
    request_fingerprint TEXT NOT NULL,
    input_json TEXT NOT NULL CHECK (json_valid(input_json)),
    acknowledgement_json TEXT NOT NULL CHECK (json_valid(acknowledgement_json)),
    PRIMARY KEY (provider_id, provider_event_id)
) STRICT;
