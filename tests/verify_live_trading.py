"""
Verification tests for live trading implementation.

Run from project root: python -m pytest tests/verify_live_trading.py -v

Validates:
- LiveOrderExecutor, VirtualOrderExecutor, TradingManager imports and structure
- Flask live routes and APIs
- API handlers accept mode parameter
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_imports():
    """Verify LiveOrderExecutor, VirtualOrderExecutor, TradingManager load without errors."""
    from core.live_order_executor import LiveOrderExecutor
    from core.virtual_order_executor import VirtualOrderExecutor
    from core.trading_manager import TradingManager

    assert LiveOrderExecutor is not None
    assert VirtualOrderExecutor is not None
    assert TradingManager is not None


def test_virtual_order_executor_accepts_trading_mode():
    """VirtualOrderExecutor __init__ accepts trading_mode parameter."""
    from core.virtual_order_executor import VirtualOrderExecutor
    import inspect

    sig = inspect.signature(VirtualOrderExecutor.__init__)
    params = list(sig.parameters.keys())
    assert 'trading_mode' in params


def test_trading_manager_has_dual_executors_and_mode():
    """TradingManager has paper_executor, live_executor, and start_trading accepts mode."""
    from core.trading_manager import TradingManager
    import inspect

    # Check start_trading signature
    sig = inspect.signature(TradingManager.start_trading)
    assert 'mode' in sig.parameters
    assert sig.parameters['mode'].default == 'paper'

    # Check attributes exist (will be set on instance)
    assert hasattr(TradingManager, '__init__')
    # We verify structure by checking a minimal instance would have these
    # (Creating full instance requires DB/Kite - we skip that)
    init_src = inspect.getsource(TradingManager.__init__)
    assert 'paper_executor' in init_src
    assert 'live_executor' in init_src
    assert 'order_executor' in init_src
    assert 'trading_mode' in init_src


def test_flask_routes():
    """Flask app has live routes and APIs registered."""
    # Import app - may trigger env/DB; we only need url_map
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.getcwd() != project_root:
        os.chdir(project_root)
    from web_ui.app import app

    rules = [r.rule for r in app.url_map.iter_rules()]

    # Live page routes (Flask rules are like '/live', '/live/dashboard', etc.)
    assert '/live' in rules
    assert '/live/dashboard' in rules
    assert '/live/orders' in rules
    assert '/live/positions' in rules

    # Live API routes
    assert '/api/live/funds' in rules
    assert '/api/live/orders' in rules
    assert '/api/live/positions' in rules


def test_api_start_trading_accepts_mode():
    """api_start_trading and api_start_individual_strategy read mode from request JSON."""
    # Read app.py source (handles @requires_auth wrapper which hides actual function source)
    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'web_ui', 'app.py'
    )
    with open(app_path, 'r', encoding='utf-8') as f:
        app_src = f.read()

    # api_start_trading: data.get('mode') and start_trading(..., mode=mode)
    assert "mode = data.get('mode'" in app_src or 'mode = data.get("mode"' in app_src
    assert "start_trading(valid_strategies, mode=mode)" in app_src

    # api_start_individual_strategy: data.get('mode') and start_trading(..., mode=mode)
    assert "start_trading([strategy_name], mode=mode)" in app_src
