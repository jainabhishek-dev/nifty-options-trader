-- ===================
-- ADD TRADING_MODE COLUMNS TO EXISTING TABLES
-- Run this script in your Supabase SQL editor
-- ===================

-- Add trading_mode column to trades table
ALTER TABLE trades ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'PAPER';

-- Add trading_mode column to analysis_records table  
ALTER TABLE analysis_records ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'PAPER';

-- Add trading_mode column to positions table
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'PAPER';

-- Add trading_mode column to performance_records table
ALTER TABLE performance_records ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'PAPER';

-- Add trading_mode column to system_events table
ALTER TABLE system_events ADD COLUMN IF NOT EXISTS trading_mode VARCHAR(10) DEFAULT 'PAPER';

-- ===================
-- UPDATE PERFORMANCE TABLE CONSTRAINT
-- ===================

-- Drop the old unique constraint on date only
ALTER TABLE performance_records DROP CONSTRAINT IF EXISTS performance_records_date_key;

-- Add new unique constraint on (date, trading_mode) combination
ALTER TABLE performance_records ADD CONSTRAINT performance_records_date_mode_key UNIQUE (date, trading_mode);

-- ===================
-- CREATE INDEXES FOR TRADING_MODE COLUMNS
-- ===================

-- Create indexes for fast filtering by trading_mode
CREATE INDEX IF NOT EXISTS idx_trades_trading_mode ON trades (trading_mode);
CREATE INDEX IF NOT EXISTS idx_analysis_trading_mode ON analysis_records (trading_mode);  
CREATE INDEX IF NOT EXISTS idx_positions_trading_mode ON positions (trading_mode);
CREATE INDEX IF NOT EXISTS idx_performance_trading_mode ON performance_records (trading_mode);
CREATE INDEX IF NOT EXISTS idx_events_trading_mode ON system_events (trading_mode);

-- ===================
-- UPDATE EXISTING RECORDS (Optional - sets all existing records to PAPER mode)
-- ===================

-- Update existing records to set trading_mode = 'PAPER' for historical data
-- This ensures all your existing data is properly categorized as paper trading
UPDATE trades SET trading_mode = 'PAPER' WHERE trading_mode IS NULL;
UPDATE analysis_records SET trading_mode = 'PAPER' WHERE trading_mode IS NULL;
UPDATE positions SET trading_mode = 'PAPER' WHERE trading_mode IS NULL;
UPDATE performance_records SET trading_mode = 'PAPER' WHERE trading_mode IS NULL;  
UPDATE system_events SET trading_mode = 'PAPER' WHERE trading_mode IS NULL;

-- ===================
-- VERIFICATION QUERIES
-- ===================

-- Verify the columns were added successfully
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name IN ('trades', 'analysis_records', 'positions', 'performance_records', 'system_events')
AND column_name = 'trading_mode'
ORDER BY table_name;

-- Check record counts by trading mode
SELECT 'trades' as table_name, trading_mode, COUNT(*) as record_count FROM trades GROUP BY trading_mode
UNION ALL
SELECT 'analysis_records', trading_mode, COUNT(*) FROM analysis_records GROUP BY trading_mode  
UNION ALL
SELECT 'positions', trading_mode, COUNT(*) FROM positions GROUP BY trading_mode
UNION ALL
SELECT 'performance_records', trading_mode, COUNT(*) FROM performance_records GROUP BY trading_mode
UNION ALL
SELECT 'system_events', trading_mode, COUNT(*) FROM system_events GROUP BY trading_mode
ORDER BY table_name, trading_mode;

-- ===================
-- MIGRATION COMPLETE
-- ===================