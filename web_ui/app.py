#!/usr/bin/env python3
"""
Nifty Options Trading Platform - Clean Version
Real-time paper and live trading platform for Nifty options
"""

import os
import sys
import logging
from datetime import datetime, time as dt_time
import pytz
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

class DictObj:
    """Simple class to convert dict to object for easier template access"""
    def __init__(self, d):
        if d is None:
            return
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, DictObj(v))
            elif isinstance(v, list):
                setattr(self, k, [DictObj(i) if isinstance(i, dict) else i for i in v])
            else:
                setattr(self, k, v)

from kiteconnect import KiteConnect

# Import trading components
from core.kite_manager import KiteManager
from core.trading_manager import TradingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-nifty-trader')

# Add IST datetime filters for templates
@app.template_filter('ist_date')
def ist_date_filter(dt_str):
    """Convert UTC datetime string to IST date format: 10 Dec 2025"""
    if not dt_str:
        return ''
    try:
        # Parse the datetime string (handle both with and without 'Z')
        if dt_str.endswith('Z'):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        elif '+' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str + '+00:00')
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        dt_ist = dt.astimezone(ist)
        
        # Format as "10 Dec 2025"
        return dt_ist.strftime('%d %b %Y')
    except Exception as e:
        logger.warning(f"Error formatting date {dt_str}: {e}")
        return str(dt_str)

@app.template_filter('ist_time')
def ist_time_filter(dt_str):
    """Convert UTC datetime string to IST time format: 13:03:45"""
    if not dt_str:
        return ''
    try:
        # Parse the datetime string (handle both with and without 'Z')
        if dt_str.endswith('Z'):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        elif '+' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str + '+00:00')
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        dt_ist = dt.astimezone(ist)
        
        # Format as "13:03:45"
        return dt_ist.strftime('%H:%M:%S')
    except Exception as e:
        logger.warning(f"Error formatting time {dt_str}: {e}")
        return str(dt_str)

@app.template_filter('ist_datetime')
def ist_datetime_filter(dt_str):
    """Convert UTC datetime string to IST format: 10 Dec 2025, 13:03:45"""
    if not dt_str:
        return ''
    try:
        # Parse the datetime string (handle both with and without 'Z')
        if dt_str.endswith('Z'):
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        elif '+' in dt_str:
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = datetime.fromisoformat(dt_str + '+00:00')
        
        # Convert to IST
        ist = pytz.timezone('Asia/Kolkata')
        dt_ist = dt.astimezone(ist)
        
        # Format as "10 Dec 2025, 13:03:45"
        return dt_ist.strftime('%d %b %Y, %H:%M:%S')
    except Exception as e:
        logger.warning(f"Error formatting datetime {dt_str}: {e}")
        return str(dt_str)

# Kite Connect setup
KITE_API_KEY = os.getenv('KITE_API_KEY')
KITE_API_SECRET = os.getenv('KITE_API_SECRET')
KITE_REDIRECT_URL = os.getenv('KITE_REDIRECT_URL', 'http://127.0.0.1:5000/auth')

if not KITE_API_KEY or not KITE_API_SECRET:
    logger.error("[ERROR] KITE_API_KEY and KITE_API_SECRET must be set in .env file")
    sys.exit(1)

# Global Kite Connect instance
kite = KiteConnect(api_key=KITE_API_KEY)
kite_authenticated = False
access_token = None

# Initialize trading components
kite_manager = KiteManager()
# Initialize trading manager with default capital
try:
    trading_manager = TradingManager(kite_manager, initial_capital=200000.0)
    print("Trading manager initialized successfully")
except Exception as e:
    print(f"Warning: Could not initialize trading manager: {e}")
    trading_manager = None

def load_access_token():
    """Load existing access token from file"""
    global access_token, kite_authenticated
    try:
        token_file = os.path.join(os.path.dirname(__file__), 'access_token.txt')
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                access_token = f.read().strip()
                if access_token:
                    kite.set_access_token(access_token)
                    # Test authentication
                    try:
                        profile = kite.profile()
                        if isinstance(profile, dict) and 'user_name' in profile:
                            kite_authenticated = True
                            logger.info(f"[SUCCESS] Authenticated as: {profile.get('user_name', 'Unknown')}")
                            return True
                        else:
                            logger.warning("Token exists but invalid")
                            kite_authenticated = False
                    except Exception as e:
                        logger.warning(f"Token validation failed: {e}")
                        kite_authenticated = False
    except Exception as e:
        logger.error(f"Error loading access token: {e}")
    
    kite_authenticated = False
    return False

def save_access_token(token: str):
    """Save access token to file"""
    global access_token, trading_manager
    try:
        access_token = token
        token_file = os.path.join(os.path.dirname(__file__), 'access_token.txt')
        with open(token_file, 'w') as f:
            f.write(token)
        logger.info("[SUCCESS] Access token saved")
        
        # Initialize trading manager after successful authentication
        initialize_trading_manager()
        
        return True
    except Exception as e:
        logger.error(f"Failed to save token: {e}")
        return False


