-- Migration: Add level column to extracted_rules table
-- Date: 2025-11-11
-- Description: Add dedicated 'level' column for hierarchical rule support
-- Depends on: 001_create_extracted_rules_table.sql

-- Add level column (nullable for backwards compatibility)
ALTER TABLE extracted_rules
ADD COLUMN IF NOT EXISTS level INTEGER;

-- Add comment explaining the column
COMMENT ON COLUMN extracted_rules.level IS 'Hierarchical rule level: 1=Critical/Knockout, 2=Standard/Important, 3=Preferred/Optimal, NULL=Single-level (non-hierarchical)';

-- Create index for level-based queries
CREATE INDEX IF NOT EXISTS idx_extracted_rules_level ON extracted_rules(level);

-- Create composite index for efficient bank+policy+level queries
CREATE INDEX IF NOT EXISTS idx_extracted_rules_bank_policy_level ON extracted_rules(bank_id, policy_type_id, level);

-- Update existing rules: extract level from category field if it exists
-- This handles legacy rules that have "Level X - Category" format
UPDATE extracted_rules
SET level = CASE
    WHEN category LIKE 'Level 1 -%' THEN 1
    WHEN category LIKE 'Level 2 -%' THEN 2
    WHEN category LIKE 'Level 3 -%' THEN 3
    ELSE NULL
END
WHERE level IS NULL AND category IS NOT NULL;

-- Optional: Clean up category field by removing "Level X - " prefix
-- Uncomment if you want to clean the category field
-- UPDATE extracted_rules
-- SET category = REGEXP_REPLACE(category, '^Level [123] - ', '')
-- WHERE category LIKE 'Level % -%';
