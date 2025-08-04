-- Teardown script for JSONB tests
-- This script removes all test data and optionally drops the schema

-- Option 1: Clean data but keep schema (default)
BEGIN;

-- Delete all test data
TRUNCATE TABLE user_profiles CASCADE;
TRUNCATE TABLE product_catalog CASCADE;
TRUNCATE TABLE configuration CASCADE;
TRUNCATE TABLE transaction_test CASCADE;
TRUNCATE TABLE jsonb_performance_test CASCADE;
TRUNCATE TABLE jsonb_edge_cases CASCADE;

-- Reset sequences
ALTER SEQUENCE product_catalog_id_seq RESTART WITH 1;
ALTER SEQUENCE transaction_test_id_seq RESTART WITH 1;
ALTER SEQUENCE jsonb_performance_test_id_seq RESTART WITH 1;
ALTER SEQUENCE jsonb_edge_cases_id_seq RESTART WITH 1;

COMMIT;

SELECT 'Test data cleaned, schema preserved' as status;

-- Option 2: Complete teardown (uncomment to use)
/*
-- Drop all test tables and functions
DROP TABLE IF EXISTS transaction_test CASCADE;
DROP TABLE IF EXISTS product_catalog CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;
DROP TABLE IF EXISTS configuration CASCADE;
DROP TABLE IF EXISTS jsonb_performance_test CASCADE;
DROP TABLE IF EXISTS jsonb_edge_cases CASCADE;

DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
DROP FUNCTION IF EXISTS generate_json_data(INTEGER) CASCADE;

DROP VIEW IF EXISTS jsonb_table_stats CASCADE;

SELECT 'Complete teardown finished' as status;
*/