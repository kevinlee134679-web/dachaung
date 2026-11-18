CREATE TABLE o_demo_support_recipients (
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    recipient_id TEXT NOT NULL,
    recipient_type TEXT NOT NULL CHECK (recipient_type IN ('volunteer','pharmacist')),
    purpose_code TEXT NOT NULL,
    PRIMARY KEY (resource_id, resource_version),
    FOREIGN KEY (resource_id, resource_version)
        REFERENCES c_support_resource_versions (resource_id, resource_version)
) STRICT;

CREATE TABLE o_sharing_scopes (
    sharing_scope_ref_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    scope_version INTEGER NOT NULL CHECK (scope_version >= 1),
    grant_versions_json TEXT NOT NULL CHECK (json_valid(grant_versions_json) AND json_type(grant_versions_json)='object'),
    document_json TEXT NOT NULL CHECK (json_valid(document_json) AND json_type(document_json)='object'),
    UNIQUE (sharing_scope_ref_id, patient_id),
    FOREIGN KEY (resource_id, resource_version)
        REFERENCES o_demo_support_recipients (resource_id, resource_version)
) STRICT;

CREATE TABLE o_sharing_scope_history (
    sharing_scope_ref_id TEXT NOT NULL REFERENCES o_sharing_scopes(sharing_scope_ref_id),
    scope_version INTEGER NOT NULL CHECK (scope_version >= 1),
    document_json TEXT NOT NULL CHECK (json_valid(document_json) AND json_type(document_json)='object'),
    actor_account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    recorded_at TEXT NOT NULL,
    reason TEXT,
    PRIMARY KEY (sharing_scope_ref_id, scope_version)
) STRICT;

CREATE TABLE c_service_drafts (
    service_draft_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL CHECK (draft_revision >= 1),
    revision INTEGER NOT NULL CHECK (revision >= draft_revision),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (service_draft_id, patient_id),
    FOREIGN KEY (service_draft_id, draft_revision)
        REFERENCES c_service_draft_revisions (service_draft_id, draft_revision) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE TABLE c_service_draft_revisions (
    service_draft_id TEXT NOT NULL REFERENCES c_service_drafts(service_draft_id),
    draft_revision INTEGER NOT NULL CHECK (draft_revision >= 1),
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    request_text TEXT NOT NULL CHECK (length(request_text) BETWEEN 1 AND 2000),
    author_account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (service_draft_id, draft_revision),
    FOREIGN KEY (resource_id, resource_version)
        REFERENCES c_support_resource_versions (resource_id, resource_version)
) STRICT;

CREATE TRIGGER c_service_draft_revision_no_update
BEFORE UPDATE ON c_service_draft_revisions
BEGIN
    SELECT RAISE(ABORT, 'draft revision is immutable');
END;

CREATE TRIGGER c_service_draft_revision_no_delete
BEFORE DELETE ON c_service_draft_revisions
BEGIN
    SELECT RAISE(ABORT, 'draft revision is immutable');
END;

CREATE TABLE c_service_confirmations (
    confirmation_ref_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    service_kind TEXT NOT NULL,
    descriptor_hash TEXT NOT NULL CHECK (length(descriptor_hash)=64),
    origin_draft_id TEXT NOT NULL,
    origin_draft_revision INTEGER NOT NULL,
    sharing_scope_ref_id TEXT UNIQUE NOT NULL,
    confirmed_at TEXT NOT NULL,
    valid_until TEXT NOT NULL CHECK (valid_until > confirmed_at),
    UNIQUE (confirmation_ref_id, patient_id),
    FOREIGN KEY (origin_draft_id, patient_id)
        REFERENCES c_service_drafts (service_draft_id, patient_id),
    FOREIGN KEY (origin_draft_id, origin_draft_revision)
        REFERENCES c_service_draft_revisions (service_draft_id, draft_revision),
    FOREIGN KEY (resource_id, resource_version)
        REFERENCES c_support_resource_versions (resource_id, resource_version),
    FOREIGN KEY (sharing_scope_ref_id, patient_id)
        REFERENCES o_sharing_scopes (sharing_scope_ref_id, patient_id)
) STRICT;

CREATE INDEX c_confirmation_reuse
ON c_service_confirmations (patient_id, descriptor_hash, valid_until);

CREATE TABLE c_draft_confirmations (
    patient_id TEXT NOT NULL,
    service_draft_id TEXT NOT NULL,
    draft_revision INTEGER NOT NULL,
    confirmation_ref_id TEXT NOT NULL,
    linked_at TEXT NOT NULL,
    PRIMARY KEY (service_draft_id, draft_revision, confirmation_ref_id),
    FOREIGN KEY (service_draft_id, patient_id)
        REFERENCES c_service_drafts (service_draft_id, patient_id),
    FOREIGN KEY (service_draft_id, draft_revision)
        REFERENCES c_service_draft_revisions (service_draft_id, draft_revision),
    FOREIGN KEY (confirmation_ref_id, patient_id)
        REFERENCES c_service_confirmations (confirmation_ref_id, patient_id)
) STRICT;

CREATE TABLE c_confirmation_revocations (
    confirmation_ref_id TEXT PRIMARY KEY NOT NULL REFERENCES c_service_confirmations(confirmation_ref_id),
    actor_account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    revoked_at TEXT NOT NULL,
    reason TEXT NOT NULL
) STRICT;
