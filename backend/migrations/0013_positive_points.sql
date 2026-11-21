CREATE TABLE c_points_accounts (
    points_account_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL UNIQUE,
    revision INTEGER NOT NULL CHECK (revision>=1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (points_account_id,patient_id)
) STRICT;

CREATE TABLE c_management_reviews (
    review_id TEXT PRIMARY KEY NOT NULL,
    patient_id TEXT NOT NULL,
    actor_account_id TEXT NOT NULL REFERENCES o_accounts(account_id),
    week_start TEXT NOT NULL,
    client_review_id TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    reflection TEXT,
    completed_at TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    UNIQUE (patient_id,week_start),
    UNIQUE (patient_id,client_review_id)
) STRICT;

CREATE TABLE c_points_reconciliations (
    operation_id TEXT PRIMARY KEY NOT NULL REFERENCES operation_audit(operation_id),
    patient_id TEXT NOT NULL REFERENCES c_points_accounts(patient_id),
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL CHECK (window_end>window_start),
    rules_version TEXT NOT NULL,
    source_issues_json TEXT NOT NULL CHECK (json_valid(source_issues_json) AND json_type(source_issues_json)='array'),
    source_changes_json TEXT NOT NULL CHECK (json_valid(source_changes_json) AND json_type(source_changes_json)='array')
) STRICT;

CREATE TABLE c_points_ledger (
    ledger_id TEXT PRIMARY KEY NOT NULL,
    points_account_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    operation_id TEXT NOT NULL REFERENCES c_points_reconciliations(operation_id),
    entry_kind TEXT NOT NULL CHECK (entry_kind='award'),
    delta INTEGER NOT NULL CHECK (delta>0),
    balance_after INTEGER NOT NULL CHECK (balance_after>=0),
    business_key TEXT NOT NULL CHECK (length(business_key) BETWEEN 1 AND 200),
    rule_code TEXT NOT NULL CHECK (rule_code IN ('daily_record','five_day_block','weekly_review','peer_participation')),
    period_start TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
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
CREATE TRIGGER c_management_reviews_no_update BEFORE UPDATE ON c_management_reviews
BEGIN SELECT RAISE(ABORT, 'management reviews are immutable'); END;
CREATE TRIGGER c_management_reviews_no_delete BEFORE DELETE ON c_management_reviews
BEGIN SELECT RAISE(ABORT, 'management reviews are immutable'); END;
CREATE TRIGGER c_points_reconciliations_no_update BEFORE UPDATE ON c_points_reconciliations
BEGIN SELECT RAISE(ABORT, 'points audit is immutable'); END;
CREATE TRIGGER c_points_reconciliations_no_delete BEFORE DELETE ON c_points_reconciliations
BEGIN SELECT RAISE(ABORT, 'points audit is immutable'); END;
