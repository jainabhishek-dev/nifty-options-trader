-- Supabase SQL Schema for Nifty Options Trading Platform
-- This script creates all necessary tables for the trading platform

-- 1. Strategies Table
-- Stores strategy configurations and metadata
CREATE TABLE IF NOT EXISTS strategies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index on strategy name for fast lookups
CREATE INDEX IF NOT EXISTS idx_strategies_name ON strategies(name);
CREATE INDEX IF NOT EXISTS idx_strategies_active ON strategies(is_active);

-- 2. Orders Table  
-- Stores all order information (both paper and live trading)
CREATE TABLE IF NOT EXISTS orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    trading_mode VARCHAR(20) NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    symbol VARCHAR(50) NOT NULL,
    order_type VARCHAR(20) NOT NULL CHECK (order_type IN ('BUY', 'SELL')),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price DECIMAL(10,2) NOT NULL CHECK (price > 0),
    order_id VARCHAR(100), -- Kite order ID for live trades
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'COMPLETE', 'CANCELLED', 'REJECTED')),
    filled_quantity INTEGER DEFAULT 0,
    filled_price DECIMAL(10,2),
    signal_data JSONB, -- Store signal information that triggered the order
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_orders_strategy ON orders(strategy_name);
CREATE INDEX IF NOT EXISTS idx_orders_trading_mode ON orders(trading_mode);
CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at DESC);

-- 3. Positions Table
-- Tracks current and historical positions
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    trading_mode VARCHAR(20) NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    symbol VARCHAR(50) NOT NULL,
    quantity INTEGER NOT NULL,
    average_price DECIMAL(10,2) NOT NULL CHECK (average_price > 0),
    current_price DECIMAL(10,2),
    unrealized_pnl DECIMAL(15,2) DEFAULT 0,
    is_open BOOLEAN DEFAULT true,
    entry_time TIMESTAMPTZ DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_positions_strategy ON positions(strategy_name);
CREATE INDEX IF NOT EXISTS idx_positions_trading_mode ON positions(trading_mode);
CREATE INDEX IF NOT EXISTS idx_positions_symbol ON positions(symbol);
CREATE INDEX IF NOT EXISTS idx_positions_is_open ON positions(is_open);
CREATE INDEX IF NOT EXISTS idx_positions_entry_time ON positions(entry_time DESC);

-- Create unique constraint for open positions
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_open 
ON positions(symbol, strategy_name, trading_mode) 
WHERE is_open = true;

-- 4. Trades Table
-- Stores completed trade information for analysis
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    trading_mode VARCHAR(20) NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    symbol VARCHAR(50) NOT NULL,
    entry_price DECIMAL(10,2) NOT NULL CHECK (entry_price > 0),
    exit_price DECIMAL(10,2) NOT NULL CHECK (exit_price > 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    pnl DECIMAL(15,2) NOT NULL,
    pnl_percentage DECIMAL(8,4),
    entry_time TIMESTAMPTZ NOT NULL,
    exit_time TIMESTAMPTZ NOT NULL,
    hold_duration_minutes INTEGER,
    exit_reason VARCHAR(50), -- 'TARGET', 'STOP_LOSS', 'TIME_STOP', 'MANUAL'
    entry_signal_data JSONB, -- Signal data that triggered entry
    exit_signal_data JSONB,  -- Signal data that triggered exit
    fees DECIMAL(10,2) DEFAULT 0,
    slippage DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for analysis
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy_name);
CREATE INDEX IF NOT EXISTS idx_trades_trading_mode ON trades(trading_mode);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time DESC);
CREATE INDEX IF NOT EXISTS idx_trades_pnl ON trades(pnl);
CREATE INDEX IF NOT EXISTS idx_trades_exit_reason ON trades(exit_reason);

