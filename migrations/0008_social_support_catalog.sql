CREATE TABLE c_support_resource_versions (
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    previous_version TEXT,
    recorded_at TEXT NOT NULL,
    fixture_source TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status = 'not_reviewed'),
    resource_json TEXT NOT NULL CHECK (
        json_valid(resource_json)
        AND json_extract(resource_json, '$.resource_id') IS resource_id
        AND json_extract(resource_json, '$.resource_version') IS resource_version
        AND json_type(resource_json, '$.is_simulated') IS 'true'
        AND json_type(resource_json, '$.provider.is_simulated') IS 'true'
    ),
    profile_types_json TEXT NOT NULL CHECK (
        json_valid(profile_types_json) AND json_type(profile_types_json) = 'array'
    ),
    PRIMARY KEY (resource_id, resource_version),
    FOREIGN KEY (resource_id, previous_version)
        REFERENCES c_support_resource_versions (resource_id, resource_version),
    CHECK (previous_version IS NULL OR previous_version <> resource_version)
) STRICT;

CREATE TABLE c_support_resources (
    resource_id TEXT PRIMARY KEY NOT NULL,
    current_version TEXT NOT NULL,
    FOREIGN KEY (resource_id, current_version)
        REFERENCES c_support_resource_versions (resource_id, resource_version)
) STRICT;

CREATE TRIGGER c_support_resource_version_no_update
BEFORE UPDATE ON c_support_resource_versions
BEGIN
    SELECT RAISE(ABORT, 'support resource version is immutable');
END;

CREATE TRIGGER c_support_resource_version_no_delete
BEFORE DELETE ON c_support_resource_versions
BEGIN
    SELECT RAISE(ABORT, 'support resource version is immutable');
END;
