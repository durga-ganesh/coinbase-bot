"""
Portfolio management for the trading bot
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd

from src.utils.logger import get_logger
from src.utils.exceptions import TradingError, InsufficientFundsError
from src.utils.config import Config

logger = get_logger(__name__)


@dataclass
class Position:
    """Represents a trading position"""
    product_id: str
    side: str  # 'BUY' or 'SELL'
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    realized_pnl: float = 0.0
    
    def update_current_price(self, price: float):
        """Update current price and calculate unrealized PnL"""
        self.current_price = price
        
        if self.side == 'BUY':
            self.unrealized_pnl = (price - self.entry_price) * self.quantity
        else:  # SELL
            self.unrealized_pnl = (self.entry_price - price) * self.quantity
    
    def get_market_value(self) -> float:
        """Get current market value of position"""
        if self.current_price is None:
            return self.entry_price * self.quantity
        return self.current_price * self.quantity
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)"""
        return self.realized_pnl + (self.unrealized_pnl or 0.0)


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics"""
    total_value: float = 0.0
    cash_balance: float = 0.0
    invested_value: float = 0.0
    total_pnl: float = 0.0
    total_return_pct: float = 0.0
    daily_return_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    num_positions: int = 0
    num_winning_trades: int = 0
    num_losing_trades: int = 0


class Portfolio:
    """Portfolio manager for tracking positions and performance"""
    
    def __init__(self, initial_capital: float, config: Optional[Config] = None):
        """
        Initialize portfolio
        
        Args:
            initial_capital: Starting capital amount
            config: Configuration object
        """
        self.initial_capital = initial_capital
        self.cash_balance = initial_capital
        self.config = config
        
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Dict] = []
        self.daily_returns: List[float] = []
        self.portfolio_values: List[Tuple[datetime, float]] = []
        
        # Risk management
        self.max_position_size = config.trading.max_position_size if config else 1000.0
        self.max_portfolio_risk = config.risk_management.max_portfolio_risk_pct if config else 0.02
        
        logger.info(f"Portfolio initialized with ${initial_capital:.2f}")
    
    def get_available_cash(self) -> float:
        """Get available cash balance"""
        return self.cash_balance
    
    def get_total_invested(self) -> float:
        """Get total value invested in positions"""
        return sum(pos.get_market_value() for pos in self.positions.values())
    
    def get_total_value(self) -> float:
        """Get total portfolio value (cash + positions)"""
        return self.cash_balance + self.get_total_invested()
    
    def get_position(self, product_id: str) -> Optional[Position]:
        """
        Get position for a product
        
        Args:
            product_id: Product identifier
            
        Returns:
            Position object or None
        """
        return self.positions.get(product_id)
    
    def add_position(self, product_id: str, side: str, quantity: float, 
                    price: float, timestamp: Optional[datetime] = None) -> Position:
        """
        Add a new position or update existing position
        
        Args:
            product_id: Product identifier
            side: 'BUY' or 'SELL'
            quantity: Position quantity
            price: Entry price
            timestamp: Entry timestamp
            
        Returns:
            Position object
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # Calculate position value
        position_value = quantity * price
        
        # Check if we have enough cash for buy positions
        if side == 'BUY' and position_value > self.cash_balance:
            raise InsufficientFundsError(
                f"Insufficient funds: need ${position_value:.2f}, have ${self.cash_balance:.2f}"
            )
        
        # Check position size limits
        if position_value > self.max_position_size:
            raise TradingError(
                f"Position size ${position_value:.2f} exceeds maximum ${self.max_position_size:.2f}"
            )
        
        # Create or update position
        if product_id in self.positions:
            # Update existing position (average price)
            existing_pos = self.positions[product_id]
            
            if existing_pos.side != side:
                # Closing or reducing position
                if quantity >= existing_pos.quantity:
                    # Full close or reverse
                    pnl = self._calculate_pnl(existing_pos, price, existing_pos.quantity)
                    self._record_trade(existing_pos, price, existing_pos.quantity, pnl)
                    
                    if quantity > existing_pos.quantity:
                        # Reverse position
                        remaining_qty = quantity - existing_pos.quantity
                        new_position = Position(
                            product_id=product_id,
                            side=side,
                            quantity=remaining_qty,
                            entry_price=price,
                            entry_time=timestamp
                        )
                        self.positions[product_id] = new_position
                        
                        # Update cash
                        if side == 'BUY':
                            self.cash_balance -= remaining_qty * price
                        else:
                            self.cash_balance += remaining_qty * price
                    else:
                        # Full close
                        del self.positions[product_id]
                        if side == 'BUY':
                            self.cash_balance += pnl
                        else:
                            self.cash_balance -= pnl
                else:
                    # Partial close
                    pnl = self._calculate_pnl(existing_pos, price, quantity)
                    self._record_trade(existing_pos, price, quantity, pnl)
                    
                    existing_pos.quantity -= quantity
                    existing_pos.realized_pnl += pnl
                    
                    if side == 'BUY':
                        self.cash_balance += pnl
                    else:
                        self.cash_balance -= pnl
            else:
                # Add to existing position
                total_value = (existing_pos.quantity * existing_pos.entry_price) + (quantity * price)
                total_quantity = existing_pos.quantity + quantity
                existing_pos.entry_price = total_value / total_quantity
                existing_pos.quantity = total_quantity
                
                # Update cash
                if side == 'BUY':
                    self.cash_balance -= quantity * price
                else:
                    self.cash_balance += quantity * price
        else:
            # New position
            new_position = Position(
                product_id=product_id,
                side=side,
                quantity=quantity,
                entry_price=price,
                entry_time=timestamp
            )
            self.positions[product_id] = new_position
            
            # Update cash
            if side == 'BUY':
                self.cash_balance -= position_value
            else:
                self.cash_balance += position_value
        
        logger.info(f"Added position: {product_id} {side} {quantity:.6f} @ ${price:.2f}")
        return self.positions[product_id]
    
    def close_position(self, product_id: str, price: float, 
                      timestamp: Optional[datetime] = None) -> Optional[float]:
        """
        Close a position
        
        Args:
            product_id: Product identifier
            price: Exit price
            timestamp: Exit timestamp
            
        Returns:
            Realized PnL or None if position doesn't exist
        """
        if product_id not in self.positions:
            logger.warning(f"No position found for {product_id}")
            return None
        
        position = self.positions[product_id]
        pnl = self._calculate_pnl(position, price, position.quantity)
        
        self._record_trade(position, price, position.quantity, pnl)
        
        # Update cash based on position type
        if position.side == 'BUY':
            self.cash_balance += position.quantity * price
        else:
            self.cash_balance += pnl  # For short positions
        
        del self.positions[product_id]
        
        logger.info(f"Closed position: {product_id} PnL: ${pnl:.2f}")
        return pnl
    
    def update_positions(self, market_prices: Dict[str, float]):
        """
        Update all positions with current market prices
        
        Args:
            market_prices: Dictionary of product_id -> current_price
        """
        for product_id, position in self.positions.items():
            if product_id in market_prices:
                position.update_current_price(market_prices[product_id])
    
    def _calculate_pnl(self, position: Position, exit_price: float, quantity: float) -> float:
        """
        Calculate PnL for a position
        
        Args:
            position: Position object
            exit_price: Exit price
            quantity: Quantity being closed
            
        Returns:
            Realized PnL
        """
        if position.side == 'BUY':
            return (exit_price - position.entry_price) * quantity
        else:  # SELL
            return (position.entry_price - exit_price) * quantity
    
    def _record_trade(self, position: Position, exit_price: float, 
                     quantity: float, pnl: float):
        """
        Record a completed trade
        
        Args:
            position: Position object
            exit_price: Exit price
            quantity: Quantity traded
            pnl: Realized PnL
        """
        trade = {
            'product_id': position.product_id,
            'side': position.side,
            'quantity': quantity,
            'entry_price': position.entry_price,
            'exit_price': exit_price,
            'entry_time': position.entry_time,
            'exit_time': datetime.now(),
            'pnl': pnl,
            'return_pct': (pnl / (position.entry_price * quantity)) * 100
        }
        
        self.trade_history.append(trade)
    
    def get_metrics(self) -> PortfolioMetrics:
        """
        Calculate portfolio performance metrics
        
        Returns:
            PortfolioMetrics object
        """
        total_value = self.get_total_value()
        invested_value = self.get_total_invested()
        
        # Calculate total PnL
        realized_pnl = sum(trade['pnl'] for trade in self.trade_history)
        unrealized_pnl = sum(pos.unrealized_pnl or 0.0 for pos in self.positions.values())
        total_pnl = realized_pnl + unrealized_pnl
        
        # Calculate returns
        total_return_pct = (total_value - self.initial_capital) / self.initial_capital * 100
        
        # Win/loss statistics
        winning_trades = [t for t in self.trade_history if t['pnl'] > 0]
        losing_trades = [t for t in self.trade_history if t['pnl'] < 0]
        win_rate = len(winning_trades) / len(self.trade_history) if self.trade_history else 0
        
        # TODO: Calculate Sharpe ratio and max drawdown properly
        
        return PortfolioMetrics(
            total_value=total_value,
            cash_balance=self.cash_balance,
            invested_value=invested_value,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            win_rate=win_rate,
            num_positions=len(self.positions),
            num_winning_trades=len(winning_trades),
            num_losing_trades=len(losing_trades)
        )
    
    def get_position_summary(self) -> pd.DataFrame:
        """
        Get summary of all positions
        
        Returns:
            DataFrame with position information
        """
        if not self.positions:
            return pd.DataFrame()
        
        data = []
        for pos in self.positions.values():
            data.append({
                'Product': pos.product_id,
                'Side': pos.side,
                'Quantity': pos.quantity,
                'Entry Price': pos.entry_price,
                'Current Price': pos.current_price or pos.entry_price,
                'Market Value': pos.get_market_value(),
                'Unrealized PnL': pos.unrealized_pnl or 0.0,
                'Entry Time': pos.entry_time
            })
        
        return pd.DataFrame(data)
    
    def get_trade_summary(self) -> pd.DataFrame:
        """
        Get summary of all trades
        
        Returns:
            DataFrame with trade history
        """
        if not self.trade_history:
            return pd.DataFrame()
        
        return pd.DataFrame(self.trade_history)
    
    def reset(self):
        """Reset portfolio to initial state"""
        self.cash_balance = self.initial_capital
        self.positions.clear()
        self.trade_history.clear()
        self.daily_returns.clear()
        self.portfolio_values.clear()
        
        logger.info("Portfolio reset to initial state")
