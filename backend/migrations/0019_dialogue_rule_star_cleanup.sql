CREATE TABLE b_support_rule (
    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
    profile_id TEXT NOT NULL CHECK(profile_id IN ('support-default','support-explicit-needs'))
) STRICT;
INSERT INTO b_support_rule
SELECT 1, CASE WHEN json_extract(v.document_json,'$.state_events') THEN 'support-explicit-needs' ELSE 'support-default' END
FROM b_rule_selection s JOIN b_rule_versions v ON v.version=s.version;
DROP TABLE b_rule_selection_history;
DROP TABLE b_rule_selection;
DROP TABLE b_rule_versions;
DROP TABLE b_star_checkpoints;
DROP TABLE b_model_selection;
DROP TABLE b_intervention_revisions;
UPDATE b_generations SET document_json=json_remove(
    json_set(document_json,'$.deadline_at',json_extract(document_json,'$.budget.deadline_at')),
    '$.budget','$.requested_pipeline','$.actual_pipeline','$.fallback_reason'
)
WHERE json_type(document_json,'$.budget') IS NOT NULL;
