#!/usr/bin/env python3
"""
Web-based Trading Dashboard
Simple Flask app to visualize portfolio, strategies, and trades
"""

from flask import Flask, render_template, jsonify, request, redirect, url_for, session, flash
import sys
import os
import logging
from datetime import datetime
import json
from functools import wraps

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.kite_manager import KiteManager
from core.config_manager import config_manager, get_trading_config
from core.platform_auth import platform_auth
from analytics.options_data_provider import OptionsDataProvider
from analytics.options_greeks_calculator import OptionsGreeksCalculator
from analytics.volatility_analyzer import VolatilityAnalyzer
from analytics.max_pain_analyzer import MaxPainAnalyzer
from analytics.ml_models import ModelTrainer, InferenceEngine, LSTMPricePredictor

app = Flask(__name__)
# Use environment variable for secret key in production
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Global instances
kite_manager = KiteManager()
options_data_provider = OptionsDataProvider(kite_manager)
greeks_calculator = OptionsGreeksCalculator()
volatility_analyzer = VolatilityAnalyzer()
max_pain_analyzer = MaxPainAnalyzer()

# ML instances
model_trainer = ModelTrainer(kite_manager)
inference_engine = InferenceEngine()

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
    
    connection_status = kite_manager.get_connection_status()
    return render_template('strategies.html', status=connection_status)

@app.route('/backtest')
@platform_login_required
def backtest():
    """Backtesting page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    connection_status = kite_manager.get_connection_status()
    return render_template('backtest.html', status=connection_status)

@app.route('/trades')
@platform_login_required
def trades():
    """Trade history page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    connection_status = kite_manager.get_connection_status()
    orders = kite_manager.get_orders()
    return render_template('trades.html', status=connection_status, orders=orders)

