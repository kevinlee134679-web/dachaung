INSERT INTO a_task_history (task_id, revision, document_json)
SELECT task_id, json_extract(document_json, '$.meta.revision') + 1,
    json_set(document_json,
        '$.status', 'cancelled',
        '$.cancellation_requested', json('true'),
        '$.next_attempt_at', NULL,
        '$.failure_reason', 'Analytics refresh tasks have been removed',
        '$.meta.revision', json_extract(document_json, '$.meta.revision') + 1,
        '$.meta.updated_at', strftime('%Y-%m-%dT%H:%M:%f000+00:00', 'now'))
FROM a_tasks
WHERE json_extract(document_json, '$.kind') IN ('refresh_statistics', 'refresh_summary')
    AND json_extract(document_json, '$.status') NOT IN ('succeeded', 'failed', 'cancelled', 'expired');

UPDATE a_tasks
SET document_json = (
    SELECT document_json FROM a_task_history
    WHERE a_task_history.task_id = a_tasks.task_id
        AND revision = json_extract(a_tasks.document_json, '$.meta.revision') + 1
)
WHERE json_extract(document_json, '$.kind') IN ('refresh_statistics', 'refresh_summary')
    AND json_extract(document_json, '$.status') NOT IN ('succeeded', 'failed', 'cancelled', 'expired');

DROP TABLE s03_invalidations;
DROP TABLE s03_results;
DROP TABLE s03_computation_snapshots;
DROP TABLE change_notices;
