"""
Base strategy class for all trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
from enum import Enum

from src.utils.logger import get_logger
from src.utils.exceptions import StrategyError

logger = get_logger(__name__)


class Signal(Enum):
    """Trading signals"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class TradingSignal:
    """Trading signal with additional information"""
    signal: Signal
    confidence: float  # 0.0 to 1.0
    price: Optional[float] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")


@dataclass
class StrategyMetrics:
    """Strategy performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    
    def update_metrics(self, returns: pd.Series):
        """Update metrics based on returns series"""
        if len(returns) == 0:
            return
            
        self.total_trades = len(returns)
        self.winning_trades = len(returns[returns > 0])
        self.losing_trades = len(returns[returns < 0])
        self.total_return = returns.sum()
        
        # Calculate drawdown
        cumulative_returns = (1 + returns).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        self.max_drawdown = drawdown.min()
        
        # Calculate Sharpe ratio (assuming daily returns)
        if returns.std() > 0:
            self.sharpe_ratio = (returns.mean() / returns.std()) * (252 ** 0.5)  # Annualized
        
        # Win rate and average win/loss
        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        if self.winning_trades > 0:
            self.avg_win = returns[returns > 0].mean()
        if self.losing_trades > 0:
            self.avg_loss = returns[returns < 0].mean()


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, name: str, **params):
        """
        Initialize strategy
        
        Args:
            name: Strategy name
            **params: Strategy parameters
        """
        self.name = name
        self.params = params
        self.metrics = StrategyMetrics()
        self._initialized = False
        
        logger.info(f"Initialized strategy: {self.name} with params: {params}")
    
    @abstractmethod
    def generate_signal(self, market_data: pd.DataFrame) -> TradingSignal:
        """
        Generate trading signal based on market data
        
        Args:
            market_data: DataFrame with OHLCV data
            
        Returns:
            TradingSignal object
        """
        pass
    
    def initialize(self, market_data: pd.DataFrame) -> None:
        """
        Initialize strategy with historical data if needed
        
        Args:
            market_data: Historical market data
        """
        if not self._initialized:
            self._setup_indicators(market_data)
            self._initialized = True
            logger.info(f"Strategy {self.name} initialized")
    
    def _setup_indicators(self, market_data: pd.DataFrame) -> None:
        """
        Setup technical indicators (override in subclasses)
        
        Args:
            market_data: Historical market data
        """
        pass
    
    def validate_data(self, market_data: pd.DataFrame) -> bool:
        """
        Validate market data before generating signals
        
        Args:
            market_data: Market data to validate
            
        Returns:
            True if data is valid
        """
        if market_data is None or market_data.empty:
            logger.warning(f"Strategy {self.name}: Empty market data")
            return False
            
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in market_data.columns]
        
        if missing_columns:
            logger.error(f"Strategy {self.name}: Missing columns: {missing_columns}")
            return False
            
        if len(market_data) < self.get_required_history():
            logger.warning(f"Strategy {self.name}: Insufficient data points")
            return False
            
        return True
    
    @abstractmethod
    def get_required_history(self) -> int:
        """
        Get minimum number of data points required for strategy
        
        Returns:
            Minimum number of historical data points
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """
        Get strategy parameters
        
        Returns:
            Dictionary of parameters
        """
        return self.params.copy()
    
    def update_parameters(self, **params):
        """
        Update strategy parameters
        
        Args:
            **params: Parameters to update
        """
        self.params.update(params)
        self._initialized = False  # Force re-initialization
        logger.info(f"Updated parameters for {self.name}: {params}")
    
    def calculate_position_size(self, account_balance: float, current_price: float, 
                              signal: TradingSignal) -> float:
        """
        Calculate position size based on signal and account balance
        
        Args:
            account_balance: Available account balance
            current_price: Current asset price
            signal: Trading signal
            
        Returns:
            Position size in quote currency (e.g., USD)
        """
        # Default implementation: fixed position size adjusted by confidence
        base_size = self.params.get('position_size', 100.0)
        confidence_adjusted_size = base_size * signal.confidence
        
        # Don't exceed account balance
        max_size = min(confidence_adjusted_size, account_balance * 0.1)  # Max 10% of balance
        
        return max_size
    
    def should_exit_position(self, market_data: pd.DataFrame, 
                           entry_price: float, current_price: float,
                           position_side: str) -> Tuple[bool, str]:
        """
        Determine if position should be closed
        
        Args:
            market_data: Current market data
            entry_price: Position entry price
            current_price: Current market price
            position_side: "BUY" or "SELL"
            
        Returns:
            Tuple of (should_exit, reason)
        """
        # Default implementation: simple stop loss and take profit
        stop_loss_pct = self.params.get('stop_loss_pct', 0.05)
        take_profit_pct = self.params.get('take_profit_pct', 0.10)
        
        if position_side == "BUY":
            pnl_pct = (current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - current_price) / entry_price
        
        if pnl_pct <= -stop_loss_pct:
            return True, "stop_loss"
        elif pnl_pct >= take_profit_pct:
            return True, "take_profit"
        
        return False, ""
    
    def get_metrics(self) -> StrategyMetrics:
        """
        Get strategy performance metrics
        
        Returns:
            StrategyMetrics object
        """
        return self.metrics
    
    def reset_metrics(self):
        """Reset strategy metrics"""
        self.metrics = StrategyMetrics()
        logger.info(f"Reset metrics for strategy {self.name}")
    
    def __str__(self):
        return f"Strategy(name={self.name}, params={self.params})"
    
    def __repr__(self):
        return self.__str__()
