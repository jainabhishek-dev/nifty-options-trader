# auth_handler.py
"""
Kite Connect Authentication Handler for Nifty Options Trading
Handles OAuth flow, token generation, and connection testing
"""

from kiteconnect import KiteConnect
from flask import Flask, request, redirect
import os
from dotenv import load_dotenv
import webbrowser
import logging
from datetime import datetime
from config.settings import TradingConfig
from typing import Dict, List, Any, Optional, Union

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = Flask(__name__)

class KiteAuthenticator:
    """Handles Kite Connect authentication and testing"""
    
    def __init__(self):
        self.api_key = TradingConfig.KITE_API_KEY
        self.api_secret = TradingConfig.KITE_API_SECRET
        
        if not self.api_key or not self.api_secret:
            raise ValueError("❌ Kite API credentials not found in environment variables")
        
        # Initialize Kite client with increased timeout for better reliability
        self.kite = KiteConnect(api_key=self.api_key, timeout=30)  # 30 second timeout
        logger.info("🔧 Kite Connect client initialized")
        
        # Load existing access token if available
        self._load_existing_token()
    
    def _load_existing_token(self) -> None:
        """Load existing access token from file if available"""
        try:
            with open('access_token.txt', 'r') as f:
                access_token = f.read().strip()
            
            if access_token:
                self.kite.set_access_token(access_token)
                logger.info("🔑 Loaded existing access token from file")
            else:
                logger.warning("⚠️ Empty access token file found")
                
        except FileNotFoundError:
            logger.info("📄 No existing access token file found - will need authentication")
        except Exception as e:
            logger.error(f"❌ Failed to load access token: {e}")
        
    def get_login_url(self) -> str:
        """Generate Kite Connect login URL"""
        login_url = self.kite.login_url()
        logger.info(f"🔗 Generated login URL: {login_url}")
        return login_url
    
    def generate_session(self, request_token: str) -> Optional[str]:
        """Generate access token from request token"""
        try:
            logger.info(f"🔄 Processing request token: {request_token[:10]}...")
            
            # KiteConnect.generate_session returns a dict or bytes
            response: Union[Dict[str, Any], bytes, Any] = self.kite.generate_session(request_token, self.api_secret)
            
            # Handle response type
            if isinstance(response, dict):
                access_token: str = response.get("access_token", "")
            else:
                logger.error(f"❌ Unexpected response type from Kite Connect: {type(response)}")
                return None
            
            if not access_token:
                logger.error("❌ No access token received from Kite Connect")
                return None
            
            # Save access token to file
            with open('access_token.txt', 'w') as f:
                f.write(access_token)
            logger.info("💾 Access token saved to access_token.txt")
            
            # Update .env file
            self._update_env_file('KITE_ACCESS_TOKEN', access_token)
            logger.info("📝 Access token updated in .env file")
            
            # Set access token in kite instance
            self.kite.set_access_token(access_token)
            
            # Test the connection immediately
            self._comprehensive_connection_test()
            
            return access_token
            
        except Exception as e:
            logger.error(f"❌ Authentication failed: {e}")
            return None
    
    def _update_env_file(self, key: str, value: str):
        """Update environment file with new value"""
        env_file = '.env'
        
        # Read existing content
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Update or add the key
        with open(env_file, 'w') as f:
            updated = False
            for line in lines:
                if line.startswith(f"{key}="):
                    f.write(f"{key}={value}\n")
                    updated = True
                else:
                    f.write(line)
            
            # If key wasn't found, add it
            if not updated:
                f.write(f"{key}={value}\n")
    
    def _comprehensive_connection_test(self) -> None:
        """Comprehensive test of Kite Connect functionality"""
        logger.info("🧪 Starting comprehensive connection test...")
        
        try:
            # Test 1: Profile access
            profile_response: Union[Dict[str, Any], bytes, Any] = self.kite.profile()
            
            if isinstance(profile_response, dict):
                user_name = profile_response.get('user_name', 'Unknown')
                email = profile_response.get('email', 'Unknown')
                logger.info(f"✅ Profile Test: Welcome {user_name} ({email})")
            else:
                logger.warning(f"⚠️ Profile response type: {type(profile_response)}")
                logger.info("✅ Profile Test: Connected (response format different)")
            
            # Test 2: Nifty 50 quote
            quote_response: Union[Dict[Any, Any], bytes, Any] = self.kite.quote(["NSE:NIFTY 50"])
            
            if isinstance(quote_response, dict):
                nifty_data = quote_response.get("NSE:NIFTY 50", {})
                if isinstance(nifty_data, dict):
                    nifty_ltp = nifty_data.get("last_price", 0)
                    logger.info(f"✅ Market Data Test: Nifty 50 LTP = ₹{nifty_ltp}")
                else:
                    logger.info("✅ Market Data Test: Quote data received (format different)")
            else:
                logger.info("✅ Market Data Test: Connected to market data")
            
            # Test 3: Options instruments access
            instruments_response: Union[List[Dict[str, Any]], bytes, Any] = self.kite.instruments("NFO")
            
            if isinstance(instruments_response, list):
                nifty_options = [
                    i for i in instruments_response 
                    if isinstance(i, dict) and 
                    'NIFTY' in str(i.get('name', '')) and 
                    i.get('instrument_type') in ['CE', 'PE']
                ]
                
                if nifty_options:
                    total_nifty_options = len(nifty_options)
                    logger.info(f"✅ Options Test: Found {total_nifty_options} Nifty options contracts")
                    
                    # Show sample options
                    logger.info("📋 Sample Nifty Options:")
                    for i, opt in enumerate(nifty_options[:3]):
                        symbol = opt.get('tradingsymbol', 'Unknown')
                        strike = opt.get('strike', 0)
                        expiry = opt.get('expiry', 'Unknown')
                        logger.info(f"   {i+1}. {symbol} | Strike: {strike} | Expiry: {expiry}")
                else:
                    logger.warning("⚠️ No Nifty options found")
            else:
                logger.info("✅ Options Test: Instruments data received (processing skipped)")
            
            # Test 4: Historical data access (if Connect API)
            try:
                from datetime import datetime, timedelta
                to_date = datetime.now()
                from_date = to_date - timedelta(days=5)
                
                # Get Nifty historical data
                historical_data = self.kite.historical_data(
                    instrument_token=256265,  # Nifty 50 token
                    from_date=from_date,
                    to_date=to_date,
                    interval="day"
                )
                
                if historical_data:
                    logger.info(f"✅ Historical Data Test: Retrieved {len(historical_data)} days of Nifty data")
                else:
                    logger.warning("⚠️ Historical data access limited (Personal API tier)")
                    
            except Exception as e:
                logger.warning(f"⚠️ Historical data test failed: {str(e)[:100]}...")
            
            # Test 5: Funds and margins
            try:
                margins_response: Union[Dict[str, Any], bytes, Any] = self.kite.margins()
                
                if isinstance(margins_response, dict):
                    equity_data = margins_response.get('equity', {})
                    if isinstance(equity_data, dict):
                        available_data = equity_data.get('available', {})
                        if isinstance(available_data, dict):
                            available_cash = available_data.get('cash', 0)
                            logger.info(f"✅ Account Test: Available cash = ₹{available_cash:,.2f}")
                        else:
                            logger.info("✅ Account Test: Margins data received")
                    else:
                        logger.info("✅ Account Test: Account connected")
                else:
                    logger.info("✅ Account Test: Margins endpoint accessible")
            except Exception as e:
                logger.warning(f"⚠️ Margins test failed: {str(e)[:50]}...")
            
            # Test 6: Portfolio positions
            try:
                positions_response: Union[Dict[str, Any], bytes, Any] = self.kite.positions()
                
                if isinstance(positions_response, dict):
                    net_positions_list = positions_response.get('net', [])
                    if isinstance(net_positions_list, list):
                        net_positions = len(net_positions_list)
                        logger.info(f"✅ Positions Test: {net_positions} current positions")
                    else:
                        logger.info("✅ Positions Test: Positions data received")
                else:
                    logger.info("✅ Positions Test: Positions endpoint accessible")
            except Exception as e:
                logger.warning(f"⚠️ Positions test failed: {str(e)[:50]}...")
            
            logger.info("🎉 All core tests completed successfully!")
            logger.info("🚀 Your Nifty options trading system is ready!")
            
        except Exception as e:
            logger.error(f"❌ Connection test failed: {e}")
            raise

