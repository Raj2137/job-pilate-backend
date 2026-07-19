ALTER TABLE user_resumes
    ADD COLUMN IF NOT EXISTS original_file_size INTEGER,
    ADD COLUMN IF NOT EXISTS original_file_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS original_storage_provider VARCHAR(50),
    ADD COLUMN IF NOT EXISTS original_storage_key VARCHAR(500),
    ADD COLUMN IF NOT EXISTS original_file_data BYTEA;

ALTER TABLE tailored_resumes
    ADD COLUMN IF NOT EXISTS requested_render_mode VARCHAR(32) NOT NULL DEFAULT 'auto',
    ADD COLUMN IF NOT EXISTS actual_render_mode VARCHAR(32) NOT NULL DEFAULT 'ats',
    ADD COLUMN IF NOT EXISTS template_fidelity VARCHAR(32) NOT NULL DEFAULT 'standardized';
