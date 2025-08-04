-- Setup script for JSONB tests
-- This script creates the test schema and inserts sample data

-- First, run the schema creation
\i jsonb_test_schema.sql

-- Insert sample data for tests
BEGIN;

-- Sample user profiles with various JSONB patterns
INSERT INTO user_profiles (username, email, preferences, metadata, tags) VALUES
    ('test_user_1', 'user1@test.com', 
     '{"theme": "dark", "language": "en", "notifications": {"email": true, "push": false, "sms": true}}',
     '{"last_login": "2024-01-15T10:30:00Z", "account_type": "premium", "verified": true}',
     '["developer", "early-adopter", "beta-tester"]'),
    
    ('test_user_2', 'user2@test.com',
     '{"theme": "light", "language": "es", "notifications": {"email": false, "push": true}}',
     '{"last_login": "2024-01-16T14:20:00Z", "account_type": "standard"}',
     '["designer", "contributor"]'),
    
    ('test_user_3', 'user3@test.com',
     '{"theme": "auto", "language": "fr", "notifications": {}, "privacy": {"profile_visible": false}}',
     NULL,
     '[]'),
    
    ('test_user_4', 'user4@test.com',
     '{"theme": "dark", "language": "de", "advanced": {"api_access": true, "rate_limit": 1000}}',
     '{"account_type": "developer", "api_keys": ["key1", "key2"], "limits": {"storage": 10737418240}}',
     '["api-user", "power-user", "vip"]');

-- Sample products with complex specifications
INSERT INTO product_catalog (sku, name, specifications, pricing, inventory, attributes) VALUES
    ('TEST-LAPTOP-001', 'Test Laptop Pro',
     '{"cpu": {"brand": "Intel", "model": "i7-12700H", "cores": 14, "threads": 20}, 
       "ram": {"size": 16, "type": "DDR5", "speed": 4800}, 
       "storage": [{"type": "NVMe SSD", "capacity": 512, "interface": "PCIe 4.0"}], 
       "display": {"size": 15.6, "resolution": [1920, 1080], "refresh_rate": 144, "panel_type": "IPS"}}',
     '{"base_price": 1299.99, "currency": "USD", "tax_rate": 0.08, 
       "discounts": [{"code": "EARLY", "amount": 100, "type": "fixed"}], 
       "pricing_tiers": [{"quantity": 10, "discount": 0.05}, {"quantity": 50, "discount": 0.10}]}',
     '{"available": 50, "reserved": 5, "warehouses": {"NYC": 20, "LAX": 30}}',
     '{"colors": ["silver", "space-gray"], "weight": 1.8, "dimensions": {"width": 35.7, "height": 24.8, "depth": 1.8}}'),
    
    ('TEST-PHONE-001', 'Test Phone X',
     '{"cpu": {"brand": "Qualcomm", "model": "Snapdragon 8 Gen 2", "cores": 8}, 
       "ram": {"size": 12, "type": "LPDDR5X"}, 
       "storage": [{"type": "UFS 4.0", "capacity": 256}], 
       "camera": {"main": {"resolution": 50, "aperture": 1.8, "ois": true}, 
                  "front": {"resolution": 32, "aperture": 2.2}}}',
     '{"base_price": 899.99, "currency": "USD", "tax_rate": 0.08, 
       "promotional_price": 799.99, "valid_until": "2024-12-31"}',
     '{"available": 100, "reserved": 20, "pre_orders": 150}',
     '{"colors": ["midnight", "starlight", "red"], "5g": true, "battery": 5000, "wireless_charging": true}'),
    
    ('TEST-TABLET-001', 'Test Tablet Pro',
     '{"cpu": {"brand": "Apple", "model": "M2", "cores": 8}, 
       "ram": {"size": 8}, 
       "storage": [{"capacity": 128}], 
       "display": {"size": 11, "resolution": [2388, 1668], "technology": "Liquid Retina"}}',
     '{"base_price": 799.00, "currency": "USD", "education_discount": 0.10}',
     '{"available": 30, "reserved": 0}',
     NULL);

-- Sample configurations
INSERT INTO configuration (id, config_key, config_value, metadata) VALUES
    (1, 'test_app_settings', 
     '{"maintenance_mode": false, "max_upload_size": 10485760, 
       "allowed_file_types": ["pdf", "jpg", "png", "docx"], 
       "api": {"rate_limit": 1000, "timeout": 30, "retry_count": 3}}', 
     '{"version": "2.0", "last_modified_by": "system", "changelog": ["Added API settings", "Updated file types"]}'),
    
    (2, 'test_feature_flags', 
     '{"new_ui": true, "beta_features": false, "dark_mode": true,
       "experiments": {"exp_1": {"enabled": true, "percentage": 0.5}, 
                       "exp_2": {"enabled": false, "percentage": 0.0}}}', 
     NULL),
    
    (3, 'test_system_limits',
     '{"users": {"max_sessions": 5, "session_timeout": 3600}, 
       "storage": {"max_file_size": 104857600, "total_quota": 107374182400},
       "api": {"burst_limit": 100, "sustained_limit": 50}}',
     '{"enforced": true, "override_roles": ["admin", "system"]}');

-- Sample data for performance testing
INSERT INTO jsonb_performance_test (category, json_small, json_medium, json_large, json_array)
SELECT 
    'category_' || (i % 5),
    ('{"id": ' || i || ', "type": "small", "value": "' || md5(random()::text) || '"}')::jsonb,
    generate_json_data(1),  -- 1KB
    generate_json_data(10), -- 10KB
    ('["item_' || i || '", "item_' || (i+1) || '", "item_' || (i+2) || '"]')::jsonb
FROM generate_series(1, 100) i;

-- Sample edge cases
INSERT INTO jsonb_edge_cases (test_name, edge_case_data, description, expected_behavior) VALUES
    ('empty_object', '{}', 'Empty JSON object', 'success'),
    ('empty_array', '[]', 'Empty JSON array', 'success'),
    ('null_value', 'null', 'JSON null value', 'success'),
    ('nested_empty', '{"a": {}, "b": [], "c": null}', 'Nested empty values', 'success'),
    ('deep_nesting', '{"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}}', 'Deeply nested object', 'success'),
    ('large_array', (SELECT jsonb_build_array(generate_series(1, 1000))), 'Array with 1000 elements', 'success'),
    ('unicode_test', '{"emoji": "🚀", "chinese": "你好", "arabic": "مرحبا"}', 'Unicode characters', 'success'),
    ('special_chars', '{"quote": "\"", "backslash": "\\", "newline": "\n", "tab": "\t"}', 'Special characters', 'success');

COMMIT;

-- Analyze tables for query planner
ANALYZE user_profiles;
ANALYZE product_catalog;
ANALYZE configuration;
ANALYZE jsonb_performance_test;
ANALYZE jsonb_edge_cases;

-- Display summary
SELECT 'JSONB test schema setup complete' as status;
SELECT tablename, count(*) as row_count 
FROM (
    SELECT 'user_profiles' as tablename, count(*) FROM user_profiles
    UNION ALL
    SELECT 'product_catalog', count(*) FROM product_catalog
    UNION ALL
    SELECT 'configuration', count(*) FROM configuration
    UNION ALL
    SELECT 'jsonb_performance_test', count(*) FROM jsonb_performance_test
    UNION ALL
    SELECT 'jsonb_edge_cases', count(*) FROM jsonb_edge_cases
) counts
GROUP BY tablename
ORDER BY tablename;