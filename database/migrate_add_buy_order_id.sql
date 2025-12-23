-- ==========================================
-- POSITIONS TABLE MIGRATION SCRIPT
-- Purpose: Add buy_order_id foreign key for 1:1 BUY order to position mapping
-- ==========================================

-- STEP 1: Add buy_order_id column with foreign key relationship
ALTER TABLE public.positions 
ADD COLUMN buy_order_id UUID NULL 
REFERENCES public.orders(id) ON DELETE SET NULL;

-- STEP 2: Create index on buy_order_id for performance
CREATE INDEX IF NOT EXISTS idx_positions_buy_order_id 
ON public.positions USING btree (buy_order_id) 
TABLESPACE pg_default;

-- STEP 3: Drop the existing unique constraint that blocks multiple positions per symbol/strategy
DROP INDEX IF EXISTS idx_positions_unique_open;

-- STEP 4: Create new unique constraint that allows multiple positions per symbol/strategy
-- but prevents duplicate positions for the same BUY order
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_buy_order 
ON public.positions USING btree (buy_order_id) 
TABLESPACE pg_default
WHERE (is_open = true AND buy_order_id IS NOT NULL);

-- STEP 5: Migrate existing data - link positions to orders by timestamp matching
-- This updates existing positions to reference their corresponding BUY orders
UPDATE public.positions 
SET buy_order_id = (
    SELECT o.id 
    FROM public.orders o 
    WHERE o.symbol = positions.symbol 
    AND o.order_type = 'BUY'
    AND o.quantity = positions.quantity
    AND o.price = positions.average_price
    AND ABS(EXTRACT(EPOCH FROM (o.created_at - positions.entry_time))) < 120 -- Within 2 minutes
    ORDER BY ABS(EXTRACT(EPOCH FROM (o.created_at - positions.entry_time))) ASC
    LIMIT 1
)
WHERE buy_order_id IS NULL AND is_open = true;

-- STEP 6: Add constraint to ensure all new positions have buy_order_id
-- (Optional - remove this if you want to allow positions without linked orders)
-- ALTER TABLE public.positions 
-- ADD CONSTRAINT positions_buy_order_id_required 
-- CHECK (buy_order_id IS NOT NULL OR is_open = false);

-- ==========================================
-- VERIFICATION QUERIES (run after migration)
-- ==========================================

-- Check migration results
SELECT 
    'Migration Summary' as check_type,
    COUNT(*) as total_positions,
    COUNT(buy_order_id) as positions_with_buy_order_id,
    COUNT(*) - COUNT(buy_order_id) as positions_without_buy_order_id
FROM public.positions 
WHERE is_open = true;

-- Verify 1:1 relationship 
SELECT 
    'Buy Order Mapping' as check_type,
    COUNT(DISTINCT buy_order_id) as unique_buy_orders_linked,
    COUNT(*) as total_open_positions
FROM public.positions 
WHERE is_open = true AND buy_order_id IS NOT NULL;

-- Show positions linked to orders
SELECT 
    p.id as position_id,
    p.symbol,
    p.strategy_name,
    p.quantity,
    p.buy_order_id,
    o.created_at as order_created,
    p.entry_time as position_created,
    EXTRACT(EPOCH FROM (p.entry_time - o.created_at)) as time_diff_seconds
FROM public.positions p
LEFT JOIN public.orders o ON p.buy_order_id = o.id
WHERE p.is_open = true
ORDER BY p.created_at DESC;

-- ==========================================
-- ROLLBACK SCRIPT (if needed)
-- ==========================================
/*
-- To rollback this migration:

-- Remove the new constraint
DROP INDEX IF EXISTS idx_positions_unique_buy_order;

-- Restore original unique constraint  
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_unique_open 
ON public.positions USING btree (symbol, strategy_name, trading_mode) 
TABLESPACE pg_default
WHERE (is_open = true);

-- Remove the foreign key column
ALTER TABLE public.positions DROP COLUMN IF EXISTS buy_order_id;

-- Remove the index
DROP INDEX IF EXISTS idx_positions_buy_order_id;
*/