@app.route('/options')
@platform_login_required
def options():
    """Options chain page with advanced analytics"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    connection_status = kite_manager.get_connection_status()
    
    # Use LIVE data provider ONLY - no fallbacks or mock data
    try:
        # Get options chain data using LIVE provider only
        options_chain = options_data_provider.get_options_chain('NIFTY')
        
        # Check for errors in live data fetching
        if options_chain.get('error'):
            # Return error page instead of showing mock data
            error_message = options_chain['error']
            logging.error(f"Live data error: {error_message}")
            return render_template('error.html', 
                                 status=connection_status, 
                                 error=error_message,
                                 page_title="Options Chain Data Error")
        
        # Validate live data structure
        if not options_chain or not options_chain.get('data') or not options_chain.get('spot_price'):
            error_message = "❌ No live options data available. Please check Kite Connect authentication."
            logging.error(error_message)
            return render_template('error.html', 
                                 status=connection_status, 
                                 error=error_message,
                                 page_title="Options Chain Data Error")
        
        # Calculate Max Pain if we have data
        max_pain_analysis = {}
        if options_chain.get('data'):
            try:
                max_pain_analysis = max_pain_analyzer.calculate_max_pain(options_chain)
            except Exception as e:
                logging.warning(f"Max Pain calculation failed: {e}")
                max_pain_analysis = {}
        
        # Analyze volatility
        iv_analysis = {}
        if options_chain.get('data'):
            try:
                iv_analysis = volatility_analyzer.analyze_volatility_skew(options_chain)
            except Exception as e:
                logging.warning(f"Volatility analysis failed: {e}")
                iv_analysis = {}
        
        # Calculate Greeks for ATM options (example)
        greeks_examples = {}
        spot_price = options_chain.get('spot_price', 0)
        if not spot_price:
            logging.error("❌ No spot price available for Greeks calculation")
            spot_price = 0
        if options_chain.get('data'):
            try:
                # Find ATM strike
                atm_strike = min(options_chain['data'], 
                               key=lambda x: abs(x['strike_price'] - spot_price))['strike_price']
                
                # Calculate Greeks for ATM Call and Put
                greeks_examples = {
                    'atm_call': greeks_calculator.calculate_all_greeks(
                        spot_price, atm_strike, 0.1, 0.2, 'CE'
                    ),
                    'atm_put': greeks_calculator.calculate_all_greeks(
                        spot_price, atm_strike, 0.1, 0.2, 'PE'
                    )
                }
            except Exception as e:
                logging.warning(f"Greeks calculation failed: {e}")
                greeks_examples = {}
    
    except Exception as e:
        error_message = f"❌ Critical error loading options analytics: {str(e)}"
        logging.error(error_message)
        return render_template('error.html', 
                             status=connection_status, 
                             error=error_message,
                             page_title="Options Chain System Error")
    
    return render_template('options.html', 
                         status=connection_status, 
                         option_chain=options_chain,
                         max_pain_analysis=max_pain_analysis,
                         iv_analysis=iv_analysis,
                         greeks_examples=greeks_examples)

@app.route('/settings')
@platform_login_required
def settings():
    """Settings page"""
    if not kite_manager.is_authenticated:
        return redirect(url_for('login'))
    
    connection_status = kite_manager.get_connection_status()
    config = get_trading_config()
    return render_template('settings.html', status=connection_status, config=config)

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

# ===========================================
# STRATEGY MANAGEMENT API ENDPOINTS
# ===========================================

# Global execution engine instance
execution_engine = None

@app.route('/api/strategies')
@platform_login_required
def api_strategies():
    """API endpoint to get all available strategies"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        from strategies.execution_engine import StrategyExecutionEngine
        
        # Initialize execution engine if needed
        global execution_engine
        if execution_engine is None:
            execution_engine = StrategyExecutionEngine(kite_manager)
        
        strategies = execution_engine.get_available_strategies()
        
        return jsonify({
            'success': True,
            'strategies': strategies,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/create', methods=['POST'])
@platform_login_required
def api_create_strategy():
    """API endpoint to create a new strategy"""
    try:
        data = request.get_json()
        
        name = data.get('name')
        description = data.get('description', '')
        strategy_class = data.get('strategy_class')
        parameters = data.get('parameters', {})
        
        if not name or not strategy_class:
            return jsonify({'error': 'Name and strategy class are required'}), 400
        
        # Initialize execution engine to ensure strategies are registered
        # Note: We don't require Kite authentication for strategy configuration
        global execution_engine
        if execution_engine is None:
            try:
                from strategies.execution_engine import StrategyExecutionEngine
                execution_engine = StrategyExecutionEngine(kite_manager)
            except Exception as init_error:
                # If execution engine fails, try to register strategies manually
                print(f"Execution engine init failed: {init_error}, registering strategies manually")
                from strategies.strategy_registry import strategy_registry
                from strategies.options_strategy import ATMStraddleStrategy, IronCondorStrategy
                strategy_registry.register_strategy(ATMStraddleStrategy)
                strategy_registry.register_strategy(IronCondorStrategy)
        
        from strategies.strategy_registry import strategy_registry
        
        success = strategy_registry.create_strategy_config(
            name=name,
            description=description,
            strategy_class=strategy_class,
            parameters=parameters,
            author="web_ui"
        )
        
        if success:
            return jsonify({'success': True, 'message': 'Strategy created successfully'})
        else:
            return jsonify({'error': 'Failed to create strategy - strategy class may not be registered'}), 500
            
    except Exception as e:
        print(f"Strategy creation error: {e}")  # Debug logging
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/execution-status')
@platform_login_required
def api_execution_status():
    """API endpoint to get execution status"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        global execution_engine
        if execution_engine is None:
            from strategies.execution_engine import StrategyExecutionEngine
            execution_engine = StrategyExecutionEngine(kite_manager)
        
        status = execution_engine.get_execution_status()
        
        return jsonify({
            'success': True,
            **status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/start-execution', methods=['POST'])
@platform_login_required
def api_start_execution():
    """API endpoint to start strategy execution"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        strategies = data.get('strategies', [])
        
        if not strategies:
            return jsonify({'error': 'No strategies specified'}), 400
        
        global execution_engine
        if execution_engine is None:
            from strategies.execution_engine import StrategyExecutionEngine
            execution_engine = StrategyExecutionEngine(kite_manager)
        
        session_id = execution_engine.start_execution_session(strategies)
        
        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': 'Execution session started successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/stop-execution', methods=['POST'])
@platform_login_required
def api_stop_execution():
    """API endpoint to stop strategy execution"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        global execution_engine
        if execution_engine is None:
            return jsonify({'error': 'No execution engine active'}), 400
        
        success = execution_engine.stop_execution_session()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Execution session stopped successfully'
            })
        else:
            return jsonify({'error': 'Failed to stop execution session'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/strategies/backtest', methods=['POST'])
@platform_login_required
def api_run_backtest():
    """API endpoint to run strategy backtest"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        
        strategy_name = data.get('strategy_name')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        initial_capital = data.get('initial_capital', 100000)
        
        if not all([strategy_name, start_date, end_date]):
            return jsonify({'error': 'Missing required parameters'}), 400
        
        # Parse dates
        from datetime import datetime
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Run backtest
        from backtest.backtesting_engine import BacktestEngine
        backtest_engine = BacktestEngine()
        
        result = backtest_engine.run_backtest(
            strategy_name=strategy_name,
            start_date=start_dt,
            end_date=end_dt,
            initial_capital=initial_capital
        )
        
        return jsonify({
            'success': True,
            'result': result.to_dict() if hasattr(result, 'to_dict') else result,
            'message': 'Backtest completed successfully'
        })
        
    except Exception as e:
        print(f"Backtest error: {e}")  # Use print for now, logger will be set up later
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for Railway"""
    print(f"Health check accessed at {datetime.now()}")
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

@app.route('/test')
def test_endpoint():
    """Simple test endpoint"""
    return f"OK - Flask app is running on Railway! Time: {datetime.now().isoformat()}"

@app.route('/ping')
def ping():
    """Ultra simple ping endpoint"""
    return "PONG"

@app.route('/debug')
def debug_info():
    """Debug information without authentication"""
    import os
    return f"""
    <html>
    <head>
        <title>Debug Info</title>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    </head>
    <body>
        <h2>Debug Info</h2>
        <p>Flask is running!</p>
        <p>Environment: {os.environ.get('FLASK_ENV', 'not set')}</p>
        <p>Time: {datetime.now()}</p>
        <p>Session: {dict(session)}</p>
        <div id="jquery-test">Testing jQuery...</div>
        <script>
            $(document).ready(function() {{
                $('#jquery-test').text('jQuery is working! Version: ' + $.fn.jquery);
                console.log('jQuery loaded successfully');
            }});
        </script>
        <a href="/platform-login">Go to Platform Login</a>
    </body>
    </html>
    """

# Options Analytics API Endpoints
@app.route('/api/options/expiry-dates')
@platform_login_required
def api_get_expiry_dates():
    """API endpoint to get available expiry dates from Kite Connect"""
    if not kite_manager.is_authenticated:
        return jsonify({'error': 'Not authenticated'}), 401
    
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        
        # Ensure instruments are loaded
        if not kite_manager.instruments:
            kite_manager.load_instruments()
        
        # Get real expiry dates from options data provider
        expiry_dates = options_data_provider._get_expiry_dates(symbol)
        
        if not expiry_dates:
            return jsonify({'error': 'No expiry dates available from Kite Connect'}), 404
        
        # Format expiry dates for frontend
        formatted_dates = []
        for expiry_str in expiry_dates:
            try:
                # Parse and format the date
                expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d')
                formatted_dates.append({
                    'date': expiry_str,
                    'label': expiry_date.strftime('%b %d'),  # e.g., "Oct 07"
                    'full_label': expiry_date.strftime('%d %b %Y')  # e.g., "07 Oct 2025"
                })
            except ValueError:
                # Skip invalid dates
                continue
        
        return jsonify({
            'success': True,
            'expiry_dates': formatted_dates,
            'count': len(formatted_dates),
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error in expiry dates API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options/chain')
@platform_login_required
def api_get_options_chain():
    """API endpoint to get options chain data"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        expiry = request.args.get('expiry', None)
        
        options_chain = options_data_provider.get_options_chain(symbol, expiry)
        return jsonify(options_chain)
    
    except Exception as e:
        logging.error(f"Error in options chain API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options/max-pain')
@platform_login_required
def api_get_max_pain():
    """API endpoint to get Max Pain analysis"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        expiry = request.args.get('expiry', None)
        
        options_chain = options_data_provider.get_options_chain(symbol, expiry)
        max_pain_analysis = max_pain_analyzer.calculate_max_pain(options_chain)
        
        return jsonify(max_pain_analysis)
    
    except Exception as e:
        logging.error(f"Error in Max Pain API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options/greeks')
@platform_login_required
def api_calculate_greeks():
    """API endpoint to calculate Greeks for specific option"""
    try:
        spot_price = request.args.get('spot_price')
        strike_price = request.args.get('strike_price')
        
        if not spot_price or not strike_price:
            return jsonify({'error': 'spot_price and strike_price are required parameters'}), 400
            
        try:
            spot_price = float(spot_price)
            strike_price = float(strike_price)
        except ValueError:
            return jsonify({'error': 'spot_price and strike_price must be valid numbers'}), 400
        time_to_expiry = float(request.args.get('time_to_expiry', 0.1))
        volatility = float(request.args.get('volatility', 0.2))
        option_type = request.args.get('option_type', 'CE')
        
        greeks = greeks_calculator.calculate_all_greeks(
            spot_price, strike_price, time_to_expiry, volatility, option_type
        )
        
        return jsonify(greeks)
    
    except Exception as e:
        logging.error(f"Error in Greeks API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options/volatility-analysis')
@platform_login_required
def api_volatility_analysis():
    """API endpoint to get volatility analysis"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        expiry = request.args.get('expiry', None)
        
        options_chain = options_data_provider.get_options_chain(symbol, expiry)
        volatility_analysis = volatility_analyzer.analyze_volatility_skew(options_chain)
        
        return jsonify(volatility_analysis)
    
    except Exception as e:
        logging.error(f"Error in volatility analysis API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/options/key-levels')
@platform_login_required
def api_key_levels():
    """API endpoint to get key support/resistance levels"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        expiry = request.args.get('expiry', None)
        
        options_chain = options_data_provider.get_options_chain(symbol, expiry)
        key_levels = max_pain_analyzer.identify_key_levels(options_chain)
        
        return jsonify(key_levels)
    
    except Exception as e:
        logging.error(f"Error in key levels API: {e}")
        return jsonify({'error': str(e)}), 500

# Machine Learning Endpoints

@app.route('/ml-predictions')
@platform_login_required 
def ml_predictions_page():
    """ML predictions dashboard page"""
    return render_template('ml_predictions.html')

@app.route('/api/ml/train-model')
@platform_login_required
def api_train_model():
    """API endpoint to train LSTM model"""
    try:
        # Get parameters
        period_days = int(request.args.get('period_days', 252))  # Default 1 year
        model_type = request.args.get('model_type', 'lstm')
        force_retrain = bool(request.args.get('force_retrain', False))
        
        if model_type.lower() != 'lstm':
            return jsonify({'error': 'Only LSTM model supported currently'}), 400
        
        # Train model
        result = model_trainer.train_lstm_model(
            symbol='^NSEI',  # Nifty symbol for yfinance
            period_days=period_days,
            force_retrain=force_retrain
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Model training completed successfully',
            'result': result
        })
    
    except Exception as e:
        logging.error(f"Error in model training API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/ml/predict-price')
@platform_login_required
def api_predict_price():
    """API endpoint to get price predictions"""
    try:
        # Get parameters
        model_name = request.args.get('model_name', 'lstm_price_predictor')
        use_cache = bool(request.args.get('use_cache', True))
        
        # Get predictions
        prediction_result = inference_engine.predict_price(
            model_name=model_name, 
            use_cache=use_cache
        )
        
        return jsonify({
            'status': 'success',
            'model_name': model_name,
            'prediction': {
                'prediction_value': prediction_result.prediction_value,
                'confidence_score': prediction_result.confidence_score,
                'prediction_type': prediction_result.prediction_type,
                'features_used': prediction_result.features_used,
                'model_name': prediction_result.model_name,
                'timestamp': prediction_result.timestamp.isoformat(),
                'additional_info': prediction_result.additional_info
            },
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error in price prediction API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/ml/trading-signals')
@platform_login_required
def api_trading_signals():
    """API endpoint to get ML-based trading signals"""
    try:
        symbol = request.args.get('symbol', 'NIFTY')
        
        # Get trading signals
        signals = inference_engine.get_trading_signals(symbol)
        
        return jsonify({
            'status': 'success',
            'symbol': symbol,
            'signals': signals,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error in trading signals API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/ml/model-status')
@platform_login_required
def api_model_status():
    """API endpoint to get ML model status"""
    try:
        stats = inference_engine.get_inference_stats()
        
        return jsonify({
            'status': 'success',
            'inference_stats': stats,
            'loaded_models': list(inference_engine.loaded_models.keys()),
            'cache_size': len(inference_engine.prediction_cache),
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        logging.error(f"Error in model status API: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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