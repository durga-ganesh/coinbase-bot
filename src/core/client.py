"""
Coinbase API Client Wrapper
Handles authentication and API interactions with Coinbase Advanced Trade API
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import pandas as pd

from coinbase.rest import RESTClient
from src.utils.config import Config
from src.utils.exceptions import TradingError, APIError
from src.utils.logger import get_logger

logger = get_logger(__name__)


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
        
    def _initialize_client(self):
        """Initialize the Coinbase REST client"""
        try:
            api_key = os.getenv('COINBASE_API_KEY')
            api_secret = os.getenv('COINBASE_API_SECRET')
            passphrase = os.getenv('COINBASE_PASSPHRASE')
            sandbox = os.getenv('COINBASE_SANDBOX', 'true').lower() == 'true'
            
            if not all([api_key, api_secret, passphrase]):
                raise TradingError("Missing required Coinbase API credentials")
                
            self._client = RESTClient(
                api_key=api_key,
                api_secret=api_secret,
                passphrase=passphrase,
                sandbox=sandbox
            )
            
            logger.info(f"Coinbase client initialized (sandbox: {sandbox})")
            
        except Exception as e:
            logger.error(f"Failed to initialize Coinbase client: {e}")
            raise TradingError(f"Client initialization failed: {e}")
    
    def get_accounts(self) -> List[Dict]:
        """Get all account balances"""
        try:
            response = self._client.get_accounts()
            accounts = response.get('accounts', [])
            
            logger.info(f"Retrieved {len(accounts)} accounts")
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to get accounts: {e}")
            raise APIError(f"Failed to get accounts: {e}")
    
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
            logger.error(f"Failed to get balance for {currency}: {e}")
            raise APIError(f"Failed to get balance: {e}")
    
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
            logger.debug(f"Retrieved product info for {product_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get product info for {product_id}: {e}")
            raise APIError(f"Failed to get product info: {e}")
    
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
            price = response.get('price', '0')
            return float(price)
            
        except Exception as e:
            logger.error(f"Failed to get price for {product_id}: {e}")
            raise APIError(f"Failed to get price: {e}")
    
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
                logger.warning(f"No market data found for {product_id}")
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
            
            logger.info(f"Retrieved {len(df)} candles for {product_id}")
            return df
            
        except Exception as e:
            logger.error(f"Failed to get market data for {product_id}: {e}")
            raise APIError(f"Failed to get market data: {e}")
    
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
            
            logger.info(f"Placed market buy order: {product_id}, ${funds}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to place buy order: {e}")
            raise APIError(f"Failed to place buy order: {e}")
    
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
            
            logger.info(f"Placed market sell order: {product_id}, {size}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to place sell order: {e}")
            raise APIError(f"Failed to place sell order: {e}")
    
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
            orders = response.get('orders', [])
            
            logger.info(f"Retrieved {len(orders)} orders")
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get orders: {e}")
            raise APIError(f"Failed to get orders: {e}")
    
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
            logger.info(f"Cancelled order: {order_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            raise APIError(f"Failed to cancel order: {e}")
    
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
            fills = response.get('fills', [])
            
            logger.info(f"Retrieved {len(fills)} fills")
            return fills
            
        except Exception as e:
            logger.error(f"Failed to get fills: {e}")
            raise APIError(f"Failed to get fills: {e}")
    
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
            logger.error(f"Health check failed: {e}")
            return False
