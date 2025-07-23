# backend/app/main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import traceback

app = FastAPI(title="Investment Rebalancing WebApp")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables to track initialization
initialization_status = {
    "config_loaded": False,
    "auth_created": False,
    "auth_successful": False,
    "service_created": False,
    "investment_service_created": False,
    "error_message": None,
    "zerodha_connection_status": "not_checked"
}

zerodha_auth = None
portfolio_service = None
investment_service = None

# Initialize step by step with error tracking
try:
    print("Step 1: Loading configuration...")
    from .config import settings
    initialization_status["config_loaded"] = True
    print("✅ Configuration loaded successfully")
    
    print("Step 2: Creating ZerodhaAuth instance...")
    from .auth import ZerodhaAuth
    zerodha_auth = ZerodhaAuth()
    initialization_status["auth_created"] = True
    print("✅ ZerodhaAuth instance created")
    
    print("Step 3: Creating portfolio service...")
    from .services.portfolio_service import PortfolioService
    portfolio_service = PortfolioService(zerodha_auth)
    initialization_status["service_created"] = True
    print("✅ Portfolio service created")
    
    print("Step 4: Creating investment service...")
    from .services.investment_service import InvestmentService
    investment_service = InvestmentService(zerodha_auth)
    initialization_status["investment_service_created"] = True
    print("✅ Investment service created")
    
except Exception as e:
    error_msg = f"Initialization error: {str(e)}\n{traceback.format_exc()}"
    print(f"❌ {error_msg}")
    initialization_status["error_message"] = error_msg

# Include routers AFTER services are created
try:
    print("Step 5: Setting up routers...")
    
    # Import and setup investment router
    from .routers.investment import router as investment_router
    
    # Set the investment service dependency BEFORE including router
    from .routers import investment
    investment.investment_service = investment_service
    
    # Include the router with proper prefix
    app.include_router(investment_router, prefix="/api")
    print("✅ Investment router included at /api/investment/*")
    
except Exception as e:
    print(f"⚠️ Could not set up routers: {e}")
    print(f"   Traceback: {traceback.format_exc()}")

@app.get("/")
async def root():
    return {
        "message": "Investment Rebalancing WebApp API", 
        "status": initialization_status,
        "available_endpoints": [
            "/health - Health check",
            "/api/test-live-prices - Test live price fetching",
            "/api/test-auth - Test Zerodha authentication",
            "/api/investment/requirements - Get investment requirements",
            "/api/investment/calculate-plan - Calculate investment plan",
            "/api/investment/execute-initial - Execute initial investment",
            "/api/investment/rebalancing-check - Check rebalancing status",
            "/api/investment/calculate-rebalancing - Calculate rebalancing plan",
            "/api/investment/execute-rebalancing - Execute rebalancing",
            "/api/investment/portfolio-status - Get portfolio status",
            "/api/investment/csv-stocks - Get CSV stocks with prices",
            "/api/investment/system-orders - Get system orders history"
        ]
    }

