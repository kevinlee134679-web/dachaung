-- Rebuild the ledger and its two dependent evidence tables in the common migration transaction.
DROP TRIGGER c_points_ledger_balance;
DROP TRIGGER c_points_ledger_no_update;
DROP TRIGGER c_points_ledger_no_delete;
DROP TRIGGER c_points_award_sources_no_update;
DROP TRIGGER c_points_award_sources_no_delete;
DROP TRIGGER c_points_date_allocations_no_update;
DROP TRIGGER c_points_date_allocations_no_delete;
DROP INDEX c_points_ledger_by_time;

ALTER TABLE c_points_award_sources RENAME TO c_points_award_sources_0013;
ALTER TABLE c_points_date_allocations RENAME TO c_points_date_allocations_0013;
ALTER TABLE c_points_ledger RENAME TO c_points_ledger_0013;

CREATE TABLE c_reward_versions (
    reward_id TEXT NOT NULL,
    reward_version TEXT NOT NULL,
    previous_version TEXT,
    registered_at TEXT NOT NULL,
    reward_json TEXT NOT NULL CHECK (json_valid(reward_json)),
    template_text TEXT,
    resource_version TEXT,
    PRIMARY KEY (reward_id,reward_version),
    FOREIGN KEY (reward_id,previous_version) REFERENCES c_reward_versions(reward_id,reward_version)
) STRICT;

CREATE TABLE c_rewards (
    reward_id TEXT PRIMARY KEY NOT NULL,
    current_version TEXT NOT NULL,
    FOREIGN KEY (reward_id,current_version) REFERENCES c_reward_versions(reward_id,reward_version)
) STRICT;

CREATE TABLE c_redemptions (
    redemption_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL REFERENCES c_points_accounts(patient_id),
    reward_id TEXT NOT NULL,
    reward_version TEXT NOT NULL,
    debit_ledger_id TEXT NOT NULL UNIQUE REFERENCES c_points_ledger(ledger_id) DEFERRABLE INITIALLY DEFERRED,
    service_id TEXT UNIQUE REFERENCES c_services(service_id),
    fulfillment_id TEXT NOT NULL UNIQUE,
    redeemed_at TEXT NOT NULL,
    account_revision INTEGER NOT NULL CHECK (account_revision>=1),
    request_fingerprint TEXT NOT NULL,
    UNIQUE (patient_id,account_revision),
    UNIQUE (redemption_id,fulfillment_id),
    FOREIGN KEY (reward_id,reward_version) REFERENCES c_reward_versions(reward_id,reward_version),
    FOREIGN KEY (fulfillment_id) REFERENCES c_reward_fulfillments(fulfillment_id) DEFERRABLE INITIALLY DEFERRED
) STRICT;

CREATE INDEX c_redemptions_by_time ON c_redemptions(patient_id,redeemed_at,redemption_id);

CREATE TABLE c_reward_fulfillments (
    fulfillment_id TEXT PRIMARY KEY NOT NULL,
    redemption_id TEXT NOT NULL UNIQUE,
    task_id TEXT NOT NULL UNIQUE REFERENCES a_tasks(task_id) DEFERRABLE INITIALLY DEFERRED,
    FOREIGN KEY (redemption_id,fulfillment_id) REFERENCES c_redemptions(redemption_id,fulfillment_id)
) STRICT;

CREATE TABLE c_redemption_history (
    redemption_id TEXT NOT NULL REFERENCES c_redemptions(redemption_id),
    revision INTEGER NOT NULL CHECK (revision>=1),
    recorded_at TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    origin TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    redemption_json TEXT NOT NULL CHECK (json_valid(redemption_json)),
    fulfillment_json TEXT NOT NULL CHECK (json_valid(fulfillment_json)),
    PRIMARY KEY (redemption_id,revision)
) STRICT;

CREATE TABLE c_fulfillment_receipts (
    subject TEXT NOT NULL,
    provider_event_id TEXT NOT NULL,
    fulfillment_id TEXT NOT NULL REFERENCES c_reward_fulfillments(fulfillment_id),
    request_fingerprint TEXT NOT NULL,
    operation_id TEXT NOT NULL UNIQUE REFERENCES operation_audit(operation_id),
    ack_json TEXT NOT NULL CHECK (json_valid(ack_json)),
    PRIMARY KEY (subject,provider_event_id)
) STRICT;

CREATE TABLE c_redemption_feedback (
    feedback_id TEXT PRIMARY KEY NOT NULL,
    redemption_id TEXT NOT NULL REFERENCES c_redemptions(redemption_id),
    client_feedback_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    document_json TEXT NOT NULL CHECK (json_valid(document_json)),
    UNIQUE (redemption_id,client_feedback_id)
) STRICT;

CREATE TABLE c_redemption_notices (
    redemption_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    PRIMARY KEY (redemption_id,revision),
    FOREIGN KEY (redemption_id,revision) REFERENCES c_redemption_history(redemption_id,revision)
) STRICT;

