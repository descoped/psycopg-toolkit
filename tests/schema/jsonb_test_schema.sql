-- JSONB Test Schema for psycopg-toolkit
-- This schema is used for integration tests of JSONB functionality

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing test tables if they exist
DROP TABLE IF EXISTS transaction_test CASCADE;
DROP TABLE IF EXISTS product_catalog CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;
DROP TABLE IF EXISTS configuration CASCADE;
DROP TABLE IF EXISTS jsonb_performance_test CASCADE;
DROP TABLE IF EXISTS jsonb_edge_cases CASCADE;

-- User Profiles table with JSONB fields
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL,
    preferences JSONB NOT NULL DEFAULT '{}',
    metadata JSONB,
    tags JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create GIN indexes for JSONB query performance
CREATE INDEX idx_user_profiles_preferences ON user_profiles USING GIN (preferences);
CREATE INDEX idx_user_profiles_metadata ON user_profiles USING GIN (metadata);
CREATE INDEX idx_user_profiles_tags ON user_profiles USING GIN (tags);

-- Product Catalog table with complex JSONB structures
CREATE TABLE product_catalog (
    id SERIAL PRIMARY KEY,
    sku VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    specifications JSONB NOT NULL,
    pricing JSONB NOT NULL,
    inventory JSONB DEFAULT '{"available": 0, "reserved": 0}',
    attributes JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create GIN indexes for product queries
CREATE INDEX idx_product_specifications ON product_catalog USING GIN (specifications);
CREATE INDEX idx_product_pricing ON product_catalog USING GIN (pricing);
CREATE INDEX idx_product_attributes ON product_catalog USING GIN (attributes);
-- Specific index for common queries
CREATE INDEX idx_product_specs_category ON product_catalog USING GIN ((specifications -> 'category'));

-- Configuration table for testing Optional JSONB fields
CREATE TABLE configuration (
    id INTEGER PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    metadata JSONB,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_configuration_value ON configuration USING GIN (config_value);

-- Transaction test table (used in transaction tests)
CREATE TABLE transaction_test (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL,
    data JSONB NOT NULL,
    history JSONB NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_transaction_data ON transaction_test USING GIN (data);
CREATE INDEX idx_transaction_history ON transaction_test USING GIN (history);

-- Performance test table with various JSONB patterns
CREATE TABLE jsonb_performance_test (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) NOT NULL,
    json_small JSONB,  -- Small JSON objects (~1KB)
    json_medium JSONB, -- Medium JSON objects (~10KB)
    json_large JSONB,  -- Large JSON objects (~100KB)
    json_array JSONB,  -- JSON arrays
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance testing
CREATE INDEX idx_perf_json_small ON jsonb_performance_test USING GIN (json_small);
CREATE INDEX idx_perf_json_medium ON jsonb_performance_test USING GIN (json_medium);
CREATE INDEX idx_perf_json_large ON jsonb_performance_test USING GIN (json_large);
CREATE INDEX idx_perf_json_array ON jsonb_performance_test USING GIN (json_array);
CREATE INDEX idx_perf_category ON jsonb_performance_test (category);

-- Edge cases table for testing JSONB limits and special scenarios
CREATE TABLE jsonb_edge_cases (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(100) NOT NULL,
    edge_case_data JSONB,
    description TEXT,
    expected_behavior VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_edge_cases_data ON jsonb_edge_cases USING GIN (edge_case_data);

-- Helper functions for JSONB operations
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add update triggers for tables with updated_at
CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_catalog_updated_at BEFORE UPDATE ON product_catalog
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Sample data insertion for testing (optional, can be run separately)
/*
-- Sample user profiles
INSERT INTO user_profiles (username, email, preferences, metadata, tags) VALUES
    ('john_doe', 'john@example.com', 
     '{"theme": "dark", "language": "en", "notifications": {"email": true, "push": false}}',
     '{"last_login": "2024-01-15T10:30:00Z", "account_type": "premium"}',
     '["developer", "early-adopter", "beta-tester"]'),
    ('jane_smith', 'jane@example.com',
     '{"theme": "light", "language": "es", "notifications": {"email": false, "push": true}}',
     '{"last_login": "2024-01-16T14:20:00Z", "account_type": "standard"}',
     '["designer", "contributor"]');

-- Sample products
INSERT INTO product_catalog (sku, name, specifications, pricing, attributes) VALUES
    ('LAPTOP-001', 'ProBook 15',
     '{"cpu": "Intel i7-12700H", "ram": "16GB DDR5", "storage": {"ssd": "512GB NVMe", "type": "PCIe 4.0"}, "display": {"size": "15.6 inch", "resolution": "1920x1080", "refresh_rate": "144Hz"}}',
     '{"base_price": 1299.99, "currency": "USD", "discounts": [{"type": "early_bird", "amount": 100}], "tax_rate": 0.08}',
     '{"color": ["silver", "black"], "weight": "1.8kg", "warranty": "2 years"}'),
    ('PHONE-001', 'SmartPhone X',
     '{"cpu": "Snapdragon 8 Gen 2", "ram": "12GB", "storage": {"internal": "256GB", "expandable": false}, "camera": {"main": "50MP", "front": "32MP", "features": ["OIS", "4K video"]}}',
     '{"base_price": 899.99, "currency": "USD", "discounts": [], "tax_rate": 0.08}',
     '{"color": ["blue", "green", "black"], "5g": true, "battery": "5000mAh"}');

-- Sample configurations
INSERT INTO configuration (id, config_key, config_value, metadata) VALUES
    (1, 'app_settings', '{"maintenance_mode": false, "max_upload_size": 10485760, "allowed_file_types": ["pdf", "jpg", "png"]}', '{"version": "1.0", "last_modified_by": "admin"}'),
    (2, 'feature_flags', '{"new_ui": true, "beta_features": false, "ab_testing": {"experiment_1": 0.5, "experiment_2": 0.3}}', NULL);
*/

-- Utility views for testing
CREATE OR REPLACE VIEW jsonb_table_stats AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) as table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) as indexes_size
FROM pg_tables
WHERE tablename IN ('user_profiles', 'product_catalog', 'configuration', 'transaction_test', 'jsonb_performance_test', 'jsonb_edge_cases')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Function to generate sample JSONB data of specific size
CREATE OR REPLACE FUNCTION generate_json_data(target_size_kb INTEGER)
RETURNS JSONB AS $$
DECLARE
    result JSONB;
    data_array JSON[];
    i INTEGER;
    item_count INTEGER;
BEGIN
    -- Estimate items needed (each item ~100 bytes)
    item_count := (target_size_kb * 1024) / 100;
    
    FOR i IN 1..item_count LOOP
        data_array := array_append(data_array, 
            json_build_object(
                'id', i,
                'value', md5(random()::text),
                'timestamp', CURRENT_TIMESTAMP,
                'nested', json_build_object(
                    'key', 'value_' || i,
                    'number', random() * 1000
                )
            )::json
        );
    END LOOP;
    
    result := json_build_object('data', data_array)::jsonb;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed for your test environment)
-- GRANT ALL ON ALL TABLES IN SCHEMA public TO your_test_user;
-- GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO your_test_user;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO your_test_user;