def initialize_trading_manager():
    """Initialize trading manager after Kite authentication"""
    global trading_manager
    try:
        if access_token:
            kite_manager.set_access_token(access_token)
            
            # Only create new trading manager if none exists or if current one is not authenticated
            if trading_manager is None or not trading_manager.kite_manager.is_authenticated:
                trading_manager = TradingManager(kite_manager, initial_capital=200000.0)
                logger.info("[SUCCESS] Trading manager initialized")
            else:
                # Update existing trading manager with new token
                trading_manager.kite_manager.set_access_token(access_token)
                logger.info("[SUCCESS] Trading manager updated with new token")
            return True
        else:
            logger.error("[ERROR] No access token available")
            return False
    except Exception as e:
        logger.error(f"Error initializing trading manager: {e}")
        return False

def requires_auth(f):
    """Decorator to require Kite Connect authentication"""
    def decorated(*args, **kwargs):
        if not kite_authenticated:
            # Check if this is an API request (returns JSON) or web request (returns HTML)
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'message': 'Authentication required. Please log in to Kite Connect.',
                    'redirect_url': '/auth'
                }), 401
            else:
                login_url = kite.login_url()
                return render_template('kite_login.html', 
                                     login_url=login_url,
                                     message="Daily Kite Connect authentication required")
        return f(*args, **kwargs)
    decorated.__name__ = f.__name__
    return decorated

def get_market_status():
    """Get current market status - NO MOCK DATA"""
    try:
        # Get current time in IST
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.now(ist)
        current_time = now.time()
        
        # Market hours: 9:15 AM to 3:30 PM on weekdays
        market_open_time = dt_time(9, 15)
        market_close_time = dt_time(15, 30)
        
        # Check if it's a weekday (Monday = 0, Sunday = 6)
        is_weekday = now.weekday() < 5
        
        # Check if current time is within market hours
        is_market_open = (is_weekday and 
                         market_open_time <= current_time <= market_close_time)
        
        return {
            'market_open': is_market_open,
            'current_time': current_time.strftime('%H:%M:%S'),
            'is_weekday': is_weekday,
            'message': 'Market is open and ready for trading!' if is_market_open else 'Market is currently closed.',
            'next_open': 'Next trading session: Tomorrow 9:15 AM' if not is_market_open else None
        }
        
    except Exception as e:
        logger.error(f"Error getting market status: {e}")
        return {
            'market_open': False,
            'message': f'Error checking market status: {str(e)}'
        }

# Routes
@app.route('/')
def index():
    """Main landing page"""
    return redirect(url_for('paper_dashboard'))

@app.route('/paper')
@app.route('/paper/dashboard')
@requires_auth
def paper_dashboard():
    """Paper trading dashboard with real data from trading manager"""
    try:
        market_status = get_market_status()
        
        # Get real data from trading manager
        if trading_manager is None:
            # Trading manager not initialized
            dashboard_data = {
                'market_status': market_status,
                'kite_authenticated': kite_authenticated,
                'trading_manager_ready': False,
                'strategies': {
                    'scalping': {'active': False, 'pnl': 0.0},
                    'supertrend': {'active': False, 'pnl': 0.0}
                },
                'positions': [],
                'recent_orders': [],
                'portfolio': {
                    'virtual_capital': 200000.0,
                    'available_capital': 200000.0,
                    'total_value': 200000.0,
                    'total_pnl': 0.0,
                    'open_positions': 0
                }
            }
        else:
            # Get real trading data from database and virtual executor
            trading_status = trading_manager.get_trading_status()
            
            # Get portfolio value and margin data from database
            if trading_manager.db_manager:
                try:
                    # Get dashboard metrics for margin calculations
                    from datetime import datetime, timezone
                    import pytz
                    
                    ist = pytz.timezone('Asia/Kolkata')
                    current_date = datetime.now(ist).date()
                    
                    # Get all positions for margin calculation
                    all_positions = trading_manager.db_manager.get_positions(trading_mode='paper')
                    
                    # Fixed initial margin for paper trading
                    initial_margin = 100000.0
                    
                    # Calculate margin used (only for currently OPEN positions)
                    margin_used = 0.0
                    open_positions_count = 0
                    current_day_pnl = 0.0
                    
                    # Calculate total PnL from CLOSED positions (realized gains/losses)
                    total_pnl = 0.0
                    
                    for position in all_positions:
                        try:
                            # Check if position is from current day
                            created_at = datetime.fromisoformat(position['created_at'].replace('Z', '+00:00'))
                            created_at_ist = created_at.astimezone(ist).date()
                            
                            # Add to current day PnL if from today
                            if created_at_ist == current_date:
                                current_day_pnl += position.get('unrealized_pnl', 0.0)
                            
                            # Calculate margin used ONLY for currently OPEN positions
                            if position.get('is_open', False):
                                open_positions_count += 1
                                quantity = position.get('quantity', 0)
                                entry_price = position.get('entry_price', 0.0) or position.get('average_price', 0.0)
                                margin_used += abs(quantity * entry_price)
                            else:
                                # For CLOSED positions, add to total PnL (realized gains/losses)
                                total_pnl += position.get('unrealized_pnl', 0.0)
                                
                        except Exception as e:
                            logger.warning(f"Could not process position for margin calculation: {e}")
                            continue
                    
                    # Calculate available margin: Initial Margin - Margin Used + Total PnL
                    margin_available = initial_margin - margin_used + total_pnl
                    
                    # Current balance (available capital)
                    current_balance = margin_available
                    
                    portfolio = {
                        'initial_margin': initial_margin,
                        'available_capital': current_balance,
                        'total_value': current_balance,
                        'total_pnl': current_day_pnl,  # Show current day PnL
                        'total_pnl_percent': (current_day_pnl / initial_margin * 100) if initial_margin > 0 else 0.0,
                        'total_realized_pnl': total_pnl,  # Total PnL from all closed positions
                        'margin_available': margin_available,
                        'margin_used': margin_used,
                        'open_positions': open_positions_count,
                        'current_day_pnl': current_day_pnl
                    }
                    
                except Exception as e:
                    logger.warning(f"Failed to get database portfolio: {e}")
                    portfolio = trading_manager.order_executor.get_portfolio_summary()
            else:
                portfolio = trading_manager.order_executor.get_portfolio_summary()
            
            # Get positions from database instead of virtual executor for consistency
            if trading_manager.db_manager:
                positions = trading_manager.db_manager.get_positions(trading_mode='paper', is_open=True)
                # Add field mapping for UI compatibility
                for position in positions:
                    position['pnl'] = position.get('unrealized_pnl', 0.0)
            else:
                positions = trading_manager.get_active_positions()
            
            # Get recent orders from database with field mapping
            if trading_manager.db_manager:
                recent_orders_raw = trading_manager.db_manager.get_orders(trading_mode='paper', limit=5)
                recent_orders = []
                for order in recent_orders_raw:
                    order['time'] = order['created_at']
                    order['action'] = order['order_type'] 
                    recent_orders.append(order)
            else:
                recent_orders = trading_manager.get_recent_orders(limit=5)
            
            dashboard_data = {
                'market_status': market_status,
                'kite_authenticated': kite_authenticated,
                'trading_manager_ready': True,
                'trading_active': trading_status.get('trading_active', False),
                'strategies': trading_status.get('strategies', {}),
                'positions': positions,
                'recent_orders': recent_orders,
                'portfolio': portfolio,
                'market_data': trading_status.get('market_data', {})
            }
        
        return render_template('paper_dashboard.html', data=DictObj(dashboard_data))
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        flash(f'Error loading dashboard: {e}', 'error')
        return render_template('paper_dashboard.html', data=DictObj({
            'market_status': {'market_open': False, 'message': 'Error loading market status'},
            'kite_authenticated': False,
            'trading_manager_ready': False,
            'strategies': {},
            'positions': [],
            'recent_orders': [],
            'portfolio': {'virtual_capital': 200000.0, 'available_capital': 200000.0}
        }))

