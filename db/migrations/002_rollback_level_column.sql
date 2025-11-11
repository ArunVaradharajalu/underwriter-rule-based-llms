-- Rollback Migration: Remove level column from extracted_rules table
-- Date: 2025-11-11
-- Description: Rollback for 002_add_level_column_to_extracted_rules.sql

-- Drop composite index
DROP INDEX IF EXISTS idx_extracted_rules_bank_policy_level;

-- Drop level index
DROP INDEX IF EXISTS idx_extracted_rules_level;

-- Drop level column
ALTER TABLE extracted_rules
DROP COLUMN IF EXISTS level;
