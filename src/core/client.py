"""
Coinbase API Client Wrapper
Handles authentication and API interactions with Coinbase Advanced Trade API

Logging Categories:
- [OPER ]: High-level operations (what the bot is doing)
- [API  ]: Direct API calls to Coinbase (starting, completion, failures)  
- [BOT  ]: Bot processing and initialization
- [AUTH ]: Authentication and credential loading
- [CONF ]: Configuration loading and management
- [ENV  ]: Environment variable handling
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps
import threading
import pandas as pd

from coinbase.rest import RESTClient
from src.utils.config import Config
from src.utils.exceptions import TradingError, APIError
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Thread-local storage for tracking API call depth
_api_call_depth = threading.local()


def log_api_interaction(func):
    """Decorator to log API interactions with detailed information"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        method_name = func.__name__
        start_time = datetime.now()
        
        # Track API call depth to avoid blank lines in nested calls
        if not hasattr(_api_call_depth, 'value'):
            _api_call_depth.value = 0
        
        is_top_level = _api_call_depth.value == 0
        _api_call_depth.value += 1
        
        # Format arguments for logging
        args_str = ', '.join([f"'{arg}'" if isinstance(arg, str) else str(arg) for arg in args])
        kwargs_str = ', '.join([f"{k}={v}" for k, v in kwargs.items()])
        params = f"({args_str}" + (f", {kwargs_str}" if kwargs_str else "") + ")"
        
        # Log the API call start
        logger.info(f"[API  ] Starting {method_name}{params}")
        
        try:
            result = func(self, *args, **kwargs)
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Log successful API call
            result_summary = self._summarize_result(result)
            logger.info(f"[API  ] Completed {method_name} in {duration:.3f}s - {result_summary}")
            
            # Only add blank line for top-level API calls
            if is_top_level:
                with open(os.getenv('LOG_FILE', 'logs/bot.log'), 'a') as f:
                    f.write('\n')
            
            _api_call_depth.value -= 1
            return result
            
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Log failed API call
            logger.error(f"[API  ] Failed {method_name} after {duration:.3f}s - Error: {str(e)}")
            
            # Only add blank line for top-level API calls
            if is_top_level:
                with open(os.getenv('LOG_FILE', 'logs/bot.log'), 'a') as f:
                    f.write('\n')
                    
            _api_call_depth.value -= 1
            raise
            
    return wrapper