-- 5. Daily P&L Table
-- Tracks daily performance by strategy and trading mode
CREATE TABLE IF NOT EXISTS daily_pnl (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    strategy_name VARCHAR(100) NOT NULL,
    trading_mode VARCHAR(20) NOT NULL CHECK (trading_mode IN ('paper', 'live')),
    realized_pnl DECIMAL(15,2) DEFAULT 0,
    unrealized_pnl DECIMAL(15,2) DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0,
    trades_count INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    fees_paid DECIMAL(10,2) DEFAULT 0,
    portfolio_value DECIMAL(15,2), -- Total portfolio value at end of day
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes and unique constraint
CREATE UNIQUE INDEX IF NOT EXISTS idx_daily_pnl_unique 
ON daily_pnl(date, strategy_name, trading_mode);
CREATE INDEX IF NOT EXISTS idx_daily_pnl_date ON daily_pnl(date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_pnl_strategy ON daily_pnl(strategy_name);

-- 6. Strategy Signals Table
-- Stores all strategy signals for analysis and debugging
CREATE TABLE IF NOT EXISTS strategy_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_name VARCHAR(100) NOT NULL,
    signal_type VARCHAR(50) NOT NULL, -- 'BUY', 'SELL', 'HOLD', 'EXIT'
    symbol VARCHAR(50),
    price DECIMAL(10,2),
    signal_strength DECIMAL(5,2), -- Confidence level of signal (0-100)
    market_data JSONB, -- Store relevant market data at signal time
    indicators JSONB,  -- Store indicator values (RSI, ATR, etc.)
    action_taken BOOLEAN DEFAULT false, -- Whether signal resulted in order
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for signal analysis
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON strategy_signals(strategy_name);
CREATE INDEX IF NOT EXISTS idx_signals_type ON strategy_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON strategy_signals(symbol);
CREATE INDEX IF NOT EXISTS idx_signals_created_at ON strategy_signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_action_taken ON strategy_signals(action_taken);

-- Create Row Level Security (RLS) policies if needed
-- Note: Enable RLS based on your security requirements

-- Enable RLS on all tables (optional - uncomment if using authentication)
-- ALTER TABLE strategies ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE daily_pnl ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE strategy_signals ENABLE ROW LEVEL SECURITY;

-- Create functions for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for automatic timestamp updates
CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER update_daily_pnl_updated_at
    BEFORE UPDATE ON daily_pnl
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Create views for common queries
CREATE OR REPLACE VIEW active_positions AS
SELECT 
    p.*,
    (p.current_price - p.average_price) * p.quantity as unrealized_pnl_calculated
FROM positions p
WHERE p.is_open = true;

CREATE OR REPLACE VIEW daily_performance AS
SELECT 
    dp.*,
    CASE 
        WHEN dp.trades_count > 0 
        THEN ROUND((dp.winning_trades::DECIMAL / dp.trades_count * 100), 2)
        ELSE 0 
    END as win_rate_percentage
FROM daily_pnl dp
ORDER BY dp.date DESC;

CREATE OR REPLACE VIEW strategy_performance_summary AS
SELECT 
    t.strategy_name,
    t.trading_mode,
    COUNT(*) as total_trades,
    COUNT(CASE WHEN t.pnl > 0 THEN 1 END) as winning_trades,
    COUNT(CASE WHEN t.pnl < 0 THEN 1 END) as losing_trades,
    ROUND(AVG(CASE WHEN t.pnl > 0 THEN t.pnl END), 2) as avg_winning_trade,
    ROUND(AVG(CASE WHEN t.pnl < 0 THEN t.pnl END), 2) as avg_losing_trade,
    ROUND(SUM(t.pnl), 2) as total_pnl,
    ROUND(AVG(t.pnl), 2) as avg_pnl_per_trade,
    MAX(t.pnl) as best_trade,
    MIN(t.pnl) as worst_trade,
    ROUND(AVG(t.hold_duration_minutes), 1) as avg_hold_duration_minutes
FROM trades t
GROUP BY t.strategy_name, t.trading_mode
ORDER BY total_pnl DESC;

-- Insert default strategy configurations
INSERT INTO strategies (name, config, is_active) VALUES 
('scalping', '{
    "timeframe": "1minute",
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "volume_threshold": 1.5,
    "target_percentage": 35,
    "stop_loss_percentage": 40,
    "time_stop_minutes": 30,
    "max_positions": 3,
    "lot_size": 1
}', true),
('supertrend', '{
    "timeframe": "15minute", 
    "atr_period": 10,
    "multiplier": 3.0,
    "target_percentage": 40,
    "stop_loss_percentage": 50,
    "time_stop_minutes": 120,
    "max_positions": 2,
    "lot_size": 1
}', true)
ON CONFLICT (name) DO NOTHING;

-- Create helpful indexes for performance
CREATE INDEX IF NOT EXISTS idx_trades_pnl_positive ON trades(pnl) WHERE pnl > 0;
CREATE INDEX IF NOT EXISTS idx_trades_pnl_negative ON trades(pnl) WHERE pnl < 0;
CREATE INDEX IF NOT EXISTS idx_orders_pending ON orders(created_at) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_positions_with_pnl ON positions(strategy_name, trading_mode) WHERE is_open = true;

-- Add comments for documentation
COMMENT ON TABLE strategies IS 'Stores trading strategy configurations and metadata';
COMMENT ON TABLE orders IS 'Records all trading orders for both paper and live trading modes';
COMMENT ON TABLE positions IS 'Tracks current and historical position data with P&L calculations';
COMMENT ON TABLE trades IS 'Stores completed trades with detailed entry/exit information for analysis';
COMMENT ON TABLE daily_pnl IS 'Daily performance tracking by strategy and trading mode';
COMMENT ON TABLE strategy_signals IS 'Logs all strategy signals for analysis and debugging purposes';

COMMENT ON COLUMN orders.signal_data IS 'JSON data containing the signal information that triggered this order';
COMMENT ON COLUMN trades.entry_signal_data IS 'Signal data that caused the trade entry';
COMMENT ON COLUMN trades.exit_signal_data IS 'Signal data that caused the trade exit';
COMMENT ON COLUMN strategy_signals.market_data IS 'Market conditions at the time of signal generation';
COMMENT ON COLUMN strategy_signals.indicators IS 'Technical indicator values at signal time';