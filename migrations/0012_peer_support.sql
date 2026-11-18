CREATE TABLE c_peer_groups (
    group_id TEXT PRIMARY KEY NOT NULL,
    resource_id TEXT NOT NULL UNIQUE REFERENCES c_support_resources(resource_id),
    document_json TEXT NOT NULL CHECK (json_valid(document_json) AND json_type(document_json)='object'
        AND json_extract(document_json,'$.group_id') IS group_id
        AND json_extract(document_json,'$.resource_id') IS resource_id)
) STRICT;

CREATE TABLE c_peer_moderators (
    group_id TEXT NOT NULL REFERENCES c_peer_groups(group_id),
    account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    PRIMARY KEY (group_id, account_id)
) STRICT;

CREATE UNIQUE INDEX c_services_patient_identity ON c_services(service_id,patient_id);

CREATE TABLE c_peer_memberships (
    membership_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    group_id TEXT NOT NULL REFERENCES c_peer_groups(group_id),
    service_id TEXT NOT NULL UNIQUE,
    alias TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','active','left')),
    revision INTEGER NOT NULL CHECK (revision >= 1),
    UNIQUE (group_id,alias),
    UNIQUE (membership_id,group_id),
    FOREIGN KEY (service_id,patient_id) REFERENCES c_services(service_id,patient_id)
) STRICT;

CREATE UNIQUE INDEX c_peer_membership_open ON c_peer_memberships(patient_id,group_id) WHERE status IN ('pending','active');

CREATE TABLE c_peer_membership_history (
    membership_id TEXT NOT NULL REFERENCES c_peer_memberships(membership_id),
    revision INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','active','left')),
    actor_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK (json_valid(document_json)
        AND json_extract(document_json,'$.membership_id') IS membership_id
        AND json_extract(document_json,'$.meta.revision') IS revision
        AND json_extract(document_json,'$.status') IS status),
    PRIMARY KEY (membership_id,revision)
) STRICT;

CREATE TABLE c_peer_posts (
    post_id TEXT PRIMARY KEY NOT NULL,
    group_id TEXT NOT NULL,
    membership_id TEXT NOT NULL,
    client_post_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    content TEXT NOT NULL CHECK (length(content) BETWEEN 1 AND 1000),
    created_at TEXT NOT NULL,
    UNIQUE (membership_id,client_post_id),
    FOREIGN KEY (membership_id,group_id) REFERENCES c_peer_memberships(membership_id,group_id)
) STRICT;

CREATE INDEX c_peer_posts_by_group ON c_peer_posts(group_id,created_at,post_id);

CREATE TABLE c_peer_post_history (
    post_id TEXT NOT NULL REFERENCES c_peer_posts(post_id),
    revision INTEGER NOT NULL CHECK (revision>=1),
    status TEXT NOT NULL CHECK (status IN ('pending','visible','hidden')),
    actor_id TEXT NOT NULL,
    reason TEXT,
    recorded_at TEXT NOT NULL,
    CHECK ((revision=1 AND status='pending' AND reason IS NULL)
        OR (revision>1 AND status IN ('visible','hidden') AND reason IS NOT NULL)),
    PRIMARY KEY (post_id,revision)
) STRICT;

CREATE TRIGGER c_peer_membership_history_no_update BEFORE UPDATE ON c_peer_membership_history
BEGIN SELECT RAISE(ABORT, 'membership history is immutable'); END;
CREATE TRIGGER c_peer_membership_history_no_delete BEFORE DELETE ON c_peer_membership_history
BEGIN SELECT RAISE(ABORT, 'membership history is immutable'); END;
CREATE TRIGGER c_peer_posts_no_update BEFORE UPDATE ON c_peer_posts
BEGIN SELECT RAISE(ABORT, 'post origin is immutable'); END;
CREATE TRIGGER c_peer_posts_no_delete BEFORE DELETE ON c_peer_posts
BEGIN SELECT RAISE(ABORT, 'post origin is immutable'); END;
CREATE TRIGGER c_peer_post_history_no_update BEFORE UPDATE ON c_peer_post_history
BEGIN SELECT RAISE(ABORT, 'post history is immutable'); END;
CREATE TRIGGER c_peer_post_history_no_delete BEFORE DELETE ON c_peer_post_history
BEGIN SELECT RAISE(ABORT, 'post history is immutable'); END;
