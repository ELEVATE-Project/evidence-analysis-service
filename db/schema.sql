-- Evidence Analysis System - Phase 1 Database Schema
-- PostgreSQL 14+

-- Create database (run as superuser)
-- CREATE DATABASE evidence_analysis;

-- Connect to the database
-- \c evidence_analysis;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(255) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_superuser BOOLEAN DEFAULT FALSE,
    tenant_code VARCHAR(100),
    organization_code VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_code);

-- ============================================
-- CSV Source Types Table
-- ============================================
CREATE TABLE IF NOT EXISTS csv_source_types (
    id SERIAL PRIMARY KEY,
    tenant_code VARCHAR(100) NOT NULL,
    organization_code VARCHAR(100) NOT NULL,

    -- Metadata
    type_key VARCHAR(100) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    description TEXT,

    -- Flags
    has_geo BOOLEAN NOT NULL DEFAULT FALSE,
    has_program BOOLEAN NOT NULL DEFAULT FALSE,
    has_rubric BOOLEAN NOT NULL DEFAULT FALSE,
    has_narrative BOOLEAN NOT NULL DEFAULT FALSE,
    max_rows_per_upload INTEGER DEFAULT 10000,

    -- Config (JSONB)
    column_mappings JSONB NOT NULL,
    evidence_columns JSONB NOT NULL DEFAULT '[]'::jsonb,
    evidence_context_config JSONB NOT NULL,
    available_filters JSONB DEFAULT '[]'::jsonb,
    question_config JSONB DEFAULT '{"entry_options":[{"key":"UPLOAD","label":"Upload CSV"},{"key":"COMMON","label":"Manual Entry"}],"mandatory_columns":[],"optional_columns":[]}'::jsonb,
    default_thresholds JSONB DEFAULT '{"relevant":0.8,"partial":0.5}'::jsonb,

    -- Status & Audit
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_by VARCHAR(255) REFERENCES users(id),
    updated_by VARCHAR(255) REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_csv_source_types_scope_type_key UNIQUE (tenant_code, organization_code, type_key)
);

CREATE INDEX IF NOT EXISTS idx_csv_source_types_scope_active
    ON csv_source_types(tenant_code, organization_code, is_active);
CREATE INDEX IF NOT EXISTS idx_csv_source_types_type_key
    ON csv_source_types(type_key);

-- ============================================
-- Executions Table (Phase 1 Complete Schema)
-- ============================================
CREATE TABLE IF NOT EXISTS executions (
    -- Primary identification
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_code VARCHAR(100) NOT NULL,
    organization_code VARCHAR(100) NOT NULL,
    
    -- Execution metadata
    name VARCHAR(255) NOT NULL,
    csv_type_id VARCHAR(100),
    ai_model_id VARCHAR(100),
    program_ref_id VARCHAR(100),
    program_name VARCHAR(255),
    state VARCHAR(50),
    district VARCHAR(100),
    
    -- Configuration
    criterias_mode VARCHAR(50),
    criterias_file_url TEXT,
    criterias_config JSONB,
    threshold_config JSONB,
    
    -- Status and processing
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    failure_reason TEXT,
    
    -- Metrics
    total_rows INTEGER,
    processed_rows INTEGER DEFAULT 0,
    actual_cost NUMERIC(10, 4),
    estimated_cost NUMERIC(10, 4),
    
    -- File storage fields (store provider-agnostic absolute file paths)
    input_file_url TEXT,
    input_file_size BIGINT,
    input_file_checksum VARCHAR(64),
    questions_file_url TEXT,
    questions_file_size BIGINT,
    output_file_url TEXT,
    output_file_size BIGINT,
    
    -- Processing metadata (Phase 1)
    worker_id VARCHAR(100),
    error_logs TEXT,
    retry_count INTEGER DEFAULT 0,
    checkpoint_data JSONB,
    
    -- Timestamps
    created_by VARCHAR(100),
    updated_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    upload_completed_at TIMESTAMPTZ,
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    
    -- New metrics (Phase 1)
    average_processing_time NUMERIC(10, 2),
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMPTZ
);

-- Indexes for executions table
CREATE INDEX IF NOT EXISTS idx_executions_created_by ON executions(created_by);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_created_at ON executions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_executions_state ON executions(state);
CREATE INDEX IF NOT EXISTS idx_executions_notification ON executions(notification_sent);
CREATE INDEX IF NOT EXISTS idx_executions_tenant ON executions(tenant_code);
CREATE INDEX IF NOT EXISTS idx_executions_org ON executions(organization_code);



-- ============================================
-- Comments
-- ============================================
COMMENT ON TABLE users IS 'User accounts for authentication and authorization';
COMMENT ON TABLE csv_source_types IS 'Configuration registry for CSV parsing and validation rules by tenant/org/type';
COMMENT ON TABLE executions IS 'Evidence analysis execution jobs with complete Phase 1 schema';

COMMENT ON COLUMN executions.status IS 'Execution status: queued, running, completed, failed';
COMMENT ON COLUMN executions.average_processing_time IS 'Average processing time per row in seconds';
COMMENT ON COLUMN executions.notification_sent IS 'Whether email notification was sent';

-- ============================================
-- Grants (adjust as needed for your user)
-- ============================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO evidence_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO evidence_user;