CREATE TABLE c_points_ledger (
    ledger_id TEXT PRIMARY KEY NOT NULL,
    points_account_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    operation_id TEXT NOT NULL REFERENCES operation_audit(operation_id),
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('award','redemption_debit','redemption_refund')),
    delta INTEGER NOT NULL,
    balance_after INTEGER NOT NULL CHECK (balance_after>=0),
    business_key TEXT NOT NULL CHECK (length(business_key) BETWEEN 1 AND 200),
    rule_code TEXT CHECK (rule_code IN ('daily_record','five_day_block','weekly_review','peer_participation')),
    period_start TEXT,
    rules_version TEXT,
    created_at TEXT NOT NULL,
    redemption_id TEXT REFERENCES c_redemptions(redemption_id) DEFERRABLE INITIALLY DEFERRED,
    reverses_ledger_id TEXT UNIQUE REFERENCES c_points_ledger(ledger_id),
    CHECK ((entry_kind='award' AND delta>0 AND rule_code IS NOT NULL AND period_start IS NOT NULL
            AND rules_version IS NOT NULL AND redemption_id IS NULL AND reverses_ledger_id IS NULL)
        OR (entry_kind='redemption_debit' AND delta<0 AND rule_code IS NULL AND period_start IS NULL
            AND rules_version IS NULL AND redemption_id IS NOT NULL AND reverses_ledger_id IS NULL)
        OR (entry_kind='redemption_refund' AND delta>0 AND rule_code IS NULL AND period_start IS NULL
            AND rules_version IS NULL AND redemption_id IS NOT NULL AND reverses_ledger_id IS NOT NULL)),
    UNIQUE (redemption_id,entry_kind),
    UNIQUE (patient_id,business_key),
    UNIQUE (patient_id,rule_code,period_start),
    UNIQUE (ledger_id,patient_id,rule_code),
    FOREIGN KEY (points_account_id,patient_id) REFERENCES c_points_accounts(points_account_id,patient_id)
) STRICT;

CREATE INDEX c_points_ledger_by_time ON c_points_ledger(patient_id,created_at,ledger_id);

CREATE TABLE c_points_award_sources (
    ledger_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    rule_code TEXT NOT NULL,
    module TEXT NOT NULL,
    record_kind TEXT NOT NULL,
    record_id TEXT NOT NULL,
    source_revision INTEGER NOT NULL CHECK (source_revision>=1),
    recorded_at TEXT NOT NULL,
    anchor_at TEXT NOT NULL,
    qualification_ref TEXT,
    source_order INTEGER NOT NULL CHECK (source_order>=1),
    CHECK ((module='A' AND record_kind='event' AND rule_code IN ('daily_record','five_day_block'))
        OR (module='C' AND record_kind='management_review' AND rule_code='weekly_review')
        OR (module='C' AND record_kind='peer_post' AND rule_code='peer_participation')),
    PRIMARY KEY (ledger_id,source_order),
    UNIQUE (patient_id,rule_code,module,record_kind,record_id),
    FOREIGN KEY (ledger_id,patient_id,rule_code) REFERENCES c_points_ledger(ledger_id,patient_id,rule_code)
) STRICT;

CREATE TABLE c_points_date_allocations (
    allocation_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    rule_code TEXT NOT NULL CHECK (rule_code='five_day_block'),
    local_date TEXT NOT NULL,
    ledger_id TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    assigned_at TEXT NOT NULL,
    UNIQUE (patient_id,rule_code,local_date),
    FOREIGN KEY (ledger_id,patient_id,rule_code) REFERENCES c_points_ledger(ledger_id,patient_id,rule_code)
) STRICT;

INSERT INTO c_points_ledger
    (ledger_id,points_account_id,patient_id,operation_id,entry_kind,delta,balance_after,
     business_key,rule_code,period_start,rules_version,created_at)
SELECT * FROM c_points_ledger_0013 ORDER BY rowid;
INSERT INTO c_points_award_sources SELECT * FROM c_points_award_sources_0013 ORDER BY rowid;
INSERT INTO c_points_date_allocations SELECT * FROM c_points_date_allocations_0013 ORDER BY rowid;

DROP TABLE c_points_award_sources_0013;
DROP TABLE c_points_date_allocations_0013;
DROP TABLE c_points_ledger_0013;

CREATE TRIGGER c_points_ledger_award_audit BEFORE INSERT ON c_points_ledger
WHEN NEW.entry_kind='award' AND NOT EXISTS (
    SELECT 1 FROM c_points_reconciliations WHERE operation_id=NEW.operation_id AND patient_id=NEW.patient_id
)
BEGIN SELECT RAISE(ABORT, 'points award requires its reconciliation'); END;

CREATE TRIGGER c_points_ledger_no_replace BEFORE INSERT ON c_points_ledger
WHEN EXISTS (
    SELECT 1 FROM c_points_ledger l WHERE l.ledger_id=NEW.ledger_id
       OR (l.patient_id=NEW.patient_id AND (l.business_key=NEW.business_key
          OR (l.rule_code=NEW.rule_code AND l.period_start=NEW.period_start)))
       OR (l.redemption_id=NEW.redemption_id AND l.entry_kind=NEW.entry_kind)
       OR l.reverses_ledger_id=NEW.reverses_ledger_id
)
BEGIN SELECT RAISE(ABORT, 'UNIQUE points ledger entries cannot be replaced'); END;

