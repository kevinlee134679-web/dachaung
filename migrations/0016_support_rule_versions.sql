CREATE TABLE b_rule_versions (
    version TEXT PRIMARY KEY NOT NULL,
    profile_id TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal>=1),
    content_hash TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    registered_at TEXT NOT NULL,
    UNIQUE(profile_id, ordinal)
) STRICT;
CREATE TABLE b_rule_selection (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    version TEXT NOT NULL REFERENCES b_rule_versions(version),
    revision INTEGER NOT NULL CHECK(revision>=1),
    selected_at TEXT NOT NULL
) STRICT;
CREATE TABLE b_rule_selection_history (
    selection_id TEXT PRIMARY KEY NOT NULL,
    previous_version TEXT,
    selected_version TEXT NOT NULL REFERENCES b_rule_versions(version),
    revision INTEGER NOT NULL UNIQUE CHECK(revision>=1),
    cancelled_invitations INTEGER NOT NULL CHECK(cancelled_invitations>=0),
    selected_by TEXT NOT NULL,
    selected_at TEXT NOT NULL
) STRICT;