@app.route('/paper/orders')
@requires_auth
def paper_orders():
    """Paper trading orders page with database data"""

    
    try:

        
        if trading_manager is None or trading_manager.db_manager is None:

            orders_data = {
                'orders': [],
                'total_orders': 0,
                'trading_manager_ready': False
            }
        else:
            # Get paper trading orders from database
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            current_date_ist = datetime.now(ist).date()
            
            # Get all paper trading orders
            all_orders = trading_manager.db_manager.get_orders(trading_mode='paper', limit=50)

            
            # Filter for current day and add field mapping for template compatibility
            current_day_orders = []
            for order in all_orders:
                try:
                    created_at_str = order.get('created_at', '')
                    if created_at_str:
                        # Parse UTC datetime and convert to IST
                        order_datetime = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                        order_date_ist = order_datetime.astimezone(ist).date()
                        
                        if order_date_ist == current_date_ist:
                            # Add field mapping for template compatibility
                            order['time'] = order['created_at']
                            order['action'] = order['order_type']
                            order['timestamp'] = order['created_at']
                            order['strategy'] = order['strategy_name']  # Template expects 'strategy'
                            order['pnl'] = 0  # Default P&L for orders
                            current_day_orders.append(order)
                except Exception as e:

                    logger.warning(f"Error processing order date: {e}")
                    continue
            

            
            orders_data = {
                'orders': current_day_orders,
                'total_orders': len(current_day_orders),
                'trading_manager_ready': True
            }
        
        # Log successful data retrieval
        logger.info(f"Orders page: Found {len(current_day_orders)} orders for template")
        if current_day_orders:
            logger.info(f"First order fields: {list(current_day_orders[0].keys())}")
            
        return render_template('paper_orders.html', data=orders_data)
        
    except Exception as e:
        logger.error(f"Orders page error: {e}")
        return render_template('paper_orders.html', data={
            'orders': [],
            'total_orders': 0,
            'trading_manager_ready': False,
            'error': str(e)
        })