@app.get("/health")
async def health_check():
    """Comprehensive health check with honest status reporting"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "initialization": initialization_status.copy(),
        "zerodha_connection": {
            "available": False,
            "authenticated": False,
            "can_fetch_data": False,
            "error_message": None
        },
        "services": {
            "portfolio_service": bool(portfolio_service),
            "investment_service": bool(investment_service),
            "zerodha_auth": bool(zerodha_auth)
        }
    }
    
    # Test Zerodha connection if available
    if zerodha_auth:
        try:
            print("🔍 Testing Zerodha connection...")
            
            # Check if already authenticated
            if zerodha_auth.is_authenticated():
                health_status["zerodha_connection"]["available"] = True
                health_status["zerodha_connection"]["authenticated"] = True
                health_status["zerodha_connection"]["can_fetch_data"] = True
                initialization_status["zerodha_connection_status"] = "connected"
                print("✅ Zerodha already authenticated")
            else:
                # Try to authenticate
                print("🔄 Attempting Zerodha authentication...")
                try:
                    kite = zerodha_auth.authenticate()
                    if zerodha_auth.is_authenticated():
                        health_status["zerodha_connection"]["available"] = True
                        health_status["zerodha_connection"]["authenticated"] = True
                        health_status["zerodha_connection"]["can_fetch_data"] = True
                        initialization_status["zerodha_connection_status"] = "connected"
                        initialization_status["auth_successful"] = True
                        print("✅ Zerodha authentication successful")
                    else:
                        health_status["zerodha_connection"]["error_message"] = "Authentication failed - returned False"
                        initialization_status["zerodha_connection_status"] = "authentication_failed"
                        print("❌ Zerodha authentication failed")
                except Exception as auth_error:
                    health_status["zerodha_connection"]["error_message"] = str(auth_error)
                    initialization_status["zerodha_connection_status"] = f"error: {str(auth_error)}"
                    print(f"❌ Zerodha authentication error: {auth_error}")
        except Exception as e:
            health_status["zerodha_connection"]["error_message"] = str(e)
            initialization_status["zerodha_connection_status"] = f"error: {str(e)}"
            print(f"❌ Zerodha connection test error: {e}")
    else:
        health_status["zerodha_connection"]["error_message"] = "ZerodhaAuth service not initialized"
        initialization_status["zerodha_connection_status"] = "service_not_available"
    
    # Update initialization status
    initialization_status["auth_successful"] = health_status["zerodha_connection"]["authenticated"]
    
    return health_status

@app.get("/api/test-auth")
async def test_auth():
    """Test Zerodha authentication separately with detailed feedback"""
    if not zerodha_auth:
        return {
            "success": False,
            "error": "ZerodhaAuth service not initialized",
            "details": "The Zerodha authentication service could not be created. Check your configuration.",
            "initialization_status": initialization_status
        }
    
    try:
        print("🔄 Testing Zerodha authentication...")
        
        # Check current status
        if zerodha_auth.is_authenticated():
            return {
                "success": True,
                "message": "Already authenticated with Zerodha",
                "profile_name": getattr(zerodha_auth, 'profile_name', 'Unknown'),
                "status": "authenticated"
            }
        
        # Try to authenticate
        print("🔐 Attempting new authentication...")
        kite = zerodha_auth.authenticate()
        
        if zerodha_auth.is_authenticated():
            return {
                "success": True,
                "message": "Zerodha authentication successful!",
                "profile_name": getattr(zerodha_auth, 'profile_name', 'Unknown'),
                "status": "newly_authenticated"
            }
        else:
            return {
                "success": False,
                "message": "Zerodha authentication failed",
                "error": "Authentication method returned False",
                "details": "The authentication process completed but did not result in a valid session.",
                "status": "authentication_failed"
            }
    except Exception as e:
        error_msg = f"Auth test error: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        return {
            "success": False,
            "message": "Authentication error occurred",
            "error": str(e),
            "details": "An exception occurred during the authentication process. Check your API credentials and network connection.",
            "traceback": traceback.format_exc() if app.debug else None,
            "status": "error"
        }

@app.get("/api/test-live-prices")
async def test_live_prices():
    """Test live price fetching with detailed debugging"""
    if not zerodha_auth:
        return {
            "success": False,
            "error": "ZerodhaAuth service not initialized"
        }
    
    try:
        print("🧪 Testing live price fetching...")
        
        # Check authentication first
        if not zerodha_auth.is_authenticated():
            print("🔄 Not authenticated, attempting authentication...")
            try:
                zerodha_auth.authenticate()
                if not zerodha_auth.is_authenticated():
                    return {
                        "success": False,
                        "error": "Zerodha authentication failed",
                        "details": "Cannot test live prices without authentication"
                    }
            except Exception as auth_error:
                return {
                    "success": False,
                    "error": f"Authentication failed: {str(auth_error)}"
                }
        
        kite = zerodha_auth.get_kite_instance()
        if not kite:
            return {
                "success": False,
                "error": "No kite instance available"
            }
        
        # Test with a few known symbols
        test_symbols = ["NSE:RELIANCE", "NSE:TCS", "NSE:INFY", "NSE:HDFCBANK", "NSE:ICICIBANK"]
        
        try:
            print(f"🔍 Testing quotes for: {test_symbols}")
            quote_response = kite.quote(test_symbols)
            
            formatted_prices = {}
            raw_sample = {}
            
            for symbol, data in quote_response.items():
                if isinstance(data, dict):
                    last_price = data.get('last_price', 0)
                    formatted_prices[symbol] = last_price
                    # Include some raw data for debugging
                    raw_sample[symbol] = {
                        'last_price': data.get('last_price'),
                        'timestamp': data.get('timestamp'),
                        'last_trade_time': data.get('last_trade_time'),
                        'ohlc': data.get('ohlc', {})
                    }
            
            return {
                "success": True,
                "message": "Live price test successful",
                "test_symbols": test_symbols,
                "prices_fetched": len(formatted_prices),
                "formatted_prices": formatted_prices,
                "raw_sample": raw_sample,
                "profile_name": getattr(zerodha_auth, 'profile_name', 'Unknown'),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as quote_error:
            return {
                "success": False,
                "error": f"Quote request failed: {str(quote_error)}",
                "test_symbols": test_symbols,
                "details": "The kite.quote() API call failed"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"Live price test error: {str(e)}",
            "traceback": traceback.format_exc()
        }

@app.get("/api/debug-csv-service")
async def debug_csv_service():
    """Debug CSV service and price fetching"""
    if not investment_service:
        return {
            "success": False,
            "error": "Investment service not available"
        }
    
    try:
        print("🔍 Debugging CSV service...")
        
        # Test CSV fetching
        csv_service = investment_service.csv_service
        csv_data = csv_service.fetch_csv_data()
        
        # Test a small batch of price fetching
        test_symbols = csv_data['symbols'][:5]  # Test first 5 symbols
        print(f"🧪 Testing price fetch for: {test_symbols}")
        
        prices = csv_service.get_live_prices(test_symbols)
        
        # Get connection status
        connection_status = csv_service.get_connection_status()
        
        return {
            "success": True,
            "csv_data": {
                "total_symbols": len(csv_data['symbols']),
                "sample_symbols": csv_data['symbols'][:10],
                "fetch_time": csv_data['fetch_time'],
                "csv_hash": csv_data['csv_hash']
            },
            "price_test": {
                "test_symbols": test_symbols,
                "prices": prices,
                "price_count": len(prices)
            },
            "connection_status": connection_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }

# Legacy portfolio endpoint for compatibility
@app.get("/api/portfolio/summary/{user_id}")
async def get_portfolio_summary(user_id: int):
    """Get portfolio summary - redirects to investment service"""
    
    print(f"🔍 PORTFOLIO SUMMARY CALLED for user {user_id}")
    
    # Check if services are available
    if not zerodha_auth:
        print("❌ ZerodhaAuth not available")
        return {
            "error": "Zerodha authentication service not available",
            "connected": False,
            "message": "Please check your Zerodha API configuration and restart the service",
            "data": None
        }
    
    if not portfolio_service:
        print("❌ Portfolio service not available")
        return {
            "error": "Portfolio service not available",
            "connected": False,
            "message": "Portfolio service could not be initialized",
            "data": None
        }
    
    try:
        # Check authentication status first
        if not zerodha_auth.is_authenticated():
            print("🔄 Attempting Zerodha authentication...")
            try:
                kite = zerodha_auth.authenticate()
                if not zerodha_auth.is_authenticated():
                    print("❌ Authentication failed")
                    return {
                        "error": "Zerodha authentication failed",
                        "connected": False,
                        "message": "Unable to authenticate with Zerodha. Please check your API credentials.",
                        "data": None
                    }
            except Exception as auth_error:
                print(f"❌ Authentication error: {auth_error}")
                return {
                    "error": f"Authentication error: {str(auth_error)}",
                    "connected": False,
                    "message": "Failed to connect to Zerodha. Please check your internet connection and API credentials.",
                    "data": None
                }
        
        print(f"✅ Authentication status: {zerodha_auth.is_authenticated()}")
        
        # Try to get real portfolio data
        print("📊 Fetching real portfolio data...")
        portfolio_data = portfolio_service.get_portfolio_data()
        
        if portfolio_data:
            print(f"📊 SUCCESS! Returning real portfolio data with {len(portfolio_data.get('holdings', []))} holdings")
            print(f"📊 Total value: ₹{portfolio_data.get('current_value', 0):,.2f}")
            return portfolio_data
        else:
            print("❌ Portfolio service returned None")
            return {
                "error": "No portfolio data available",
                "connected": True,
                "message": "Connected to Zerodha but no portfolio data found. This could mean:\n1. No holdings in your account\n2. Market is closed\n3. Data fetch failed",
                "data": None
            }
        
    except Exception as e:
        error_msg = f"Portfolio error: {str(e)}\n{traceback.format_exc()}"
        print(f"❌ {error_msg}")
        return {
            "error": str(e),
            "connected": False,
            "message": "An error occurred while fetching portfolio data",
            "data": None
        }

@app.get("/api/connection-status")
async def get_connection_status():
    """Get comprehensive connection status"""
    status = {
        "timestamp": datetime.now().isoformat(),
        "services": {
            "zerodha_auth": {
                "available": bool(zerodha_auth),
                "authenticated": False,
                "profile_name": None,
                "error": None
            },
            "portfolio_service": {
                "available": bool(portfolio_service),
                "can_fetch_data": False
            },
            "investment_service": {
                "available": bool(investment_service)
            }
        },
        "overall_status": "disconnected"
    }
    
    # Test Zerodha connection
    if zerodha_auth:
        try:
            if zerodha_auth.is_authenticated():
                status["services"]["zerodha_auth"]["authenticated"] = True
                status["services"]["zerodha_auth"]["profile_name"] = getattr(zerodha_auth, 'profile_name', None)
                status["services"]["portfolio_service"]["can_fetch_data"] = True
                status["overall_status"] = "connected"
            else:
                status["services"]["zerodha_auth"]["error"] = "Not authenticated"
        except Exception as e:
            status["services"]["zerodha_auth"]["error"] = str(e)
    else:
        status["services"]["zerodha_auth"]["error"] = "Service not available"
    
    return status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)