-- Initialize test schema for JSONB tests
-- This file is mounted to the test container and executed on startup

-- Simple JSONB table with SERIAL ID
CREATE TABLE IF NOT EXISTS jsonb_simple (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

-- Complex JSONB table with multiple fields and SERIAL ID
CREATE TABLE IF NOT EXISTS jsonb_complex (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    metadata JSONB NOT NULL,
    tags JSONB,
    settings JSONB
);

-- Type comparison table for JSON vs JSONB
CREATE TABLE IF NOT EXISTS jsonb_types (
    id SERIAL PRIMARY KEY,
    json_col JSON,
    jsonb_col JSONB
);

-- Create indexes for query performance
CREATE INDEX IF NOT EXISTS idx_jsonb_simple_data ON jsonb_simple USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_jsonb_complex_metadata ON jsonb_complex USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_jsonb_complex_tags ON jsonb_complex USING GIN (tags);

-- Additional tables for specific test scenarios

-- Table for transaction tests
CREATE TABLE IF NOT EXISTS jsonb_transactions (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL,
    version INTEGER DEFAULT 1
);

-- Table for performance benchmarks
CREATE TABLE IF NOT EXISTS jsonb_performance (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    small_data JSONB,
    medium_data JSONB,
    large_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for edge case testing
CREATE TABLE IF NOT EXISTS jsonb_edge_cases (
    id SERIAL PRIMARY KEY,
    test_name TEXT NOT NULL,
    test_data JSONB,
    UNIQUE(test_name)
);

-- Regular table for performance comparison
CREATE TABLE IF NOT EXISTS regular_table (
    id SERIAL PRIMARY KEY,
    name TEXT,
    value INTEGER,
    description TEXT
);

-- Create indexes for all tables
CREATE INDEX IF NOT EXISTS idx_jsonb_transactions_data ON jsonb_transactions USING GIN (data);
CREATE INDEX IF NOT EXISTS idx_jsonb_performance_small ON jsonb_performance USING GIN (small_data);
CREATE INDEX IF NOT EXISTS idx_jsonb_performance_medium ON jsonb_performance USING GIN (medium_data);
CREATE INDEX IF NOT EXISTS idx_jsonb_performance_large ON jsonb_performance USING GIN (large_data);
CREATE INDEX IF NOT EXISTS idx_jsonb_edge_cases_data ON jsonb_edge_cases USING GIN (test_data);