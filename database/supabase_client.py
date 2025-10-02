# database/supabase_client.py
"""
Supabase Database Client for Trading Platform
Handles data persistence, retrieval, and management
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
import json

# Try to import supabase, fall back to local storage if not available
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = Any

from config.settings import TradingConfig
from database.models import TradeRecord, AnalysisRecord, PositionRecord, PerformanceRecord, SystemEvent

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database manager with Supabase backend and local fallback"""
    
    def __init__(self):
        """Initialize database connection"""
        self.client = None
        self.use_local_storage = True
        
        # Try to connect to Supabase
        if SUPABASE_AVAILABLE and TradingConfig.SUPABASE_URL and TradingConfig.SUPABASE_KEY:
            try:
                self.client = create_client(
                    TradingConfig.SUPABASE_URL,
                    TradingConfig.SUPABASE_KEY
                )
                self.use_local_storage = False
                logger.info("✅ Connected to Supabase database")
                
                # Test connection
                self._test_connection()
                
            except Exception as e:
                logger.warning(f"⚠️ Supabase connection failed: {e}")
                logger.info("🔄 Falling back to local file storage")
                self.use_local_storage = True
        else:
            logger.info("📁 Using local file storage (Supabase not configured)")
        
        # Initialize local storage if needed
        if self.use_local_storage:
            self._init_local_storage()
    
    def _test_connection(self) -> None:
        """Test Supabase connection"""
        if self.client:
            try:
                # Try to query a table (will create if doesn't exist)
                result = self.client.table('system_events').select('*').limit(1).execute()
                logger.debug("🔗 Supabase connection test successful")
            except Exception as e:
                logger.error(f"❌ Supabase connection test failed: {e}")
                raise
    
    def _init_local_storage(self) -> None:
        """Initialize local file storage"""
        import os
        
        self.storage_dir = 'data/database'
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize JSON files
        self.files = {
            'trades': os.path.join(self.storage_dir, 'trades.json'),
            'analysis': os.path.join(self.storage_dir, 'analysis.json'),
            'positions': os.path.join(self.storage_dir, 'positions.json'),
            'performance': os.path.join(self.storage_dir, 'performance.json'),
            'events': os.path.join(self.storage_dir, 'events.json')
        }
        
        # Create files if they don't exist
        for file_path in self.files.values():
            if not os.path.exists(file_path):
                with open(file_path, 'w') as f:
                    json.dump([], f)
        
        logger.info(f"📁 Local storage initialized at {self.storage_dir}")
    
    def save_trade(self, trade: TradeRecord) -> bool:
        """Save trade record"""
        try:
            if self.use_local_storage:
                return self._save_to_local_file('trades', trade.to_dict())
            else:
                return self._save_to_supabase('trades', trade.to_dict())
        except Exception as e:
            logger.error(f"❌ Failed to save trade: {e}")
            return False
    
    def save_analysis(self, analysis: AnalysisRecord) -> bool:
        """Save analysis record"""
        try:
            if self.use_local_storage:
                return self._save_to_local_file('analysis', analysis.to_dict())
            else:
                return self._save_to_supabase('analysis_records', analysis.to_dict())
        except Exception as e:
            logger.error(f"❌ Failed to save analysis: {e}")
            return False
    
    def save_position(self, position: PositionRecord) -> bool:
        """Save position record"""
        try:
            if self.use_local_storage:
                return self._save_to_local_file('positions', position.to_dict())
            else:
                return self._save_to_supabase('positions', position.to_dict())
        except Exception as e:
            logger.error(f"❌ Failed to save position: {e}")
            return False
    
    def save_performance(self, performance: PerformanceRecord) -> bool:
        """Save performance record"""
        try:
            if self.use_local_storage:
                return self._save_to_local_file('performance', performance.to_dict())
            else:
                return self._save_to_supabase('performance_records', performance.to_dict())
        except Exception as e:
            logger.error(f"❌ Failed to save performance: {e}")
            return False
    
    def save_event(self, event: SystemEvent) -> bool:
        """Save system event"""
        try:
            if self.use_local_storage:
                return self._save_to_local_file('events', event.to_dict())
            else:
                return self._save_to_supabase('system_events', event.to_dict())
        except Exception as e:
            logger.error(f"❌ Failed to save event: {e}")
            return False
    
    def get_trades(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[TradeRecord]:
        """Get trade records"""
        try:
            if self.use_local_storage:
                data = self._load_from_local_file('trades')
                trades = [TradeRecord.from_dict(item) for item in data]
            else:
                if self.client:
                    query = self.client.table('trades').select('*')
                    if start_date:
                        query = query.gte('timestamp', start_date.isoformat())
                    if end_date:
                        query = query.lte('timestamp', end_date.isoformat())
                    
                    result = query.execute()
                    trades = [TradeRecord.from_dict(item) for item in result.data]
                else:
                    trades = []
            
            # Filter by date if using local storage
            if self.use_local_storage and (start_date or end_date):
                trades = [
                    t for t in trades
                    if (not start_date or t.timestamp >= start_date) and
                       (not end_date or t.timestamp <= end_date)
                ]
            
            return trades
            
        except Exception as e:
            logger.error(f"❌ Failed to get trades: {e}")
            return []
    
    def get_daily_performance(self, date: datetime) -> Optional[PerformanceRecord]:
        """Get performance record for specific date"""
        try:
            target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
            
            if self.use_local_storage:
                data = self._load_from_local_file('performance')
                for item in data:
                    record_date = datetime.fromisoformat(item['date'].replace('Z', '+00:00'))
                    if record_date.date() == target_date.date():
                        return PerformanceRecord(**item)
                return None
            else:
                if self.client:
                    result = self.client.table('performance_records').select('*').eq('date', target_date.isoformat()).execute()
                    if result.data:
                        return PerformanceRecord(**result.data[0])
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get daily performance: {e}")
            return None
    
    def get_recent_analysis(self, hours: int = 24) -> List[AnalysisRecord]:
        """Get recent analysis records"""
        try:
            since = datetime.now() - timedelta(hours=hours)
            
            if self.use_local_storage:
                data = self._load_from_local_file('analysis')
                records = []
                for item in data:
                    record_time = datetime.fromisoformat(item['timestamp'].replace('Z', '+00:00'))
                    if record_time >= since:
                        records.append(AnalysisRecord(**item))
                return sorted(records, key=lambda x: x.timestamp, reverse=True)
            else:
                if self.client:
                    result = self.client.table('analysis_records').select('*').gte('timestamp', since.isoformat()).execute()
                    return [AnalysisRecord(**item) for item in result.data]
                return []
                
        except Exception as e:
            logger.error(f"❌ Failed to get recent analysis: {e}")
            return []
    
    def _save_to_local_file(self, file_key: str, data: Dict[str, Any]) -> bool:
        """Save data to local JSON file"""
        try:
            file_path = self.files[file_key]
            
            # Load existing data
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
            
            # Add new data
            existing_data.append(data)
            
            # Keep only last 1000 records to prevent files from growing too large
            if len(existing_data) > 1000:
                existing_data = existing_data[-1000:]
            
            # Save back to file
            with open(file_path, 'w') as f:
                json.dump(existing_data, f, indent=2, default=str)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save to local file: {e}")
            return False
    
    def _load_from_local_file(self, file_key: str) -> List[Dict[str, Any]]:
        """Load data from local JSON file"""
        try:
            file_path = self.files[file_key]
            with open(file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load from local file: {e}")
            return []
    
    def _save_to_supabase(self, table_name: str, data: Dict[str, Any]) -> bool:
        """Save data to Supabase table"""
        try:
            if self.client:
                result = self.client.table(table_name).insert(data).execute()
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Failed to save to Supabase: {e}")
            return False
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get system statistics"""
        try:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get today's trades
            today_trades = self.get_trades(start_date=today)
            
            # Get recent analysis
            recent_analysis = self.get_recent_analysis(hours=24)
            
            return {
                'storage_type': 'Local Files' if self.use_local_storage else 'Supabase',
                'trades_today': len(today_trades),
                'analysis_today': len(recent_analysis),
                'total_pnl_today': sum(t.pnl for t in today_trades),
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get system stats: {e}")
            return {}
    
    def close(self) -> None:
        """Close database connections"""
        if self.client:
            # Supabase client doesn't need explicit closing
            pass
        logger.info("📊 Database connections closed")

# Export main class
__all__ = ['DatabaseManager']