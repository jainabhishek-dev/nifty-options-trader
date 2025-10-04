-- Supabase Database Setup for Nifty Options Trading Platform
-- Run this script in your Supabase SQL editor

-- ===================
-- CREATE TABLES
-- ===================

-- Trades table
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(50) NOT NULL,
    action VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    order_id VARCHAR(100),
    status VARCHAR(20) NOT NULL,
    pnl DECIMAL(10,2) DEFAULT 0,
    fees DECIMAL(10,2) DEFAULT 0,
    strategy VARCHAR(50),
    confidence INTEGER DEFAULT 0,
    entry_reason TEXT,
    exit_reason TEXT,
    stop_loss DECIMAL(10,2) DEFAULT 0,
    target DECIMAL(10,2) DEFAULT 0,
    trading_mode VARCHAR(10) DEFAULT 'PAPER' -- PAPER/LIVE separation
);

-- Analysis records table
CREATE TABLE IF NOT EXISTS analysis_records (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    sentiment VARCHAR(20) NOT NULL,
    impact VARCHAR(20) NOT NULL,
    action VARCHAR(20) NOT NULL,
    strike_type VARCHAR(10) NOT NULL,
    confidence INTEGER NOT NULL,
    reason TEXT,
    nifty_level DECIMAL(10,2) DEFAULT 0,
    used_for_trade BOOLEAN DEFAULT FALSE,
    trading_mode VARCHAR(10) DEFAULT 'PAPER' -- PAPER/LIVE context
);

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    symbol VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    average_price DECIMAL(10,2) NOT NULL,
    current_price DECIMAL(10,2) NOT NULL,
    pnl DECIMAL(10,2) DEFAULT 0,
    unrealized_pnl DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'OPEN',
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    trading_mode VARCHAR(10) DEFAULT 'PAPER' -- PAPER/LIVE separation
);

-- Performance records table
CREATE TABLE IF NOT EXISTS performance_records (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    total_trades INTEGER DEFAULT 0,
    successful_trades INTEGER DEFAULT 0,
    total_pnl DECIMAL(10,2) DEFAULT 0,
    max_drawdown DECIMAL(5,2) DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0,
    avg_profit DECIMAL(10,2) DEFAULT 0,
    avg_loss DECIMAL(10,2) DEFAULT 0,
    largest_win DECIMAL(10,2) DEFAULT 0,
    largest_loss DECIMAL(10,2) DEFAULT 0,
    risk_adjusted_return DECIMAL(5,2) DEFAULT 0,
    trading_mode VARCHAR(10) DEFAULT 'PAPER', -- PAPER/LIVE separation
    UNIQUE(date, trading_mode) -- Allow separate records per mode
);

-- System events table
CREATE TABLE IF NOT EXISTS system_events (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    event_type VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    resolved BOOLEAN DEFAULT FALSE,
    trading_mode VARCHAR(10) DEFAULT 'PAPER' -- PAPER/LIVE context
);

-- ===================
-- CREATE INDEXES
-- ===================

-- Trades table indexes
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades (timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades (strategy);
CREATE INDEX IF NOT EXISTS idx_trades_trading_mode ON trades (trading_mode);

-- Analysis records indexes
CREATE INDEX IF NOT EXISTS idx_analysis_timestamp ON analysis_records (timestamp);
CREATE INDEX IF NOT EXISTS idx_analysis_confidence ON analysis_records (confidence);
CREATE INDEX IF NOT EXISTS idx_analysis_sentiment ON analysis_records (sentiment);
CREATE INDEX IF NOT EXISTS idx_analysis_used_for_trade ON analysis_records (used_for_trade);
CREATE INDEX IF NOT EXISTS idx_analysis_trading_mode ON analysis_records (trading_mode);

-- Positions table indexes
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions (symbol);
CREATE INDEX IF NOT EXISTS idx_positions_status ON positions (status);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions (entry_time);
CREATE INDEX IF NOT EXISTS idx_positions_trading_mode ON positions (trading_mode);

-- Performance records indexes
CREATE INDEX IF NOT EXISTS idx_performance_date ON performance_records (date);
CREATE INDEX IF NOT EXISTS idx_performance_trading_mode ON performance_records (trading_mode);

-- System events indexes
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON system_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_events_type ON system_events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_resolved ON system_events (resolved);
CREATE INDEX IF NOT EXISTS idx_events_trading_mode ON system_events (trading_mode);

-- ===================
-- ENABLE ROW LEVEL SECURITY (Optional)
-- ===================

-- Enable RLS on all tables
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_events ENABLE ROW LEVEL SECURITY;

-- Create permissive policies for development (adjust for production)
-- Drop existing policies if they exist, then create new ones
DROP POLICY IF EXISTS "Enable all operations for trades" ON trades;
DROP POLICY IF EXISTS "Enable all operations for analysis" ON analysis_records;
DROP POLICY IF EXISTS "Enable all operations for positions" ON positions;
DROP POLICY IF EXISTS "Enable all operations for performance" ON performance_records;
DROP POLICY IF EXISTS "Enable all operations for events" ON system_events;

CREATE POLICY "Enable all operations for trades" ON trades FOR ALL USING (true);
CREATE POLICY "Enable all operations for analysis" ON analysis_records FOR ALL USING (true);
CREATE POLICY "Enable all operations for positions" ON positions FOR ALL USING (true);
CREATE POLICY "Enable all operations for performance" ON performance_records FOR ALL USING (true);
CREATE POLICY "Enable all operations for events" ON system_events FOR ALL USING (true);

-- ===================
-- CREATE FUNCTIONS (Optional - for advanced features)
-- ===================

-- Function to get daily trading summary
CREATE OR REPLACE FUNCTION get_daily_summary(target_date DATE)
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'date', target_date,
        'total_trades', COUNT(*),
        'total_pnl', COALESCE(SUM(pnl), 0),
        'win_rate', CASE 
            WHEN COUNT(*) > 0 THEN ROUND((COUNT(*) FILTER (WHERE pnl > 0) * 100.0 / COUNT(*)), 2)
            ELSE 0
        END,
        'largest_win', COALESCE(MAX(pnl), 0),
        'largest_loss', COALESCE(MIN(pnl), 0)
    )
    INTO result
    FROM trades
    WHERE DATE(timestamp) = target_date;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ===================
-- INSERT SAMPLE DATA (Optional - for testing)
-- ===================

-- Sample system event
INSERT INTO system_events (event_type, message, details) 
VALUES ('INFO', 'Database setup completed successfully', '{"setup_date": "2025-10-02"}'::jsonb)
ON CONFLICT DO NOTHING;

-- ===================
-- SETUP COMPLETE
-- ===================

-- Verify tables were created
SELECT 
    schemaname,
    tablename,
    tableowner
FROM pg_tables 
WHERE tablename IN ('trades', 'analysis_records', 'positions', 'performance_records', 'system_events')
ORDER BY tablename;