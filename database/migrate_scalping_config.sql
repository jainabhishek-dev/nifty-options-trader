-- Migration: Add scalping_strategy_config table
-- Purpose: Store configurable parameters for scalping strategy
-- Date: January 4, 2026

-- Create scalping strategy configuration table
CREATE TABLE IF NOT EXISTS scalping_strategy_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    profit_target NUMERIC NOT NULL DEFAULT 15.0,  -- Profit target percentage (e.g., 15.0 = 15%)
    stop_loss NUMERIC NOT NULL DEFAULT 10.0,       -- Trailing stop loss percentage (e.g., 10.0 = 10%)
    time_stop_minutes INTEGER NOT NULL DEFAULT 30, -- Time-based exit in minutes
    signal_cooldown_seconds INTEGER NOT NULL DEFAULT 60, -- Cooldown between opposite signals
    strike_offset INTEGER NOT NULL DEFAULT 1,      -- Strike selection: -3=3ITM, -2=2ITM, -1=1ITM, 0=ATM, 1=1OTM, 2=2OTM, 3=3OTM
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CHECK (id = 1)  -- Ensure only one row exists
);

-- Insert default configuration (matches current hardcoded values)
INSERT INTO scalping_strategy_config (id, profit_target, stop_loss, time_stop_minutes, signal_cooldown_seconds, strike_offset)
VALUES (1, 15.0, 10.0, 30, 60, 1)
ON CONFLICT (id) DO NOTHING;

-- Create index on updated_at for tracking changes
CREATE INDEX IF NOT EXISTS idx_scalping_config_updated ON scalping_strategy_config(updated_at);

-- Add comment to table
COMMENT ON TABLE scalping_strategy_config IS 'Configuration parameters for scalping strategy. Single row table (id=1 always).';
COMMENT ON COLUMN scalping_strategy_config.strike_offset IS 'Strike distance from ATM: negative=ITM, 0=ATM, positive=OTM. CE: ATM+(offset*50), PE: ATM-(offset*50)';