CREATE TRIGGER c_points_ledger_debit_order BEFORE INSERT ON c_points_ledger
WHEN NEW.entry_kind='redemption_debit' AND NOT EXISTS (
    SELECT 1 FROM c_redemptions r JOIN c_reward_versions v USING(reward_id,reward_version)
    WHERE r.redemption_id=NEW.redemption_id AND r.patient_id=NEW.patient_id
      AND r.debit_ledger_id=NEW.ledger_id AND json_extract(v.reward_json,'$.points_cost')=-NEW.delta
)
BEGIN SELECT RAISE(ABORT, 'points debit requires the exact redemption cost'); END;

CREATE TRIGGER c_points_ledger_refund_original BEFORE INSERT ON c_points_ledger
WHEN NEW.entry_kind='redemption_refund' AND NOT EXISTS (
    SELECT 1 FROM c_redemptions r JOIN c_points_ledger d ON d.ledger_id=r.debit_ledger_id
    JOIN c_redemption_history h ON h.redemption_id=r.redemption_id
    WHERE r.redemption_id=NEW.redemption_id AND d.ledger_id=NEW.reverses_ledger_id
      AND d.entry_kind='redemption_debit' AND d.points_account_id=NEW.points_account_id
      AND d.patient_id=NEW.patient_id AND NEW.delta=-d.delta
      AND NEW.business_key='refund:'||r.redemption_id
      AND h.revision=(SELECT MAX(revision) FROM c_redemption_history WHERE redemption_id=r.redemption_id)
      AND h.origin IN ('provider_receipt','c_service')
      AND json_extract(h.fulfillment_json,'$.status') IN ('failed','cancelled')
      AND json_type(h.fulfillment_json,'$.artifact')='null'
      AND json_extract(h.redemption_json,'$.refund_ledger_id')=NEW.ledger_id
)
BEGIN SELECT RAISE(ABORT, 'points refund requires the original exact debit'); END;

CREATE TRIGGER c_points_ledger_balance BEFORE INSERT ON c_points_ledger
WHEN NEW.balance_after != NEW.delta+COALESCE(
    (SELECT SUM(delta) FROM c_points_ledger WHERE points_account_id=NEW.points_account_id),0)
BEGIN SELECT RAISE(ABORT, 'incorrect points balance'); END;

CREATE TRIGGER c_points_ledger_no_update BEFORE UPDATE ON c_points_ledger
BEGIN SELECT RAISE(ABORT, 'points ledger is immutable'); END;
CREATE TRIGGER c_points_ledger_no_delete BEFORE DELETE ON c_points_ledger
BEGIN SELECT RAISE(ABORT, 'points ledger is immutable'); END;
CREATE TRIGGER c_points_award_sources_no_update BEFORE UPDATE ON c_points_award_sources
BEGIN SELECT RAISE(ABORT, 'points award sources are immutable'); END;
CREATE TRIGGER c_points_award_sources_no_delete BEFORE DELETE ON c_points_award_sources
BEGIN SELECT RAISE(ABORT, 'points award sources are immutable'); END;
CREATE TRIGGER c_points_date_allocations_no_update BEFORE UPDATE ON c_points_date_allocations
BEGIN SELECT RAISE(ABORT, 'points date allocations are immutable'); END;
CREATE TRIGGER c_points_date_allocations_no_delete BEFORE DELETE ON c_points_date_allocations
BEGIN SELECT RAISE(ABORT, 'points date allocations are immutable'); END;
CREATE TRIGGER c_reward_versions_no_update BEFORE UPDATE ON c_reward_versions
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_reward_versions_no_delete BEFORE DELETE ON c_reward_versions
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemptions_no_update BEFORE UPDATE ON c_redemptions
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemptions_no_delete BEFORE DELETE ON c_redemptions
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_reward_fulfillments_no_update BEFORE UPDATE ON c_reward_fulfillments
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_reward_fulfillments_no_delete BEFORE DELETE ON c_reward_fulfillments
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemption_history_no_update BEFORE UPDATE ON c_redemption_history
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemption_history_no_delete BEFORE DELETE ON c_redemption_history
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_fulfillment_receipts_no_update BEFORE UPDATE ON c_fulfillment_receipts
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_fulfillment_receipts_no_delete BEFORE DELETE ON c_fulfillment_receipts
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemption_feedback_no_update BEFORE UPDATE ON c_redemption_feedback
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemption_feedback_no_delete BEFORE DELETE ON c_redemption_feedback
BEGIN SELECT RAISE(ABORT, 'redemption history is immutable'); END;
CREATE TRIGGER c_redemption_notices_no_update BEFORE UPDATE ON c_redemption_notices
BEGIN SELECT RAISE(ABORT, 'redemption notices are immutable'); END;
CREATE TRIGGER c_redemption_notices_no_delete BEFORE DELETE ON c_redemption_notices
BEGIN SELECT RAISE(ABORT, 'redemption notices are immutable'); END;
