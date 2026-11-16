CREATE TABLE s03_computation_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL CHECK(data_environment IN ('demo','real')),
    as_of TEXT NOT NULL,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL CHECK(window_end>window_start),
    source_refs TEXT NOT NULL CHECK(json_valid(source_refs) AND json_type(source_refs)='array'),
    authorization_context_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;
CREATE TABLE s03_results (
    result_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('statistics','summary')),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    as_of TEXT NOT NULL,
    authorization_context_hash TEXT NOT NULL,
    input_signature TEXT NOT NULL,
    snapshot_id TEXT NOT NULL REFERENCES s03_computation_snapshots(snapshot_id),
    result_json TEXT NOT NULL CHECK(json_valid(result_json) AND json_type(result_json)='object'),
    trend_json TEXT CHECK(trend_json IS NULL OR json_valid(trend_json)),
    created_at TEXT NOT NULL
) STRICT;
CREATE INDEX s03_results_lookup ON s03_results(patient_id,data_environment,kind,window_start,window_end,authorization_context_hash,as_of,created_at);
CREATE TABLE s03_invalidations (
    notice_id TEXT PRIMARY KEY REFERENCES change_notices(notice_id),
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL
) STRICT;
