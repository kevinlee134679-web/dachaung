CREATE TABLE c_service_feedback (
    feedback_id TEXT PRIMARY KEY NOT NULL,
    service_id TEXT NOT NULL REFERENCES c_services(service_id),
    feedback_revision INTEGER NOT NULL CHECK (feedback_revision >= 1),
    supersedes_feedback_id TEXT REFERENCES c_service_feedback(feedback_id),
    client_feedback_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK (json_valid(document_json) AND json_type(document_json)='object'
        AND json_extract(document_json,'$.feedback_id') IS feedback_id
        AND json_extract(document_json,'$.service_id') IS service_id
        AND json_extract(document_json,'$.feedback_revision') IS feedback_revision
        AND json_extract(document_json,'$.supersedes_feedback_id') IS supersedes_feedback_id
        AND json_extract(document_json,'$.recorded_at') IS recorded_at),
    UNIQUE (service_id, feedback_revision),
    UNIQUE (service_id, client_feedback_id)
) STRICT;

CREATE TRIGGER c_service_feedback_append_only_chain
BEFORE INSERT ON c_service_feedback
WHEN NOT (
    (NEW.feedback_revision=1 AND NEW.supersedes_feedback_id IS NULL
        AND NOT EXISTS (SELECT 1 FROM c_service_feedback WHERE service_id=NEW.service_id))
    OR EXISTS (
        SELECT 1 FROM c_service_feedback prior
        WHERE prior.service_id=NEW.service_id AND prior.feedback_id=NEW.supersedes_feedback_id
          AND prior.feedback_revision=NEW.feedback_revision-1 AND prior.recorded_at<=NEW.recorded_at
    )
)
BEGIN
    SELECT RAISE(ABORT, 'invalid feedback predecessor');
END;

CREATE TRIGGER c_service_feedback_no_update BEFORE UPDATE ON c_service_feedback
BEGIN
    SELECT RAISE(ABORT, 'feedback revisions are immutable');
END;

CREATE TRIGGER c_service_feedback_no_delete BEFORE DELETE ON c_service_feedback
BEGIN
    SELECT RAISE(ABORT, 'feedback revisions are immutable');
END;
