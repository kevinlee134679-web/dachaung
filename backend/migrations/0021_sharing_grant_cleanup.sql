UPDATE o_sharing_scopes SET document_json=json_remove(document_json, '$.related_grant_ids');
ALTER TABLE o_sharing_scopes DROP COLUMN grant_versions_json;