# Flask routes for OAuth callback
@app.route('/callback')
def callback() -> str:
    """Handle OAuth callback from Kite Connect"""
    request_token: Optional[str] = request.args.get('request_token')
    
    if request_token:
        authenticator = KiteAuthenticator()
        access_token: Optional[str] = authenticator.generate_session(request_token)
        
        if access_token:
            return f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Authentication Successful</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 50px; background: #f0f8ff; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
                    .success {{ color: #28a745; font-size: 24px; font-weight: bold; margin-bottom: 20px; }}
                    .info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                    .token {{ font-family: monospace; background: #f8f9fa; padding: 10px; border-radius: 3px; word-break: break-all; }}
                    .next-steps {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">🎉 Authentication Successful!</div>
                    
                    <div class="info">
                        <h3>✅ Connection Verified</h3>
                        <p>Your Nifty options trading system is now connected to Zerodha Kite Connect.</p>
                    </div>
                    
                    <div class="info">
                        <h3>🔐 Access Token</h3>
                        <div class="token">{access_token[:20]}...</div>
                        <small>Token saved to access_token.txt and .env file</small>
                    </div>
                    
                    <div class="next-steps">
                        <h3>🚀 Next Steps</h3>
                        <ol>
                            <li>Close this browser window</li>
                            <li>Return to VS Code</li>
                            <li>Check the terminal for test results</li>
                            <li>Start building your trading strategies!</li>
                        </ol>
                    </div>
                </div>
                
                <script>
                    setTimeout(function() {{
                        if (confirm('Authentication complete! Close this window?')) {{
                            window.close();
                        }}
                    }}, 3000);
                </script>
            </body>
            </html>
            """
        else:
            return """
            <h2 style="color: red;">❌ Authentication Failed</h2>
            <p>Please check your API credentials and try again.</p>
            """
    
    return """
    <h2 style="color: red;">❌ No Request Token</h2>
    <p>Invalid callback request. Please restart the authentication process.</p>
    """

def main() -> None:
    """Main authentication flow"""
    print("🚀 Starting Nifty Options Trading Platform Authentication...")
    print("=" * 60)
    
    try:
        authenticator = KiteAuthenticator()
        login_url = authenticator.get_login_url()
        
        print(f"\n📱 STEP 1: Please visit this URL to authenticate:")
        print(f"🔗 {login_url}")
        print(f"\n🌐 Opening browser automatically in 3 seconds...")
        print("   (If browser doesn't open, copy the URL above)")
        
        # Small delay then open browser
        import time
        time.sleep(3)
        webbrowser.open(login_url)
        
        print(f"\n🔄 STEP 2: Complete login in browser...")
        print("   - Enter your Zerodha credentials")
        print("   - You'll be redirected back automatically")
        print("   - Look for success message")
        
        print(f"\n⚙️ STEP 3: Starting callback server...")
        print("   - Server running on http://127.0.0.1:8000")
        print("   - Waiting for authentication callback...")
        print("   - Press Ctrl+C to stop if needed")
        print("=" * 60)
        
        app.run(host='127.0.0.1', port=8000, debug=False)
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Authentication cancelled by user")
    except Exception as e:
        print(f"\n❌ Authentication setup failed: {e}")
        print("\n🔧 Please check:")
        print("  - Your .env file has correct API keys")
        print("  - Internet connection is working")
        print("  - Kite Connect app is properly configured")

if __name__ == '__main__':
    main()
