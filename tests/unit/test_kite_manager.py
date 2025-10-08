"""
Unit Tests for KiteManager
Tests the core Kite Connect integration functionality
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from core.kite_manager import KiteManager


class TestKiteManager(unittest.TestCase):
    """Test cases for KiteManager class"""

    def setUp(self):
        """Set up test fixtures"""
        self.kite_manager = KiteManager()

    @patch('core.kite_manager.KiteConnect')
    def test_initialization(self, mock_kite_connect):
        """Test KiteManager initialization"""
        manager = KiteManager()
        self.assertIsNotNone(manager.kite)
        self.assertFalse(manager.is_authenticated)
        self.assertEqual(manager.api_call_delay, 0.2)

    def test_rate_limiting(self):
        """Test API rate limiting functionality"""
        import time
        start_time = time.time()
        self.kite_manager._rate_limit()
        self.kite_manager._rate_limit()
        end_time = time.time()
        
        # Should have some delay between calls
        self.assertGreater(end_time - start_time, 0.1)

    @patch('core.kite_manager.open', create=True)
    def test_load_access_token_file_not_found(self, mock_open):
        """Test loading access token when file doesn't exist"""
        mock_open.side_effect = FileNotFoundError()
        
        manager = KiteManager()
        # Should handle missing file gracefully
        self.assertFalse(manager.is_authenticated)

    def test_market_hours_check(self):
        """Test market hours validation"""
        # Mock datetime to test market hours
        with patch('core.kite_manager.datetime') as mock_datetime:
            # Test during market hours (weekday, 10 AM)
            mock_datetime.now.return_value.weekday.return_value = 1  # Tuesday
            mock_datetime.now.return_value.replace.return_value = mock_datetime.now.return_value
            
            # This test would need more sophisticated mocking for full coverage
            is_open = self.kite_manager.is_market_open()
            self.assertIsInstance(is_open, bool)

    def test_get_connection_status(self):
        """Test connection status reporting"""
        status = self.kite_manager.get_connection_status()
        
        self.assertIn('authenticated', status)
        self.assertIn('api_key_configured', status)
        self.assertIn('access_token_available', status)
        self.assertIn('instruments_loaded', status)
        self.assertIn('market_open', status)

    def test_quote_method_error_handling(self):
        """Test quote method error handling"""
        # Test with mock instruments
        result = self.kite_manager.quote(['INVALID_INSTRUMENT'])
        self.assertEqual(result, {})

    def test_ltp_method_error_handling(self):
        """Test LTP method error handling"""
        # Test with mock instruments
        result = self.kite_manager.ltp(['INVALID_INSTRUMENT'])
        self.assertEqual(result, {})


if __name__ == '__main__':
    unittest.main()