class CoinbaseClient:
    """Wrapper for Coinbase Advanced Trade API client"""
    
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize Coinbase client
        
        Args:
            config: Configuration object, if None will load from environment
        """
        self.config = config or Config()
        self._client = None
        self._initialize_client()
    
    def _summarize_result(self, result) -> str:
        """Create a summary of API result for logging"""
        if isinstance(result, list):
            return f"Returned {len(result)} items"
        elif isinstance(result, dict):
            if 'accounts' in result:
                return f"Returned {len(result['accounts'])} accounts"
            elif 'orders' in result:
                return f"Returned {len(result['orders'])} orders"
            elif 'fills' in result:
                return f"Returned {len(result['fills'])} fills"
            elif 'candles' in result:
                return f"Returned {len(result['candles'])} candles"
            elif 'order_id' in result:
                return f"Order created with ID: {result.get('order_id', 'unknown')}"
            elif 'price' in result:
                return f"Current price: {result['price']}"
            else:
                return f"Returned dict with {len(result)} keys"
        elif isinstance(result, pd.DataFrame):
            return f"DataFrame with {len(result)} rows"
        elif isinstance(result, (int, float)):
            return f"Value: {result}"
        elif isinstance(result, bool):
            return f"Status: {result}"
        else:
            return f"Type: {type(result).__name__}"
        
    def _initialize_client(self):
        """Initialize the Coinbase REST client"""
        try:
            # Load credentials from JSON file only
            api_key_file = os.getenv('COINBASE_API_KEY_FILE')
            
            if not api_key_file:
                raise TradingError("COINBASE_API_KEY_FILE environment variable is required")
            
            # Load credentials from JSON file
            api_key, private_key = self._load_credentials_from_json(api_key_file)
            sandbox = os.getenv('COINBASE_SANDBOX', 'true').lower() == 'true'
            
            # For Coinbase Advanced Trade API with JSON credentials
            self._client = RESTClient(
                api_key=api_key,
                api_secret=private_key
            )
            
            logger.info(f"[BOT  ] Coinbase client initialized (sandbox: {sandbox})")
            
        except Exception as e:
            logger.error(f"[BOT  ] Failed to initialize Coinbase client: {e}")
            raise TradingError(f"Client initialization failed: {e}")
    
    def _load_credentials_from_json(self, json_file_path: str) -> tuple:
        """
        Load API credentials from JSON key file
        
        Args:
            json_file_path: Path to the JSON key file
            
        Returns:
            tuple: (api_key, private_key)
        """
        try:
            # Handle relative path
            if not os.path.isabs(json_file_path):
                # Look for file relative to project root
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                json_file_path = os.path.join(project_root, json_file_path)
            
            if not os.path.exists(json_file_path):
                raise TradingError(f"API key file not found: {json_file_path}")
            
            with open(json_file_path, 'r') as f:
                credentials = json.load(f)
            
            # Extract API key from the name field
            # Format: "organizations/{org_id}/apiKeys/{api_key_id}"
            api_key_name = credentials.get('name', '')
            if '/apiKeys/' in api_key_name:
                api_key = api_key_name.split('/apiKeys/')[-1]
            else:
                raise TradingError("Invalid JSON key file format: missing API key in name field")
            
            private_key = credentials.get('privateKey', '')
            if not private_key:
                raise TradingError("Invalid JSON key file format: missing privateKey field")
            
            logger.info(f"[AUTH ] Loaded credentials from JSON file: {json_file_path}")
            return api_key, private_key
            
        except json.JSONDecodeError as e:
            raise TradingError(f"Invalid JSON file format: {e}")
        except Exception as e:
            raise TradingError(f"Failed to load credentials from JSON file: {e}")
    
    @log_api_interaction
    def get_accounts(self) -> List[Dict]:
        """Get all account balances"""
        try:
            response = self._client.get_accounts()
            
            # Handle different response formats
            if hasattr(response, 'accounts'):
                accounts = response.accounts
            elif hasattr(response, 'get') and callable(response.get):
                accounts = response.get('accounts', [])
            elif isinstance(response, dict):
                accounts = response.get('accounts', [])
            else:
                # Convert response to dict if it's an object
                accounts = getattr(response, 'accounts', [])
            
            # Convert to list of dicts if needed
            if accounts and not isinstance(accounts[0], dict):
                accounts = [account.__dict__ if hasattr(account, '__dict__') else account for account in accounts]
            
            return accounts
            
        except Exception as e:
            raise APIError(f"Failed to get accounts: {e}")
    
    @log_api_interaction
    def get_account_balance(self, currency: str = 'USD') -> float:
        """
        Get balance for specific currency
        
        Args:
            currency: Currency symbol (e.g., 'USD', 'BTC')
            
        Returns:
            Available balance as float
        """
        try:
            accounts = self.get_accounts()
            
            for account in accounts:
                if account.get('currency') == currency:
                    available_balance = account.get('available_balance', {})
                    return float(available_balance.get('value', 0))
            
            return 0.0
            
        except Exception as e:
            raise APIError(f"Failed to get balance: {e}")
    
    @log_api_interaction
    def get_product_info(self, product_id: str) -> Dict:
        """
        Get product information
        
        Args:
            product_id: Product identifier (e.g., 'BTC-USD')
            
        Returns:
            Product information dictionary
        """
        try:
            response = self._client.get_product(product_id=product_id)
            
            # Convert response to dictionary if needed
            if hasattr(response, '__dict__'):
                return response.__dict__
            elif isinstance(response, dict):
                return response
            else:
                # Try to extract common attributes
                product_info = {}
                for attr in ['product_id', 'price', 'volume_24h', 'price_change_24h']:
                    if hasattr(response, attr):
                        product_info[attr] = getattr(response, attr)
                return product_info
            
        except Exception as e:
            raise APIError(f"Failed to get product info: {e}")
    
    @log_api_interaction
    def get_current_price(self, product_id: str) -> float:
        """
        Get current market price for a product
        
        Args:
            product_id: Product identifier (e.g., 'BTC-USD')
            
        Returns:
            Current price as float
        """
        try:
            response = self._client.get_product(product_id=product_id)
            
            # Handle different response formats
            if hasattr(response, 'price'):
                price = response.price
            elif hasattr(response, 'get') and callable(response.get):
                price = response.get('price', '0')
            elif isinstance(response, dict):
                price = response.get('price', '0')
            else:
                # Convert response to dict if it's an object
                price = getattr(response, 'price', '0')
            
            return float(price)
            
        except Exception as e:
            raise APIError(f"Failed to get price: {e}")
    
    @log_api_interaction
    def get_market_data(self, product_id: str, granularity: str = '300', 
                       start: Optional[str] = None, end: Optional[str] = None) -> pd.DataFrame:
        """
        Get historical market data (candles)
        
        Args:
            product_id: Product identifier (e.g., 'BTC-USD')
            granularity: Candle granularity in seconds (60, 300, 900, 3600, 21600, 86400)
            start: Start time (ISO format)
            end: End time (ISO format)
            
        Returns:
            DataFrame with OHLCV data
        """
        try:
            params = {
                'granularity': granularity
            }
            
            if start:
                params['start'] = start
            if end:
                params['end'] = end
                
            response = self._client.get_candles(product_id=product_id, **params)
            candles = response.get('candles', [])
            
            if not candles:
                logger.warn(f"[API  ] No market data found for {product_id}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=['timestamp', 'low', 'high', 'open', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.astype({
                'low': float,
                'high': float,
                'open': float,
                'close': float,
                'volume': float
            })
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            raise APIError(f"Failed to get market data: {e}")
    
    @log_api_interaction
    def place_market_buy_order(self, product_id: str, funds: float) -> Dict:
        """
        Place a market buy order
        
        Args:
            product_id: Product identifier (e.g., 'BTC-USD')
            funds: Amount in quote currency (USD)
            
        Returns:
            Order response dictionary
        """
        try:
            order_config = {
                'market_market_ioc': {
                    'quote_size': str(funds)
                }
            }
            
            response = self._client.create_order(
                client_order_id=f"buy-{datetime.now().isoformat()}",
                product_id=product_id,
                side='BUY',
                order_configuration=order_config
            )
            
            return response
            
        except Exception as e:
            raise APIError(f"Failed to place buy order: {e}")
    
    @log_api_interaction
    def place_market_sell_order(self, product_id: str, size: float) -> Dict:
        """
        Place a market sell order
        
        Args:
            product_id: Product identifier (e.g., 'BTC-USD')
            size: Amount in base currency
            
        Returns:
            Order response dictionary
        """
        try:
            order_config = {
                'market_market_ioc': {
                    'base_size': str(size)
                }
            }
            
            response = self._client.create_order(
                client_order_id=f"sell-{datetime.now().isoformat()}",
                product_id=product_id,
                side='SELL',
                order_configuration=order_config
            )
            
            return response
            
        except Exception as e:
            raise APIError(f"Failed to place sell order: {e}")
    
    @log_api_interaction
    def get_orders(self, product_id: Optional[str] = None) -> List[Dict]:
        """
        Get order history
        
        Args:
            product_id: Optional product filter
            
        Returns:
            List of order dictionaries
        """
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
                
            response = self._client.list_orders(**params)
            
            # Handle different response formats
            if hasattr(response, 'orders'):
                orders = response.orders
            elif hasattr(response, 'get') and callable(response.get):
                orders = response.get('orders', [])
            elif isinstance(response, dict):
                orders = response.get('orders', [])
            else:
                # Convert response to list if it's an object
                orders = getattr(response, 'orders', [])
            
            # Convert to list of dicts if needed
            if orders and not isinstance(orders[0], dict):
                orders = [order.__dict__ if hasattr(order, '__dict__') else order for order in orders]
            
            return orders
            
        except Exception as e:
            raise APIError(f"Failed to get orders: {e}")
    
    @log_api_interaction
    def cancel_order(self, order_id: str) -> Dict:
        """
        Cancel an order
        
        Args:
            order_id: Order identifier
            
        Returns:
            Cancellation response
        """
        try:
            response = self._client.cancel_orders([order_id])
            return response
            
        except Exception as e:
            raise APIError(f"Failed to cancel order: {e}")
    
    @log_api_interaction
    def get_fills(self, product_id: Optional[str] = None) -> List[Dict]:
        """
        Get fill history (completed trades)
        
        Args:
            product_id: Optional product filter
            
        Returns:
            List of fill dictionaries
        """
        try:
            params = {}
            if product_id:
                params['product_id'] = product_id
                
            response = self._client.get_fills(**params)
            
            # Handle different response formats
            if hasattr(response, 'fills'):
                fills = response.fills
            elif hasattr(response, 'get') and callable(response.get):
                fills = response.get('fills', [])
            elif isinstance(response, dict):
                fills = response.get('fills', [])
            else:
                # Convert response to list if it's an object
                fills = getattr(response, 'fills', [])
            
            # Convert to list of dicts if needed
            if fills and not isinstance(fills[0], dict):
                fills = [fill.__dict__ if hasattr(fill, '__dict__') else fill for fill in fills]
            
            return fills
            
        except Exception as e:
            raise APIError(f"Failed to get fills: {e}")
    
    @log_api_interaction
    def health_check(self) -> bool:
        """
        Check if the API connection is healthy
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            self.get_accounts()
            return True
        except Exception as e:
            return False