@app.route('/debug-orders')
@requires_auth  
def debug_orders():
    """Debug route to test data flow"""
    try:
        import pytz
        from core.database_manager import DatabaseManager
        
        # Get current date in IST
        ist = pytz.timezone('Asia/Kolkata')
        current_date_ist = datetime.now(ist).date()
        
        # Get orders from database
        all_orders = trading_manager.db_manager.get_orders(trading_mode='paper', limit=50)
        
        # Test the filtering logic
        current_day_orders = []
        debug_info = []
        
        for i, order in enumerate(all_orders[:5]):  # Check first 5 orders
            created_at_str = order.get('created_at', '')
            if created_at_str:
                try:
                    # Parse UTC datetime and convert to IST
                    order_datetime = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    order_date_ist = order_datetime.astimezone(ist).date()
                    
                    debug_info.append({
                        'order_index': i,
                        'created_at_raw': created_at_str,
                        'order_date_ist': str(order_date_ist),
                        'current_date_ist': str(current_date_ist),
                        'matches': order_date_ist == current_date_ist
                    })
                    
                    if order_date_ist == current_date_ist:
                        current_day_orders.append(order)
                except Exception as e:
                    debug_info.append({
                        'order_index': i,
                        'error': str(e),
                        'created_at_raw': created_at_str
                    })
        
        return {
            'debug': True,
            'total_db_orders': len(all_orders),
            'filtered_orders': len(current_day_orders),
            'current_date_ist': str(current_date_ist),
            'debug_info': debug_info
        }
    except Exception as e:
        return {'error': str(e)}

@app.route('/paper/positions')
@requires_auth  
def paper_positions():
    """Paper trading positions page with real data from database"""
    try:
        if trading_manager is None or trading_manager.db_manager is None:
            positions_data = {
                'positions': [],
                'total_pnl': 0.0,
                'margin_used': 0.0,
                'active_positions': 0,
                'trading_manager_ready': False
            }
        else:
            # Get current day positions (both open and closed) from database
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            current_date_ist = datetime.now(ist).date()
            
            # Get all positions and filter for current day
            all_positions = trading_manager.db_manager.get_positions(trading_mode='paper')
            db_positions = []
            
            for position in all_positions:
                try:
                    # Parse created_at and convert to IST
                    created_at = datetime.fromisoformat(position['created_at'].replace('Z', '+00:00'))
                    created_at_ist = created_at.astimezone(ist).date()
                    
                    # Include if position is from current day
                    if created_at_ist == current_date_ist:
                        db_positions.append(position)
                except Exception as e:
                    logger.warning(f"Error processing position date: {e}")
                    continue
            
            # Get portfolio value from database
            try:
                daily_perf = trading_manager.db_manager.supabase.table('daily_pnl').select('portfolio_value').eq('date', datetime.now().date()).eq('trading_mode', 'paper').order('updated_at', desc=True).limit(1).execute()
                portfolio_value = daily_perf.data[0]['portfolio_value'] if daily_perf.data else 200000.0
            except:
                portfolio_value = 200000.0
            
            # Add field mapping for template compatibility
            for position in db_positions:
                # Fix Issue 2: Use realized_pnl for closed positions, unrealized_pnl for open positions
                if position.get('is_open', False):
                    position['pnl'] = position.get('unrealized_pnl', 0.0)
                else:
                    position['pnl'] = position.get('realized_pnl', 0.0)
                    
                position['entry_price'] = position.get('average_price', 0.0)
                
                # Fix Issue 1: Add original_quantity for closed position calculations
                # For closed positions, get original quantity from orders table
                if not position.get('is_open', False) and position.get('quantity', 0) == 0:
                    # Find the original BUY order for this position
                    symbol = position.get('symbol', '')
                    strategy = position.get('strategy_name', '')
                    entry_time = position.get('entry_time', '')
                    
                    try:
                        # Get BUY order for this position based on symbol and time
                        buy_orders = trading_manager.db_manager.supabase.table('orders').select('quantity').eq('symbol', symbol).eq('order_type', 'BUY').eq('trading_mode', 'paper').order('created_at', desc=False).execute()
                        
                        if buy_orders.data:
                            position['original_quantity'] = buy_orders.data[0]['quantity']
                        else:
                            position['original_quantity'] = abs(position.get('quantity', 75))  # Fallback
                    except Exception as e:
                        position['original_quantity'] = 75  # Fallback to default lot size
                else:
                    position['original_quantity'] = abs(position.get('quantity', 0))
                
                # Handle current_price vs exit_price based on position status
                if position.get('is_open', False):
                    # For open positions: show current market price
                    position['current_price'] = position.get('current_price', position.get('average_price', 0.0))
                    position['exit_price'] = None  # No exit price yet
                else:
                    # For closed positions: show exit price, no current price
                    position['current_price'] = None  # No current price for closed positions
                    position['exit_price'] = position.get('exit_price', position.get('current_price', 0.0))
                
                position['entry_time'] = position.get('entry_time', position.get('created_at', ''))
                position['exit_time'] = position.get('exit_time', None) if not position.get('is_open', False) else None
                position['strategy'] = position.get('strategy_name', 'Unknown')
                
                # Add pnl_percent for template
                position['pnl_percent'] = position.get('pnl_percent', 0.0)
                
                # Add status badge for open/closed
                position['status_badge'] = 'success' if position.get('is_open', False) else 'secondary'
                position['status_text'] = 'OPEN' if position.get('is_open', False) else 'CLOSED'
            
            # Calculate totals for current day positions (PnL from today only)
            total_pnl = sum(pos.get('unrealized_pnl', 0.0) for pos in db_positions)
            
            # Margin Used = investment in ALL OPEN positions (consistent with dashboard)
            # Get all positions (not just current day) for margin calculation
            all_positions = trading_manager.db_manager.get_positions(trading_mode='paper')
            margin_used = sum(abs(pos.get('quantity', 0)) * (pos.get('entry_price', 0.0) or pos.get('average_price', 0.0)) 
                            for pos in all_positions if pos.get('is_open', False))

            positions_data = {
                'positions': db_positions,
                'total_pnl': total_pnl,
                'margin_used': margin_used,
                'active_positions': len(db_positions),
                'trading_manager_ready': True,
                'portfolio_value': portfolio_value
            }
        
        return render_template('paper_positions.html', data=positions_data)
        
    except Exception as e:
        logger.error(f"Positions page error: {e}")
        return render_template('paper_positions.html', data={
            'positions': [],
            'total_pnl': 0.0,
            'margin_used': 0.0,
            'active_positions': 0,
            'trading_manager_ready': False,
            'error': str(e)
        })

