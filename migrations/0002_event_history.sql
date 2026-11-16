CREATE TABLE event_revisions (
    event_id TEXT NOT NULL REFERENCES source_events(event_id),
    revision INTEGER NOT NULL CHECK(revision > 0),
    change_kind TEXT NOT NULL CHECK(change_kind IN ('original','correction','withdrawal')),
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL CHECK(json_valid(payload_json) AND json_type(payload_json)='object'),
    reason TEXT,
    replaces_revision INTEGER,
    actor_account_id TEXT,
    created_at TEXT NOT NULL,
    is_simulated INTEGER NOT NULL CHECK(is_simulated IN (0,1)),
    CHECK((change_kind='original' AND revision=1 AND replaces_revision IS NULL)
       OR (change_kind IN ('correction','withdrawal') AND revision>1 AND replaces_revision IS NOT NULL AND replaces_revision<revision AND length(trim(reason))>0 AND reason IS NOT NULL)),
    PRIMARY KEY(event_id, revision),
    FOREIGN KEY(event_id, is_simulated) REFERENCES source_events(event_id, is_simulated),
    FOREIGN KEY(event_id, replaces_revision) REFERENCES event_revisions(event_id, revision)
) STRICT;
INSERT INTO event_revisions
    SELECT event_id, 1, 'original', occurred_at, original_payload_json, NULL, NULL,
           reporter_account_id, received_at, is_simulated FROM source_events;
CREATE TABLE evidence_slot_links (
    event_id TEXT NOT NULL,
    event_revision INTEGER NOT NULL,
    patient_id TEXT NOT NULL,
    data_environment TEXT NOT NULL,
    dose_slot_id TEXT NOT NULL,
    PRIMARY KEY(event_id, event_revision),
    FOREIGN KEY(event_id, event_revision) REFERENCES event_revisions(event_id, revision),
    FOREIGN KEY(patient_id, data_environment, event_id) REFERENCES source_events(patient_id, data_environment, event_id),
    FOREIGN KEY(patient_id, data_environment, dose_slot_id) REFERENCES dose_slots(patient_id, data_environment, dose_slot_id)
) STRICT;
CREATE INDEX evidence_links_slot ON evidence_slot_links(patient_id, data_environment, dose_slot_id);
