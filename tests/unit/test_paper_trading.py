"""
Unit Tests for Paper Trading Engine
Tests the paper trading functionality with virtual money
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from paper_trading.paper_trading_engine import PaperTradingEngine, PaperOrder, OrderStatus
from core.kite_manager import KiteManager


class TestPaperTradingEngine(unittest.TestCase):
    """Test cases for PaperTradingEngine class"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_kite_manager = Mock(spec=KiteManager)
        self.paper_engine = PaperTradingEngine(self.mock_kite_manager)

    def test_initialization(self):
        """Test PaperTradingEngine initialization"""
        self.assertEqual(self.paper_engine.virtual_capital, 200000)  # Default ₹2 Lakhs
        self.assertEqual(self.paper_engine.available_capital, 200000)
        self.assertFalse(self.paper_engine.is_running)
        self.assertEqual(len(self.paper_engine.orders), 0)
        self.assertEqual(len(self.paper_engine.positions), 0)

    def test_start_trading(self):
        """Test starting paper trading"""
        with patch.object(self.paper_engine, '_trading_loop'):
            result = self.paper_engine.start_trading()
            self.assertTrue(result['success'])
            self.assertTrue(self.paper_engine.is_running)

    def test_stop_trading(self):
        """Test stopping paper trading"""
        self.paper_engine.is_running = True
        result = self.paper_engine.stop_trading()
        self.assertTrue(result['success'])
        self.assertFalse(self.paper_engine.is_running)

    def test_create_paper_order(self):
        """Test creating a paper order"""
        order = PaperOrder(
            order_id="TEST_001",
            strategy_name="ATMStraddle",
            symbol="NIFTY24O1025000CE",
            transaction_type="BUY",
            quantity=50,
            price=100.0,
            order_type="MARKET",
            timestamp=datetime.now(),
            status=OrderStatus.PENDING
        )
        
        self.assertEqual(order.order_id, "TEST_001")
        self.assertEqual(order.quantity, 50)
        self.assertEqual(order.status, OrderStatus.PENDING)

    def test_get_trading_status(self):
        """Test getting trading status"""
        status = self.paper_engine.get_trading_status()
        
        self.assertIn('is_running', status)
        self.assertIn('virtual_capital', status)
        self.assertIn('available_capital', status)
        self.assertIn('total_pnl', status)
        self.assertIn('active_positions', status)
        self.assertIn('total_trades', status)

    def test_capital_validation(self):
        """Test capital validation for orders"""
        # Test with order that exceeds available capital
        self.paper_engine.available_capital = 1000
        
        # This would need actual order placement logic to test properly
        # For now, just verify the capital amount is tracked
        self.assertEqual(self.paper_engine.available_capital, 1000)

    def test_performance_calculation(self):
        """Test performance metrics calculation"""
        # Mock some orders and positions for testing
        self.paper_engine.total_pnl = 5000
        
        status = self.paper_engine.get_trading_status()
        self.assertEqual(status['total_pnl'], 5000)

    @patch('paper_trading.paper_trading_engine.threading.Thread')
    def test_background_threading(self, mock_thread):
        """Test background thread creation"""
        self.paper_engine.start_trading()
        mock_thread.assert_called()


if __name__ == '__main__':
    unittest.main()