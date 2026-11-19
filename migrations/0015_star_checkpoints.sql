CREATE TABLE b_star_checkpoints (
    generation_id TEXT PRIMARY KEY NOT NULL REFERENCES b_generations(generation_id),
    document_json TEXT NOT NULL CHECK(json_valid(document_json))
) STRICT;
