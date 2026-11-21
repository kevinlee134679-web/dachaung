CREATE TABLE b_sessions (
    session_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    case_id TEXT,
    invitation_id TEXT UNIQUE,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    UNIQUE(session_id, patient_id)
) STRICT;
CREATE INDEX b_sessions_patient ON b_sessions(patient_id, case_id);

CREATE TABLE b_messages (
    message_id TEXT PRIMARY KEY NOT NULL,
    session_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    client_message_id TEXT,
    source_message_id TEXT UNIQUE REFERENCES b_messages(message_id),
    request_fingerprint TEXT,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    FOREIGN KEY(session_id, patient_id) REFERENCES b_sessions(session_id, patient_id),
    UNIQUE(session_id, client_message_id),
    CHECK((client_message_id IS NOT NULL AND source_message_id IS NULL AND request_fingerprint IS NOT NULL)
       OR (client_message_id IS NULL AND source_message_id IS NOT NULL AND request_fingerprint IS NULL))
) STRICT;

CREATE TABLE b_generations (
    generation_id TEXT PRIMARY KEY NOT NULL,
    user_message_id TEXT NOT NULL UNIQUE REFERENCES b_messages(message_id),
    run_number INTEGER NOT NULL CHECK(run_number >= 1),
    scenario TEXT,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    output_json TEXT CHECK(output_json IS NULL OR json_valid(output_json))
) STRICT;

CREATE TABLE b_generation_runs (
    generation_id TEXT NOT NULL REFERENCES b_generations(generation_id),
    run_number INTEGER NOT NULL CHECK(run_number >= 1),
    outcome TEXT NOT NULL CHECK(outcome IN ('accepted','running','completed','failed','cancelled','outcome_unknown')),
    PRIMARY KEY(generation_id, run_number)
) STRICT;

CREATE TABLE b_records (
    kind TEXT NOT NULL CHECK(kind IN ('Assessment','UIState','ModeChange','Invitation','InvitationResponse',
        'Intervention','Suggestion','SuggestionResponse','DisplayReceipt','Referral','Integration',
        'ScenarioRun','CheckinNode','Retrieval','Probe','Reset')),
    record_id TEXT NOT NULL,
    patient_id TEXT,
    session_id TEXT,
    source_key TEXT,
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    PRIMARY KEY(kind, record_id),
    UNIQUE(kind, source_key),
    FOREIGN KEY(session_id, patient_id) REFERENCES b_sessions(session_id, patient_id),
    CHECK(session_id IS NULL OR patient_id IS NOT NULL)
) STRICT;
CREATE INDEX b_records_patient ON b_records(kind, patient_id, session_id);

CREATE TABLE b_intervention_revisions (
    intervention_id TEXT PRIMARY KEY NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    updated_at TEXT NOT NULL
) STRICT;

CREATE TABLE b_knowledge (
    knowledge_id TEXT NOT NULL,
    version TEXT NOT NULL,
    ordinal INTEGER NOT NULL CHECK(ordinal >= 1),
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    PRIMARY KEY(knowledge_id, version),
    UNIQUE(knowledge_id, ordinal)
) STRICT;

CREATE TABLE b_knowledge_history (
    knowledge_id TEXT NOT NULL,
    version TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK(revision >= 1),
    document_json TEXT NOT NULL CHECK(json_valid(document_json)),
    PRIMARY KEY(knowledge_id, version, revision),
    FOREIGN KEY(knowledge_id, version) REFERENCES b_knowledge(knowledge_id, version)
) STRICT;

CREATE TABLE b_model_selection (
    singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
    document_json TEXT NOT NULL CHECK(json_valid(document_json))
) STRICT;