@app.route('/auth')
def kite_auth_callback():
    """Handle Kite Connect authentication callback"""
    global kite_authenticated
    
    try:
        request_token = request.args.get('request_token')
        if not request_token:
            flash('Authentication failed: No request token received', 'error')
            return redirect(url_for('paper_dashboard'))
        
        # Generate access token
        data = kite.generate_session(request_token, api_secret=KITE_API_SECRET)
        
        if isinstance(data, dict) and 'access_token' in data:
            token = data['access_token']
            kite.set_access_token(token)
            save_access_token(token)
            kite_authenticated = True
            
            logger.info("[SUCCESS] Kite Connect authentication successful")
            flash('Kite Connect authentication successful! Platform ready for trading.', 'success')
        else:
            flash('Authentication failed: Invalid response from Kite Connect', 'error')
        
        return redirect(url_for('paper_dashboard'))
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        flash(f'Authentication failed: {e}', 'error')
        return redirect(url_for('paper_dashboard'))

@app.route('/api/market-status')
def api_market_status():
    """API endpoint for market status"""
    market_status = get_market_status()
    return jsonify({
        'success': True,
        **market_status
    })

@app.route('/api/trading-status')
def api_trading_status():
    """Get current trading status with real data from trading manager"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': True,
                'kite_authenticated': kite_authenticated,
                'market_status': get_market_status(),
                'paper_trading': {
                    'strategies_active': 0,
                    'positions_count': 0,
                    'total_pnl': 0.0,
                    'trading_active': False
                },
                'timestamp': datetime.now().isoformat()
            })
        
        # Get real trading status from trading manager
        trading_status = trading_manager.get_trading_status()
        
        # Add running strategies info
        trading_status['running_strategies'] = trading_manager.get_running_strategies()
        
        return jsonify({
            'success': True,
            'kite_authenticated': kite_authenticated,
            'trading_status': trading_status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting trading status: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/start-trading', methods=['POST'])
@requires_auth
def api_start_trading():
    """Start automated trading"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        # Get strategy list from request (optional)
        data = request.get_json() or {}
        strategies = data.get('strategies', ['scalping', 'supertrend'])  # Default to both strategies
        
        # Validate strategies exist
        valid_strategies = [s for s in strategies if s in trading_manager.strategies]
        if not valid_strategies:
            return jsonify({
                'success': False,
                'message': 'No valid strategies specified'
            }), 400
        
        success = trading_manager.start_trading(valid_strategies)
        
        if success:
            running_strategies = trading_manager.get_running_strategies()
            return jsonify({
                'success': True,
                'message': f'Trading started with strategies: {", ".join(valid_strategies)}',
                'strategies': valid_strategies,
                'running_strategies': running_strategies
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to start trading - check market hours and authentication'
            }), 400
            
    except Exception as e:
        logger.error(f"Error starting trading: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/stop-trading', methods=['POST'])
@requires_auth
def api_stop_trading():
    """Stop automated trading"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        # Get strategy list from request (optional)
        data = request.get_json() or {}
        strategies = data.get('strategies', None)  # None means stop all
        
        trading_manager.stop_trading(strategies)
        
        running_strategies = trading_manager.get_running_strategies()
        
        if strategies:
            return jsonify({
                'success': True,
                'message': f'Stopped strategies: {", ".join(strategies)}',
                'running_strategies': running_strategies
            })
        else:
            return jsonify({
                'success': True,
                'message': 'All trading stopped',
                'running_strategies': []
            })
        
    except Exception as e:
        logger.error(f"Error stopping trading: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/portfolio')
@requires_auth
def api_portfolio():
    """Get portfolio summary"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': True,
                'portfolio': {
                    'initial_capital': 200000.0,
                    'available_capital': 200000.0,
                    'total_value': 200000.0,
                    'total_pnl': 0.0,
                    'open_positions': 0,
                    'position_details': []
                }
            })
        
        portfolio = trading_manager.order_executor.get_portfolio_summary()
        
        return jsonify({
            'success': True,
            'portfolio': portfolio
        })
        
    except Exception as e:
        logger.error(f"Error getting portfolio: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/positions')
@requires_auth
def api_positions():
    """Get current day positions (both open and closed) from database"""
    try:
        # Use direct database connection instead of relying on trading_manager
        from core.database_manager import DatabaseManager
        from datetime import datetime, timezone
        import pytz
        
        db_manager = DatabaseManager()
        
        if not db_manager:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            })
        
        # Get current day in IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(ist).date()
        current_date_str = current_date.strftime('%Y-%m-%d')
        
        # Get all positions for the current day (both open and closed)
        all_positions = db_manager.get_positions(trading_mode='paper')
        
        # Filter positions for current day only
        current_day_positions = []
        for position in all_positions:
            # Parse the created_at timestamp and convert to IST
            try:
                created_at = datetime.fromisoformat(position['created_at'].replace('Z', '+00:00'))
                created_at_ist = created_at.astimezone(ist).date()
                
                if created_at_ist == current_date:
                    # Add position status and PnL fields for UI compatibility
                    position['status'] = 'OPEN' if position.get('is_open', False) else 'CLOSED'
                    position['exit_time'] = position.get('exit_time', None) if not position.get('is_open', False) else None
                    
                    # Set PnL based on position status (use unrealized_pnl for both as it contains the correct PnL)
                    position['pnl'] = position.get('unrealized_pnl', 0.0)
                    
                    current_day_positions.append(position)
            except Exception as e:
                logger.warning(f"Could not parse position date: {e}")
                continue
        
        # Calculate total PnL for the day
        total_pnl = sum(pos.get('pnl', 0.0) for pos in current_day_positions)
        
        # Calculate margin used (same formula as dashboard - ALL OPEN positions regardless of date)
        margin_used = 0.0
        for position in all_positions:  # Use all_positions, not just current_day_positions
            if position.get('is_open', False):
                quantity = position.get('quantity', 0)
                entry_price = position.get('entry_price', 0.0) or position.get('average_price', 0.0)
                margin_used += abs(quantity * entry_price)
        
        return jsonify({
            'success': True,
            'positions': current_day_positions,
            'total_pnl': total_pnl,
            'current_date': current_date_str,
            'margin_used': margin_used
        })
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/dashboard-metrics')
@requires_auth
def api_dashboard_metrics():
    """Get dashboard metrics including margin and balance information"""
    try:
        from core.database_manager import DatabaseManager
        from datetime import datetime, timezone
        import pytz
        
        db_manager = DatabaseManager()
        
        if not db_manager:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            })
        
        # Get current day in IST timezone
        ist = pytz.timezone('Asia/Kolkata')
        current_date = datetime.now(ist).date()
        
        # Get all positions for margin calculation
        all_positions = db_manager.get_positions(trading_mode='paper')
        
        # Fixed initial margin for paper trading
        initial_margin = 100000.0
        
        # Calculate margin used (only for currently OPEN positions)
        margin_used = 0.0
        open_positions_count = 0
        current_day_pnl = 0.0
        
        # Calculate total PnL from CLOSED positions (realized gains/losses)
        total_pnl = 0.0
        
        for position in all_positions:
            try:
                # Check if position is from current day
                created_at = datetime.fromisoformat(position['created_at'].replace('Z', '+00:00'))
                created_at_ist = created_at.astimezone(ist).date()
                
                # Add to current day PnL if from today
                if created_at_ist == current_date:
                    current_day_pnl += position.get('unrealized_pnl', 0.0)
                
                # Calculate margin used ONLY for currently OPEN positions
                if position.get('is_open', False):
                    open_positions_count += 1
                    quantity = position.get('quantity', 0)
                    entry_price = position.get('entry_price', 0.0) or position.get('average_price', 0.0)
                    margin_used += abs(quantity * entry_price)
                else:
                    # For CLOSED positions, add to total PnL (realized gains/losses)
                    total_pnl += position.get('unrealized_pnl', 0.0)
                    
            except Exception as e:
                logger.warning(f"Could not process position for metrics: {e}")
                continue
        
        # Calculate available margin: Initial Margin - Margin Used + Total PnL
        margin_available = initial_margin - margin_used + total_pnl
        
        # Current balance (available capital)
        current_balance = margin_available
        
        return jsonify({
            'success': True,
            'metrics': {
                'initial_margin': initial_margin,
                'current_balance': current_balance,
                'margin_available': margin_available,
                'margin_used': margin_used,
                'current_day_pnl': current_day_pnl,
                'total_pnl': total_pnl,  # Total PnL from all closed positions
                'open_positions_count': open_positions_count,
                'current_date': current_date.strftime('%Y-%m-%d')
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/orders')
@requires_auth
def api_orders():
    """Get current day order history from database"""
    try:
        limit = int(request.args.get('limit', 100))  # Increased for frequent trading
        
        # Use direct database connection instead of relying on trading_manager
        from core.database_manager import DatabaseManager
        db_manager = DatabaseManager()
        
        if not db_manager:
            return jsonify({
                'success': False,
                'message': 'Database connection failed'
            })
        
        # Get current day orders with timezone-aware filtering
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        current_date_ist = datetime.now(ist).date()
        
        # Get orders from database using direct connection
        all_orders = db_manager.get_orders(trading_mode='paper', limit=limit)
        
        # Filter for current day with proper timezone conversion and add field mapping
        current_day_orders = []
        for order in all_orders:
            try:
                created_at_str = order.get('created_at', '')
                if created_at_str:
                    # Parse UTC datetime and convert to IST
                    order_datetime = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    order_date_ist = order_datetime.astimezone(ist).date()
                    
                    if order_date_ist == current_date_ist:
                        # Add field mapping for UI compatibility
                        order['time'] = order['created_at']  # Dashboard expects 'time'
                        order['action'] = order['order_type']  # Dashboard expects 'action'
                        order['timestamp'] = order['created_at']  # Orders page expects 'timestamp'
                        current_day_orders.append(order)
            except Exception as e:
                logger.warning(f"Error processing order date: {e}")
                continue
        
        orders = current_day_orders
        
        return jsonify({
            'success': True,
            'orders': orders
        })
        
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/order-integrity')
@requires_auth
def api_order_integrity():
    """Check order integrity - verify BUY and SELL orders are properly saved"""
    try:
        from core.virtual_order_executor import VirtualOrderExecutor
        from core.database_manager import DatabaseManager
        
        db_manager = DatabaseManager()
        executor = VirtualOrderExecutor(initial_capital=100000, db_manager=db_manager)
        
        integrity_result = executor.verify_order_integrity()
        
        return jsonify({
            'success': True,
            'integrity_check': integrity_result
        })
        
    except Exception as e:
        logger.error(f"Error checking order integrity: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500


@app.route('/api/close-position', methods=['POST'])
@requires_auth
def api_close_position():
    """Manually close a position"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        data = request.get_json()
        if not data or 'symbol' not in data:
            return jsonify({
                'success': False,
                'message': 'Symbol required'
            }), 400
        
        symbol = data['symbol']
        success = trading_manager.manual_close_position(symbol)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Position {symbol} closed successfully'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to close position {symbol}'
            }), 400
            
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/strategy/<strategy_name>/start', methods=['POST'])
@requires_auth
def api_start_individual_strategy(strategy_name):
    """Start a specific trading strategy"""
    try:
        logger.info(f"Attempting to start strategy: {strategy_name}")
        
        if trading_manager is None:
            logger.error("Trading manager not initialized")
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        if strategy_name not in trading_manager.strategies:
            logger.error(f"Strategy {strategy_name} not found. Available: {list(trading_manager.strategies.keys())}")
            return jsonify({
                'success': False,
                'message': f'Strategy "{strategy_name}" not found'
            }), 404
        
        if trading_manager.is_strategy_running(strategy_name):
            logger.warning(f"Strategy {strategy_name} is already running")
            return jsonify({
                'success': False,
                'message': f'{strategy_name.title()} strategy is already running. Please stop it first.',
                'strategy': strategy_name,
                'is_running': True
            }), 400
        
        # Log current status
        logger.info(f"Market open: {trading_manager.market_data.is_market_open()}")
        logger.info(f"Kite authenticated: {trading_manager.kite_manager.is_authenticated}")
        logger.info(f"Current active strategies: {trading_manager.active_strategies}")
        
        success = trading_manager.start_trading([strategy_name])
        
        if success:
            logger.info(f"Successfully started {strategy_name} strategy")
            return jsonify({
                'success': True,
                'message': f'{strategy_name.title()} strategy started successfully',
                'strategy': strategy_name,
                'is_running': True
            })
        else:
            logger.error(f"Failed to start {strategy_name} strategy")
            return jsonify({
                'success': False,
                'message': f'Failed to start {strategy_name} strategy - check market hours and authentication'
            }), 400
            
    except Exception as e:
        logger.error(f"Error starting {strategy_name} strategy: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/strategy/<strategy_name>/stop', methods=['POST'])
@requires_auth
def api_stop_individual_strategy(strategy_name):
    """Stop a specific trading strategy"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        if strategy_name not in trading_manager.strategies:
            return jsonify({
                'success': False,
                'message': f'Strategy "{strategy_name}" not found'
            }), 404
        
        if not trading_manager.is_strategy_running(strategy_name):
            return jsonify({
                'success': False,
                'message': f'Strategy "{strategy_name}" is not currently running'
            }), 400
        
        trading_manager.stop_trading([strategy_name])
        
        return jsonify({
            'success': True,
            'message': f'{strategy_name.title()} strategy stopped successfully',
            'strategy': strategy_name,
            'is_running': False
        })
        
    except Exception as e:
        logger.error(f"Error stopping {strategy_name} strategy: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/trading/keepalive', methods=['POST'])
def api_trading_keepalive():
    """Keep trading manager alive and restart if stopped"""
    try:
        if trading_manager is None:
            return jsonify({
                'success': False,
                'message': 'Trading manager not initialized'
            }), 400
        
        # Check if trading manager is running
        if not trading_manager.is_running and trading_manager.active_strategies:
            logger.warning("Trading manager stopped but has active strategies - restarting")
            success = trading_manager.start_trading(trading_manager.active_strategies)
            if success:
                logger.info("Trading manager restarted successfully")
                return jsonify({
                    'success': True,
                    'message': 'Trading manager restarted',
                    'is_running': trading_manager.is_running,
                    'active_strategies': trading_manager.active_strategies
                })
            else:
                logger.error("Failed to restart trading manager")
                return jsonify({
                    'success': False,
                    'message': 'Failed to restart trading manager'
                }), 500
        
        return jsonify({
            'success': True,
            'message': 'Trading manager is running',
            'is_running': trading_manager.is_running,
            'active_strategies': trading_manager.active_strategies
        })
        
    except Exception as e:
        logger.error(f"Error in trading keepalive: {e}")
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/debug/strategies')
def api_debug_strategies():
    """Debug endpoint to check current strategy status"""
    try:
        if trading_manager is None:
            return jsonify({
                'trading_manager': None,
                'error': 'Trading manager not initialized'
            })
        
        return jsonify({
            'trading_manager': 'initialized',
            'is_running': trading_manager.is_running,
            'available_strategies': list(trading_manager.strategies.keys()),
            'active_strategies': trading_manager.active_strategies,
            'market_open': trading_manager.market_data.is_market_open() if trading_manager.market_data else None,
            'kite_authenticated': trading_manager.kite_manager.is_authenticated if trading_manager.kite_manager else None
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/api/database/orders')
def api_database_orders():
    """Get order history from database"""
    try:
        if not trading_manager or not trading_manager.db_manager:
            return jsonify({'error': 'Database not available'}), 400
        
        # Get query parameters
        strategy_name = request.args.get('strategy')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        
        orders = trading_manager.db_manager.get_orders(
            strategy_name=strategy_name,
            status=status,
            trading_mode=trading_manager.trading_mode,
            limit=limit
        )
        
        return jsonify({'orders': orders})
    
    except Exception as e:
        logger.error(f"Error getting orders from database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/positions')
def api_database_positions():
    """Get position history from database"""
    try:
        if not trading_manager or not trading_manager.db_manager:
            return jsonify({'error': 'Database not available'}), 400
        
        # Get query parameters
        strategy_name = request.args.get('strategy')
        is_open = request.args.get('is_open')
        if is_open is not None:
            is_open = is_open.lower() == 'true'
        
        positions = trading_manager.db_manager.get_positions(
            strategy_name=strategy_name,
            trading_mode=trading_manager.trading_mode,
            is_open=is_open
        )
        
        return jsonify({'positions': positions})
    
    except Exception as e:
        logger.error(f"Error getting positions from database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/trades')
def api_database_trades():
    """Get trade history from database"""
    try:
        if not trading_manager or not trading_manager.db_manager:
            return jsonify({'error': 'Database not available'}), 400
        
        # Get query parameters
        strategy_name = request.args.get('strategy')
        limit = int(request.args.get('limit', 100))
        
        trades = trading_manager.db_manager.get_trades(
            strategy_name=strategy_name,
            trading_mode=trading_manager.trading_mode,
            limit=limit
        )
        
        return jsonify({'trades': trades})
    
    except Exception as e:
        logger.error(f"Error getting trades from database: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/performance')
def api_database_performance():
    """Get performance analytics from database"""
    try:
        if not trading_manager:
            return jsonify({'error': 'Trading manager not initialized'}), 400
        
        days = int(request.args.get('days', 30))
        analytics = trading_manager.get_performance_analytics(days)
        
        return jsonify({'analytics': analytics})
    
    except Exception as e:
        logger.error(f"Error getting performance analytics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/database/daily_pnl')
def api_database_daily_pnl():
    """Get daily P&L data from database"""
    try:
        if not trading_manager or not trading_manager.db_manager:
            return jsonify({'error': 'Database not available'}), 400
        
        # Get query parameters
        strategy_name = request.args.get('strategy')
        days = int(request.args.get('days', 30))
        
        from datetime import timedelta
        date_from = (datetime.now() - timedelta(days=days)).date().isoformat()
        
        daily_pnl = trading_manager.db_manager.get_daily_pnl(
            strategy_name=strategy_name,
            trading_mode=trading_manager.trading_mode,
            date_from=date_from
        )
        
        return jsonify({'daily_pnl': daily_pnl})
    
    except Exception as e:
        logger.error(f"Error getting daily P&L: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'nifty-options-trader',
        'timestamp': datetime.now().isoformat(),
        'kite_connected': kite_authenticated
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'message': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error', 'message': 'Something went wrong'}), 500

if __name__ == '__main__':
    # Load existing access token on startup
    load_access_token()
    
    # Initialize trading manager if authenticated
    if kite_authenticated and access_token:
        try:
            initialize_trading_manager()
        except Exception as e:
            logger.error(f"Failed to initialize trading manager on startup: {e}")
    
    logger.info("[STARTUP] Starting Nifty Options Trading Platform...")
    logger.info(f"[CONFIG] Kite API Key: {KITE_API_KEY}")
    logger.info(f"[CONFIG] Redirect URL: {KITE_REDIRECT_URL}")
    logger.info(f"[AUTH] Authentication Status: {'Connected' if kite_authenticated else 'Not Connected'}")
    logger.info(f"[MANAGER] Trading Manager: {'Ready' if trading_manager is not None else 'Not Ready'}")
    
    # Start Flask development server
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=True,
        use_reloader=True
    )