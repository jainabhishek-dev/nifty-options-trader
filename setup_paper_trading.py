#!/usr/bin/env python3
"""
Paper Trading Setup Script
Run this before starting paper trading to ensure strategies are configured
"""

import sys
import os
sys.path.append('.')

from datetime import datetime
from strategies.strategy_manager import get_strategy_manager, TradingMode, StrategyStatus
from core.kite_manager import KiteManager

def setup_paper_trading():
    """Setup paper trading with ATM Straddle strategy"""
    print("🚀 Setting up paper trading for live market...")
    
    # Initialize managers
    kite_manager = KiteManager()
    strategy_manager = get_strategy_manager(kite_manager)
    
    # Check if strategy already exists
    existing_strategies = strategy_manager.get_active_strategies_by_mode(TradingMode.PAPER)
    if existing_strategies:
        print(f"✅ Found existing paper trading strategies: {existing_strategies}")
        return True
    
    print("📝 Creating ATM Straddle strategy for paper trading...")
    
    try:
        # Create ATM Straddle strategy
        result = strategy_manager.create_strategy_instance(
            strategy_name='ATM_Straddle_Paper',
            strategy_class_name='ATMStraddleStrategy',
            parameters={
                'entry_time_start': '09:20',
                'entry_time_end': '14:00',
                'exit_time': '15:15',
                'volatility_threshold': 15.0,
                'max_loss_percent': 50.0,
                'profit_target_percent': 100.0
            },
            trading_mode=TradingMode.PAPER,
            capital_allocation=200000,
            risk_limits={}
        )
        
        if result:
            print("✅ ATM Straddle strategy created successfully")
            
            # Activate the strategy
            activated = strategy_manager.activate_strategy('ATM_Straddle_Paper')
            if activated:
                print("✅ Strategy activated for paper trading")
                return True
            else:
                print("❌ Failed to activate strategy")
                return False
        else:
            print("❌ Failed to create strategy instance")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up paper trading: {e}")
        return False

def verify_setup():
    """Verify paper trading setup"""
    print("\n🔍 Verifying paper trading setup...")
    
    kite_manager = KiteManager()
    strategy_manager = get_strategy_manager(kite_manager)
    
    # Check active strategies
    paper_strategies = strategy_manager.get_active_strategies_by_mode(TradingMode.PAPER)
    print(f"📊 Active paper trading strategies: {len(paper_strategies)}")
    
    for strategy in paper_strategies:
        instance = strategy_manager.get_strategy_instance(strategy)
        if instance:
            print(f"   ✅ {strategy}: {instance.__class__.__name__}")
        else:
            print(f"   ❌ {strategy}: No instance found")
    
    # Check paper trading engine
    try:
        from paper_trading.paper_trading_engine import get_paper_trading_engine
        paper_engine = get_paper_trading_engine(kite_manager)
        
        engine_strategies = paper_engine.strategy_manager.get_active_strategies_by_mode(TradingMode.PAPER)
        print(f"🎯 Paper engine sees {len(engine_strategies)} strategies")
        
        print(f"💰 Virtual capital: Rs.{paper_engine.virtual_capital:,.0f}")
        
    except Exception as e:
        print(f"❌ Paper engine error: {e}")
        return False
    
    # Check market connectivity
    if kite_manager.is_authenticated:
        print("✅ Kite Connect authenticated and ready")
    else:
        print("⚠️ Kite Connect not authenticated - will need to login")
    
    return len(paper_strategies) > 0

if __name__ == "__main__":
    print("=" * 50)
    print("Paper Trading Setup & Verification")
    print("=" * 50)
    
    # Setup paper trading
    setup_success = setup_paper_trading()
    
    # Verify setup
    verify_success = verify_setup()
    
    print("\n" + "=" * 50)
    if setup_success and verify_success:
        print("🎉 PAPER TRADING READY!")
        print("\nNext steps for tomorrow:")
        print("1. Start the Flask app: python web_ui/app.py")
        print("2. Open http://localhost:5000/paper-trading")
        print("3. Click 'Start Paper Trading' at 9:15 AM")
        print("4. Watch live trades appear automatically!")
        print("\nStrategy will:")
        print("- Enter ATM Straddle positions between 9:20-14:00")
        print("- Show real-time P&L updates")
        print("- Exit all positions by 15:15")
        print("- Display complete trade history")
    else:
        print("❌ SETUP INCOMPLETE")
        print("Please fix the issues above before paper trading")
    
    print("=" * 50)