#!/usr/bin/env python3
"""
Web-based Trading Dashboard
Simple Flask app to visualize portfolio, strategies, and trades
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import sys
import os
from datetime import datetime
import json
from functools import wraps

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.kite_manager import KiteManager
from core.config_manager import config_manager, get_trading_config
from core.platform_auth import platform_auth

app = Flask(__name__)
# Use environment variable for secret key in production
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Global Kite manager instance
kite_manager = KiteManager()

# Authentication decorator
def platform_login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if user is authenticated to platform
        session_token = session.get('platform_session_token')
        
        if not session_token or not platform_auth.verify_session(session_token):
            return redirect(url_for('platform_login_page'))
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/platform-login', methods=['GET', 'POST'])
def platform_login_page():
    """Platform login page"""
    if request.method == 'POST':
        password = request.form.get('password', '')
        
        if password and platform_auth.verify_password(password):
            # Create session
            user_ip = request.remote_addr or 'unknown'
            session_token = platform_auth.create_session(user_ip)
            session['platform_session_token'] = session_token
            session.permanent = bool(request.form.get('remember_me'))
            
            return redirect(url_for('dashboard'))
        else:
            return render_template('platform_login.html', 
                                 error='Invalid platform password. Please try again.')
    
    return render_template('platform_login.html')

@app.route('/platform-logout')
def platform_logout():
    """Platform logout"""
    session_token = session.get('platform_session_token')
    if session_token:
        platform_auth.invalidate_session(session_token)
    
    session.clear()
    return redirect(url_for('platform_login_page'))

@app.route('/')
@platform_login_required
def dashboard():
    """Main dashboard page"""
    connection_status = kite_manager.get_connection_status()
    
    if not kite_manager.is_authenticated:
        return render_template('login.html', status=connection_status)
    
    # Ensure instruments are loaded
    if not kite_manager.instruments:
        kite_manager.load_instruments()
    
    # Get portfolio data
    portfolio = kite_manager.get_portfolio()
    positions = kite_manager.get_positions()
    funds = kite_manager.get_funds()
    
    # Get Nifty data
    nifty_ltp = kite_manager.get_nifty_ltp()
    
    return render_template('dashboard.html', 
                         status=connection_status,
                         portfolio=portfolio,
                         positions=positions,
                         funds=funds,
                         nifty_ltp=nifty_ltp)

@app.route('/login')
@platform_login_required
def login():
    """Login page"""
    connection_status = kite_manager.get_connection_status()
    
    if kite_manager.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # Generate login URL
    login_url = kite_manager.kite.login_url()
    
    return render_template('login.html', 
                         status=connection_status,
                         login_url=login_url)

@app.route('/auth')
@platform_login_required
def authenticate():
    """Handle authentication callback"""
    request_token = request.args.get('request_token')
    
    if not request_token:
        return redirect(url_for('login'))
    
    # Authenticate with Kite
    result = kite_manager.authenticate(request_token)
    
    if result['success']:
        # Load instruments after successful authentication
        kite_manager.load_instruments()
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html', 
                             error=result['message'])

@app.route('/api/portfolio')
@platform_login_required
def api_portfolio():
    """API endpoint for portfolio data"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    return jsonify({
        'portfolio': kite_manager.get_portfolio(),
        'positions': kite_manager.get_positions(),
        'funds': kite_manager.get_funds(),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/nifty')
@platform_login_required
def api_nifty():
    """API endpoint for Nifty data"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    nifty_ltp = kite_manager.get_nifty_ltp()
    option_chain = kite_manager.get_option_chain()
    
    return jsonify({
        'ltp': nifty_ltp,
        'option_chain': option_chain,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
@platform_login_required
def api_status():
    """API endpoint for system status"""
    return jsonify(kite_manager.get_connection_status())

@app.route('/api/refresh')
@platform_login_required
def api_refresh():
    """API endpoint to refresh market data"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        # Reload instruments if not loaded
        if not kite_manager.instruments:
            kite_manager.load_instruments()
        
        # Get fresh data
        portfolio = kite_manager.get_portfolio()
        positions = kite_manager.get_positions()
        funds = kite_manager.get_funds()
        nifty_ltp = kite_manager.get_nifty_ltp()
        status = kite_manager.get_connection_status()
        
        return jsonify({
            'success': True,
            'data': {
                'portfolio': portfolio,
                'positions': positions, 
                'funds': funds,
                'nifty_ltp': nifty_ltp,
                'status': status
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/strategies')
@platform_login_required
def strategies():
    """Strategy management page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    return render_template('strategies.html')

@app.route('/backtest')
@platform_login_required
def backtest():
    """Backtesting page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    return render_template('backtest.html')

@app.route('/trades')
@platform_login_required
def trades():
    """Trade history page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    orders = kite_manager.get_orders()
    return render_template('trades.html', orders=orders)

@app.route('/options')
@platform_login_required
def options():
    """Options chain page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    return render_template('options.html')

@app.route('/settings')
@platform_login_required
def settings():
    """Settings page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    config = get_trading_config()
    return render_template('settings.html', config=config)

@app.route('/api/config/save', methods=['POST'])
@platform_login_required
def api_config_save():
    """API endpoint to save configuration"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        config_data = request.get_json()
        success = config_manager.update_config(config_data, updated_by="web_ui")
        
        if success:
            return jsonify({'success': True, 'message': 'Configuration saved successfully'})
        else:
            return jsonify({'error': 'Failed to save configuration'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/reset', methods=['POST'])
@platform_login_required
def api_config_reset():
    """API endpoint to reset configuration to defaults"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        success = config_manager.reset_to_defaults()
        
        if success:
            return jsonify({'success': True, 'message': 'Configuration reset to defaults'})
        else:
            return jsonify({'error': 'Failed to reset configuration'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/export')
@platform_login_required
def api_config_export():
    """API endpoint to export configuration"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        config = config_manager.get_config_dict()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/import', methods=['POST'])
@platform_login_required
def api_config_import():
    """API endpoint to import configuration"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        config_data = request.get_json()
        success = config_manager.update_config(config_data, updated_by="import")
        
        if success:
            return jsonify({'success': True, 'message': 'Configuration imported successfully'})
        else:
            return jsonify({'error': 'Failed to import configuration'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/test')
def test_endpoint():
    """Simple test endpoint"""
    return "OK - Flask app is running!"

if __name__ == '__main__':
    # Use fixed port 5000 for Railway - ignore PORT env variable completely
    # This bypasses Railway's problematic PORT='$PORT' issue
    port = 5000
    
    # Check if running in production (cloud) or development (local)
    is_production = os.environ.get('FLASK_ENV') == 'production'
    
    if is_production:
        print("Starting Production Trading Platform Dashboard")
        print(f"Dashboard running on port {port}")
    else:
        print("Starting Personal Trading Platform Dashboard")
        print("Dashboard URL: http://localhost:5000")
        print("Make sure to authenticate with Kite Connect first")
    
    # Use debug mode only in development
    app.run(host='0.0.0.0', port=port, debug=not is_production)