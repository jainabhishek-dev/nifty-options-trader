-- Database Migration: Add trading_mode columns
-- Run this script to add trading_mode columns to existing databases

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

-- Update the performance_records unique constraint to include trading_mode
ALTER TABLE performance_records DROP CONSTRAINT IF EXISTS performance_records_date_key;
ALTER TABLE performance_records ADD CONSTRAINT performance_records_date_mode_key UNIQUE (date, trading_mode);

-- Create indexes for trading_mode columns
CREATE INDEX IF NOT EXISTS idx_trades_trading_mode ON trades (trading_mode);
CREATE INDEX IF NOT EXISTS idx_analysis_trading_mode ON analysis_records (trading_mode);  
CREATE INDEX IF NOT EXISTS idx_positions_trading_mode ON positions (trading_mode);
CREATE INDEX IF NOT EXISTS idx_performance_trading_mode ON performance_records (trading_mode);
CREATE INDEX IF NOT EXISTS idx_events_trading_mode ON system_events (trading_mode);

-- Update existing records to set trading_mode based on current system mode
-- This ensures historical data is properly categorized
UPDATE trades SET trading_mode = 'PAPER' WHERE trading_mode IS NULL OR trading_mode = '';
UPDATE analysis_records SET trading_mode = 'PAPER' WHERE trading_mode IS NULL OR trading_mode = '';
UPDATE positions SET trading_mode = 'PAPER' WHERE trading_mode IS NULL OR trading_mode = '';
UPDATE performance_records SET trading_mode = 'PAPER' WHERE trading_mode IS NULL OR trading_mode = '';  
UPDATE system_events SET trading_mode = 'PAPER' WHERE trading_mode IS NULL OR trading_mode = '';

-- Verification queries (uncomment to run)
-- SELECT COUNT(*) as total_trades, trading_mode FROM trades GROUP BY trading_mode;
-- SELECT COUNT(*) as total_analysis, trading_mode FROM analysis_records GROUP BY trading_mode;
-- SELECT COUNT(*) as total_positions, trading_mode FROM positions GROUP BY trading_mode;
-- SELECT COUNT(*) as total_performance, trading_mode FROM performance_records GROUP BY trading_mode;
-- SELECT COUNT(*) as total_events, trading_mode FROM system_events GROUP BY trading_mode;