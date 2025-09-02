"""
Simple Moving Average (SMA) Crossover Strategy

This strategy generates:
- BUY signal when short MA crosses above long MA
- SELL signal when short MA crosses below long MA
- HOLD signal otherwise
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from src.strategies.base import BaseStrategy, TradingSignal, Signal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class SMACrossoverStrategy(BaseStrategy):
    """Simple Moving Average Crossover Strategy"""
    
    def __init__(self, short_window: int = 10, long_window: int = 30, **params):
        """
        Initialize SMA Crossover strategy
        
        Args:
            short_window: Period for short-term moving average
            long_window: Period for long-term moving average
            **params: Additional strategy parameters
        """
        super().__init__(
            name="SMA_Crossover",
            short_window=short_window,
            long_window=long_window,
            **params
        )
        
        if short_window >= long_window:
            raise ValueError("Short window must be less than long window")
    
    def generate_signal(self, market_data: pd.DataFrame) -> TradingSignal:
        """
        Generate trading signal based on SMA crossover
        
        Args:
            market_data: DataFrame with OHLCV data
            
        Returns:
            TradingSignal object
        """
        if not self.validate_data(market_data):
            return TradingSignal(Signal.HOLD, 0.0)
        
        try:
            # Calculate moving averages
            short_window = self.params['short_window']
            long_window = self.params['long_window']
            
            data = market_data.copy()
            data['SMA_short'] = data['close'].rolling(window=short_window).mean()
            data['SMA_long'] = data['close'].rolling(window=long_window).mean()
            
            # Get the last few values to determine crossover
            if len(data) < long_window + 1:
                return TradingSignal(Signal.HOLD, 0.0)
            
            current_short = data['SMA_short'].iloc[-1]
            current_long = data['SMA_long'].iloc[-1]
            prev_short = data['SMA_short'].iloc[-2]
            prev_long = data['SMA_long'].iloc[-2]
            
            current_price = data['close'].iloc[-1]
            
            # Check for crossover
            signal = Signal.HOLD
            confidence = 0.0
            
            # Bullish crossover: short MA crosses above long MA
            if prev_short <= prev_long and current_short > current_long:
                signal = Signal.BUY
                # Confidence based on the magnitude of the crossover
                crossover_strength = abs(current_short - current_long) / current_long
                confidence = min(0.8, max(0.3, crossover_strength * 10))
                
                logger.info(f"SMA Crossover: BUY signal - Short: {current_short:.2f}, Long: {current_long:.2f}")
                
            # Bearish crossover: short MA crosses below long MA
            elif prev_short >= prev_long and current_short < current_long:
                signal = Signal.SELL
                crossover_strength = abs(current_short - current_long) / current_long
                confidence = min(0.8, max(0.3, crossover_strength * 10))
                
                logger.info(f"SMA Crossover: SELL signal - Short: {current_short:.2f}, Long: {current_long:.2f}")
            
            # Add volume confirmation if available
            if 'volume' in data.columns:
                recent_volume = data['volume'].iloc[-5:].mean()
                avg_volume = data['volume'].mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                # Increase confidence if volume is above average
                if volume_ratio > 1.2:
                    confidence *= 1.2
                elif volume_ratio < 0.8:
                    confidence *= 0.8
                
                confidence = min(1.0, confidence)
            
            metadata = {
                'short_ma': current_short,
                'long_ma': current_long,
                'crossover_strength': abs(current_short - current_long) / current_long,
                'trend_strength': (current_short - current_long) / current_long
            }
            
            return TradingSignal(
                signal=signal,
                confidence=confidence,
                price=current_price,
                timestamp=data.index[-1] if hasattr(data.index[-1], 'isoformat') else None,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error generating SMA crossover signal: {e}")
            return TradingSignal(Signal.HOLD, 0.0)
    
    def get_required_history(self) -> int:
        """
        Get minimum number of data points required
        
        Returns:
            Minimum number of historical data points
        """
        return self.params['long_window'] + 5  # Extra buffer for calculations
    
    def _setup_indicators(self, market_data: pd.DataFrame) -> None:
        """
        Setup indicators (pre-calculate if needed)
        
        Args:
            market_data: Historical market data
        """
        # For SMA crossover, no pre-setup needed
        logger.info(f"SMA Crossover strategy setup complete with windows: "
                   f"{self.params['short_window']}, {self.params['long_window']}")
    
    def get_strategy_description(self) -> str:
        """
        Get human-readable strategy description
        
        Returns:
            Strategy description
        """
        return (f"SMA Crossover Strategy using {self.params['short_window']}-period and "
                f"{self.params['long_window']}-period moving averages. "
                f"Generates BUY signals on bullish crossovers and SELL signals on bearish crossovers.")
    
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
        
        short_window = self.params['short_window']
        long_window = self.params['long_window']
        
        short_ma = market_data['close'].rolling(window=short_window).mean().iloc[-1]
        long_ma = market_data['close'].rolling(window=long_window).mean().iloc[-1]
        
        return {
            f'SMA_{short_window}': short_ma,
            f'SMA_{long_window}': long_ma,
            'trend_strength': (short_ma - long_ma) / long_ma,
            'current_price': market_data['close'].iloc[-1]
        }
