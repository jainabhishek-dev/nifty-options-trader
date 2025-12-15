-- Add exit reason columns to positions table
-- Run this in your Supabase SQL editor

-- Add exit_reason column to store detailed exit reason text
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS exit_reason TEXT;

-- Add exit_reason_category column for categorized exit reasons
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS exit_reason_category VARCHAR(20) 
CHECK (exit_reason_category IN ('PROFIT_TARGET', 'STOP_LOSS', 'TIME_STOP', 'TREND_REVERSAL', 'ERROR', 'MIN_HOLD_TIME', 'MANUAL', 'OTHER'));

-- Add exit_price column to store the price at which position was closed
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS exit_price DECIMAL(10,2);

-- Add realized_pnl column to store final P&L when position is closed
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS realized_pnl DECIMAL(15,2) DEFAULT 0;

-- Add pnl_percent column to store P&L percentage
ALTER TABLE positions 
ADD COLUMN IF NOT EXISTS pnl_percent DECIMAL(8,4);

-- Create index on exit_reason_category for filtering
CREATE INDEX IF NOT EXISTS idx_positions_exit_reason_category ON positions(exit_reason_category);

-- Create index on realized_pnl for sorting/filtering
CREATE INDEX IF NOT EXISTS idx_positions_realized_pnl ON positions(realized_pnl);

-- Update the trades table to include more exit reason options
ALTER TABLE trades 
DROP CONSTRAINT IF EXISTS trades_exit_reason_check;

ALTER TABLE trades 
ADD CONSTRAINT trades_exit_reason_check 
CHECK (exit_reason IN ('PROFIT_TARGET', 'STOP_LOSS', 'TIME_STOP', 'TREND_REVERSAL', 'ERROR', 'MIN_HOLD_TIME', 'MANUAL', 'OTHER'));