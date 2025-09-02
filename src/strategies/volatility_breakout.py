"""
Volatility Breakout Strategy

This strategy generates:
- BUY signal when price breaks above upper volatility band
- SELL signal when price breaks below lower volatility band  
- HOLD signal otherwise
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from src.strategies.base import BaseStrategy, TradingSignal, Signal
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VolatilityBreakoutStrategy(BaseStrategy):
    """Volatility breakout trading strategy"""
    
    def __init__(self, lookback_period: int = 20, volatility_multiplier: float = 2.0, 
                 min_volume: int = 100000, **params):
        """
        Initialize volatility breakout strategy
        
        Args:
            lookback_period: Period for volatility calculation
            volatility_multiplier: Multiplier for volatility bands
            min_volume: Minimum volume threshold
            **params: Additional strategy parameters
        """
        super().__init__(
            name="Volatility_Breakout",
            lookback_period=lookback_period,
            volatility_multiplier=volatility_multiplier,
            min_volume=min_volume,
            **params
        )
    
    def calculate_volatility_bands(self, prices: pd.Series, period: int, multiplier: float):
        """
        Calculate volatility-based trading bands
        
        Args:
            prices: Price series
            period: Lookback period
            multiplier: Volatility multiplier
            
        Returns:
            Tuple of (upper_band, lower_band, middle, volatility)
        """
        rolling_mean = prices.rolling(window=period).mean()
        rolling_std = prices.rolling(window=period).std()
        
        upper_band = rolling_mean + (rolling_std * multiplier)
        lower_band = rolling_mean - (rolling_std * multiplier)
        
        return upper_band, lower_band, rolling_mean, rolling_std
    
    def generate_signal(self, market_data: pd.DataFrame) -> TradingSignal:
        """
        Generate trading signal based on volatility breakout
        
        Args:
            market_data: DataFrame with OHLCV data
            
        Returns:
            TradingSignal object
        """
        if not self.validate_data(market_data):
            return TradingSignal(Signal.HOLD, 0.0)
        
        try:
            lookback_period = self.params['lookback_period']
            volatility_multiplier = self.params['volatility_multiplier']
            min_volume = self.params['min_volume']
            
            data = market_data.copy()
            
            # Calculate volatility bands
            upper_band, lower_band, middle, volatility = self.calculate_volatility_bands(
                data['close'], lookback_period, volatility_multiplier
            )
            
            data['upper_band'] = upper_band
            data['lower_band'] = lower_band
            data['middle_band'] = middle
            data['volatility'] = volatility
            
            if data['upper_band'].isna().iloc[-1] or data['lower_band'].isna().iloc[-1]:
                return TradingSignal(Signal.HOLD, 0.0)
            
            current_price = data['close'].iloc[-1]
            current_upper = data['upper_band'].iloc[-1]
            current_lower = data['lower_band'].iloc[-1]
            current_middle = data['middle_band'].iloc[-1]
            current_volume = data['volume'].iloc[-1] if 'volume' in data.columns else min_volume
            
            signal = Signal.HOLD
            confidence = 0.0
            
            # Check for breakout conditions
            if current_price > current_upper and current_volume >= min_volume:
                signal = Signal.BUY
                # Confidence based on breakout strength and volume
                breakout_strength = (current_price - current_upper) / current_upper
                volume_strength = min(2.0, current_volume / min_volume)
                confidence = min(0.9, max(0.3, breakout_strength * 5 * volume_strength))
                
                logger.info(f"Volatility Breakout: BUY signal - Price: {current_price:.2f}, "
                           f"Upper Band: {current_upper:.2f}")
                
            elif current_price < current_lower and current_volume >= min_volume:
                signal = Signal.SELL
                # Confidence based on breakdown strength and volume
                breakdown_strength = (current_lower - current_price) / current_lower
                volume_strength = min(2.0, current_volume / min_volume)
                confidence = min(0.9, max(0.3, breakdown_strength * 5 * volume_strength))
                
                logger.info(f"Volatility Breakout: SELL signal - Price: {current_price:.2f}, "
                           f"Lower Band: {current_lower:.2f}")
            
            # Add trend confirmation
            if signal != Signal.HOLD and len(data) >= 5:
                recent_prices = data['close'].iloc[-5:]
                price_trend = (recent_prices.iloc[-1] - recent_prices.iloc[0]) / recent_prices.iloc[0]
                
                # Increase confidence if breakout aligns with recent trend
                if (signal == Signal.BUY and price_trend > 0) or (signal == Signal.SELL and price_trend < 0):
                    confidence *= 1.2
                else:
                    confidence *= 0.8
                
                confidence = min(1.0, confidence)
            
            # Check for volatility expansion
            if len(data) >= lookback_period * 2:
                recent_vol = data['volatility'].iloc[-5:].mean()
                avg_vol = data['volatility'].iloc[-lookback_period*2:].mean()
                vol_expansion = recent_vol / avg_vol if avg_vol > 0 else 1
                
                # Prefer signals during volatility expansion
                if vol_expansion > 1.2:
                    confidence *= 1.1
                elif vol_expansion < 0.8:
                    confidence *= 0.9
                
                confidence = min(1.0, confidence)
            
            metadata = {
                'upper_band': current_upper,
                'lower_band': current_lower,
                'middle_band': current_middle,
                'volatility': data['volatility'].iloc[-1],
                'breakout_strength': abs(current_price - current_middle) / current_middle,
                'volume': current_volume,
                'min_volume': min_volume
            }
            
            return TradingSignal(
                signal=signal,
                confidence=confidence,
                price=current_price,
                timestamp=data.index[-1] if hasattr(data.index[-1], 'isoformat') else None,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"Error generating volatility breakout signal: {e}")
            return TradingSignal(Signal.HOLD, 0.0)
    
    def get_required_history(self) -> int:
        """
        Get minimum number of data points required
        
        Returns:
            Minimum number of historical data points
        """
        return self.params['lookback_period'] * 2 + 5
    
    def _setup_indicators(self, market_data: pd.DataFrame) -> None:
        """
        Setup indicators
        
        Args:
            market_data: Historical market data
        """
        logger.info(f"Volatility Breakout strategy setup with lookback {self.params['lookback_period']}, "
                   f"multiplier {self.params['volatility_multiplier']}")
    
    def should_exit_position(self, market_data: pd.DataFrame, 
                           entry_price: float, current_price: float,
                           position_side: str) -> tuple:
        """
        Override exit logic for volatility strategy
        
        Args:
            market_data: Current market data
            entry_price: Position entry price
            current_price: Current market price
            position_side: "BUY" or "SELL"
            
        Returns:
            Tuple of (should_exit, reason)
        """
        # Standard stop loss/take profit
        should_exit, reason = super().should_exit_position(
            market_data, entry_price, current_price, position_side
        )
        
        if should_exit:
            return should_exit, reason
        
        # Additional exit: mean reversion
        try:
            lookback_period = self.params['lookback_period']
            volatility_multiplier = self.params['volatility_multiplier']
            
            upper_band, lower_band, middle, _ = self.calculate_volatility_bands(
                market_data['close'], lookback_period, volatility_multiplier
            )
            
            current_middle = middle.iloc[-1]
            
            # Exit long positions if price returns to middle band
            if position_side == "BUY" and current_price <= current_middle:
                return True, "mean_reversion"
            
            # Exit short positions if price returns to middle band
            if position_side == "SELL" and current_price >= current_middle:
                return True, "mean_reversion"
                
        except Exception as e:
            logger.error(f"Error in volatility exit logic: {e}")
        
        return False, ""
    
    def get_strategy_description(self) -> str:
        """
        Get human-readable strategy description
        
        Returns:
            Strategy description
        """
        return (f"Volatility Breakout Strategy using {self.params['lookback_period']}-period volatility bands "
                f"with {self.params['volatility_multiplier']}x multiplier. "
                f"Trades breakouts above/below volatility bands with minimum volume {self.params['min_volume']}")
    
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
        
        lookback_period = self.params['lookback_period']
        volatility_multiplier = self.params['volatility_multiplier']
        
        upper_band, lower_band, middle, volatility = self.calculate_volatility_bands(
            market_data['close'], lookback_period, volatility_multiplier
        )
        
        return {
            'upper_band': upper_band.iloc[-1] if not upper_band.isna().iloc[-1] else 0,
            'lower_band': lower_band.iloc[-1] if not lower_band.isna().iloc[-1] else 0,
            'middle_band': middle.iloc[-1] if not middle.isna().iloc[-1] else 0,
            'volatility': volatility.iloc[-1] if not volatility.isna().iloc[-1] else 0,
            'current_price': market_data['close'].iloc[-1]
        }
