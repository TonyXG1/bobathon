-- Regulatory Radar Database Schema
-- Compatible with both PostgreSQL and SQLite

-- ============================================================================
-- REQUIREMENTS TABLE (Part 1 output)
-- ============================================================================

CREATE TABLE IF NOT EXISTS requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    update_id VARCHAR(50) UNIQUE NOT NULL,
    published_date DATE NOT NULL,
    source VARCHAR(100) NOT NULL,
    source_url TEXT NOT NULL,
    celex VARCHAR(50),
    consolidation_date DATE,
    access_timestamp TIMESTAMP NOT NULL,
    regulation_family VARCHAR(50) NOT NULL,
    reference TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    change_type VARCHAR(20) NOT NULL,
    effective_date DATE,
    deadline_date DATE,
    severity VARCHAR(20) NOT NULL,
    action_required TEXT,
    scope TEXT NOT NULL, -- JSON stored as TEXT in SQLite
    corrects VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_requirements_family ON requirements(regulation_family);
CREATE INDEX IF NOT EXISTS idx_requirements_deadline ON requirements(deadline_date);
CREATE INDEX IF NOT EXISTS idx_requirements_celex ON requirements(celex);
CREATE INDEX IF NOT EXISTS idx_requirements_severity ON requirements(severity);

-- ============================================================================
-- FINDINGS TABLE (Part 2 output)
-- ============================================================================

CREATE TABLE IF NOT EXISTS findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company VARCHAR(200) NOT NULL,
    partner_id VARCHAR(10) NOT NULL,
    product_id VARCHAR(20) NOT NULL,
    product VARCHAR(200) NOT NULL,
    regulation TEXT NOT NULL,
    requirement TEXT NOT NULL,
    source_url TEXT NOT NULL,
    gap TEXT NOT NULL,
    deadline DATE NOT NULL,
    severity VARCHAR(20) NOT NULL,
    recommended_action TEXT NOT NULL,
    alert TEXT NOT NULL, -- JSON stored as TEXT in SQLite
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_findings_partner ON findings(partner_id);
CREATE INDEX IF NOT EXISTS idx_findings_deadline ON findings(deadline);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
CREATE INDEX IF NOT EXISTS idx_findings_product ON findings(product_id);

-- ============================================================================
-- ALERTS LOG TABLE (Part 3 output)
-- ============================================================================

CREATE TABLE IF NOT EXISTS alerts_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_id INTEGER,
    channel VARCHAR(20) NOT NULL,
    recipient TEXT NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    twilio_sid VARCHAR(100),
    error_message TEXT,
    FOREIGN KEY (finding_id) REFERENCES findings(id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_finding ON alerts_log(finding_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts_log(status);
CREATE INDEX IF NOT EXISTS idx_alerts_channel ON alerts_log(channel);

-- ============================================================================
-- EXTRACTION RUNS (Audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS extraction_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    requirements_found INTEGER DEFAULT 0,
    requirements_new INTEGER DEFAULT 0,
    requirements_updated INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_extraction_runs_status ON extraction_runs(status);
CREATE INDEX IF NOT EXISTS idx_extraction_runs_started ON extraction_runs(started_at);

-- ============================================================================
-- ASSESSMENT RUNS (Audit trail)
-- ============================================================================

CREATE TABLE IF NOT EXISTS assessment_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    requirements_assessed INTEGER DEFAULT 0,
    findings_generated INTEGER DEFAULT 0,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_assessment_runs_status ON assessment_runs(status);
CREATE INDEX IF NOT EXISTS idx_assessment_runs_started ON assessment_runs(started_at);

-- ============================================================================
-- NOTES FOR POSTGRESQL
-- ============================================================================

-- For PostgreSQL, replace:
-- 1. INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
-- 2. TEXT (for JSON) → JSONB
-- 3. VARCHAR lengths as needed
-- 4. Add GIN indexes on JSONB columns for better query performance:
--    CREATE INDEX idx_requirements_scope_gin ON requirements USING GIN (scope);
--    CREATE INDEX idx_findings_alert_gin ON findings USING GIN (alert);
