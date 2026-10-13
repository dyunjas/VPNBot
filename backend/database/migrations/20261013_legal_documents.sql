-- Optional explicit migration. init_db() also creates this table on API startup.
-- Existing HTML files remain the source until a document is first saved in admin.
CREATE TABLE IF NOT EXISTS vpn_legal_documents (
    key VARCHAR(32) PRIMARY KEY,
    html TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
