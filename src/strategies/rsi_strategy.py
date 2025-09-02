"""
RSI (Relative Strength Index) Strategy

This strategy generates:
- BUY signal when RSI is oversold (< oversold_threshold)
- SELL signal when RSI is overbought (> overbought_threshold) 
- HOLD signal otherwise
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from src.strategies.base import BaseStrategy, TradingSignal, Signal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class RSIStrategy(BaseStrategy):
    """RSI-based trading strategy"""
    
    def __init__(self, rsi_period: int = 14, oversold_threshold: float = 30, 
                 overbought_threshold: float = 70, **params):
        """
        Initialize RSI strategy
        
        Args:
            rsi_period: Period for RSI calculation
            oversold_threshold: RSI level for oversold condition
            overbought_threshold: RSI level for overbought condition
            **params: Additional strategy parameters
        """
        super().__init__(
            name="RSI_Strategy",
            rsi_period=rsi_period,
            oversold_threshold=oversold_threshold,
            overbought_threshold=overbought_threshold,
            **params
        )
        
        if oversold_threshold >= overbought_threshold:
            raise ValueError("Oversold threshold must be less than overbought threshold")
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """
        Calculate Relative Strength Index
        
        Args:
            prices: Price series (typically close prices)
            period: RSI calculation period
            
        Returns:
            RSI values as pandas Series
        """
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def generate_signal(self, market_data: pd.DataFrame) -> TradingSignal:
        """
        Generate trading signal based on RSI
        
        Args:
            market_data: DataFrame with OHLCV data
            
        Returns:
            TradingSignal object
        """
        if not self.validate_data(market_data):
            return TradingSignal(Signal.HOLD, 0.0)
        
        try:
            rsi_period = self.params['rsi_period']
            oversold_threshold = self.params['oversold_threshold']
            overbought_threshold = self.params['overbought_threshold']
            
            # Calculate RSI
            data = market_data.copy()
            data['RSI'] = self.calculate_rsi(data['close'], rsi_period)
            
            if data['RSI'].isna().all():
                return TradingSignal(Signal.HOLD, 0.0)
            
            current_rsi = data['RSI'].iloc[-1]
            current_price = data['close'].iloc[-1]
            
            signal = Signal.HOLD
            confidence = 0.0
            
            # RSI-based signals
            if current_rsi < oversold_threshold:
                signal = Signal.BUY
                # Higher confidence the more oversold
                oversold_strength = (oversold_threshold - current_rsi) / oversold_threshold
                confidence = min(0.9, max(0.3, oversold_strength))
                
                logger.info(f"RSI Strategy: BUY signal - RSI: {current_rsi:.2f}")
                
            elif current_rsi > overbought_threshold:
                signal = Signal.SELL
                # Higher confidence the more overbought
                overbought_strength = (current_rsi - overbought_threshold) / (100 - overbought_threshold)
                confidence = min(0.9, max(0.3, overbought_strength))
                
                logger.info(f"RSI Strategy: SELL signal - RSI: {current_rsi:.2f}")
            
            # Add trend confirmation
            if len(data) >= 5:
                recent_rsi = data['RSI'].iloc[-5:].mean()
                rsi_trend = (current_rsi - recent_rsi) / recent_rsi if recent_rsi != 0 else 0
                
                # Increase confidence if RSI is trending in signal direction
                if signal == Signal.BUY and rsi_trend > 0:
                    confidence *= 1.1
                elif signal == Signal.SELL and rsi_trend < 0:
                    confidence *= 1.1
                else:
                    confidence *= 0.9
                
                confidence = min(1.0, confidence)
            
            # Volume confirmation
            if 'volume' in data.columns and len(data) >= 10:
                recent_volume = data['volume'].iloc[-3:].mean()
                avg_volume = data['volume'].iloc[-10:].mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                # Adjust confidence based on volume
                if volume_ratio > 1.2:
                    confidence *= 1.1
                elif volume_ratio < 0.8:
                    confidence *= 0.9
                
                confidence = min(1.0, confidence)
            
            metadata = {
                'rsi': current_rsi,
                'oversold_threshold': oversold_threshold,
                'overbought_threshold': overbought_threshold,
                'rsi_divergence': self._check_divergence(data) if len(data) >= 20 else False
            }
            
            return TradingSignal(
                signal=signal,
                confidence=confidence,
                price=current_price,
                timestamp=data.index[-1] if hasattr(data.index[-1], 'isoformat') else None,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error generating RSI signal: {e}")
            return TradingSignal(Signal.HOLD, 0.0)
    
    def _check_divergence(self, data: pd.DataFrame) -> bool:
        """
        Check for RSI-price divergence
        
        Args:
            data: Market data with RSI
            
        Returns:
            True if divergence detected
        """
        try:
            # Simple divergence check - price making new highs/lows but RSI not confirming
            recent_data = data.iloc[-10:]
            
            price_max_idx = recent_data['close'].idxmax()
            price_min_idx = recent_data['close'].idxmin()
            rsi_max_idx = recent_data['RSI'].idxmax()
            rsi_min_idx = recent_data['RSI'].idxmin()
            
            # Bearish divergence: price higher high, RSI lower high
            bearish_div = (price_max_idx > rsi_max_idx and 
                          recent_data.loc[price_max_idx, 'close'] > recent_data.loc[rsi_max_idx, 'close'])
            
            # Bullish divergence: price lower low, RSI higher low
            bullish_div = (price_min_idx < rsi_min_idx and 
                          recent_data.loc[price_min_idx, 'close'] < recent_data.loc[rsi_min_idx, 'close'])
            
            return bearish_div or bullish_div
            
        except Exception:
            return False
    
    def get_required_history(self) -> int:
        """
        Get minimum number of data points required
        
        Returns:
            Minimum number of historical data points
        """
        return self.params['rsi_period'] * 2 + 5  # RSI needs warm-up period
    
    def _setup_indicators(self, market_data: pd.DataFrame) -> None:
        """
        Setup indicators
        
        Args:
            market_data: Historical market data
        """
        logger.info(f"RSI strategy setup with period {self.params['rsi_period']}, "
                   f"thresholds: {self.params['oversold_threshold']}-{self.params['overbought_threshold']}")
    
    def get_strategy_description(self) -> str:
        """
        Get human-readable strategy description
        
        Returns:
            Strategy description
        """
        return (f"RSI Strategy using {self.params['rsi_period']}-period RSI. "
                f"BUY when RSI < {self.params['oversold_threshold']}, "
                f"SELL when RSI > {self.params['overbought_threshold']}")
    
    def get_current_indicators(self, market_data: pd.DataFrame) -> Dict[str, float]:
        """
        Get current indicator values for display
        
        Args:
            market_data: Market data
            
        Returns:
            Dictionary of current indicator values
        """
        if not self.validate_data(market_data):
            return {}
        
        rsi_period = self.params['rsi_period']
        rsi = self.calculate_rsi(market_data['close'], rsi_period)
        
        return {
            f'RSI_{rsi_period}': rsi.iloc[-1] if not rsi.isna().all() else 0,
            'oversold_threshold': self.params['oversold_threshold'],
            'overbought_threshold': self.params['overbought_threshold'],
            'current_price': market_data['close'].iloc[-1]
        }
