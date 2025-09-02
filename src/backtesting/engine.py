"""
Backtesting engine for trading strategies
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import warnings

from src.strategies.base import BaseStrategy, Signal, TradingSignal
from src.core.portfolio import Portfolio
from src.utils.logger import get_logger
from src.utils.exceptions import BacktestError
from src.utils.config import Config

logger = get_logger(__name__)
warnings.filterwarnings('ignore')


class BacktestEngine:
    """Engine for backtesting trading strategies"""
    
    def __init__(self, initial_capital: float = 10000, 
                 commission_rate: float = 0.005, 
                 slippage_rate: float = 0.001,
                 config: Optional[Config] = None):
        """
        Initialize backtest engine
        
        Args:
            initial_capital: Starting capital
            commission_rate: Commission rate per trade
            slippage_rate: Price slippage rate
            config: Configuration object
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.slippage_rate = slippage_rate
        self.config = config
        
        self.portfolio = Portfolio(initial_capital, config)
        self.results: Dict[str, Any] = {}
        
        logger.info(f"Backtest engine initialized with ${initial_capital:.2f} capital")
    
    def run_backtest(self, strategy: BaseStrategy, market_data: pd.DataFrame,
                    product_id: str = "BTC-USD",
                    start_date: Optional[str] = None,
                    end_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Run backtest for a strategy
        
        Args:
            strategy: Trading strategy to test
            market_data: Historical market data
            product_id: Product identifier
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            
        Returns:
            Backtest results dictionary
        """
        try:
            # Filter data by date range if specified
            if start_date or end_date:
                market_data = self._filter_by_date_range(market_data, start_date, end_date)
            
            if market_data.empty:
                raise BacktestError("No market data available for backtest")
            
            # Reset portfolio
            self.portfolio.reset()
            
            # Initialize strategy with some historical data
            min_history = strategy.get_required_history()
            if len(market_data) < min_history:
                raise BacktestError(f"Insufficient data: need {min_history}, have {len(market_data)}")
            
            # Initialize strategy with first portion of data
            strategy.initialize(market_data.iloc[:min_history])
            
            # Run backtest
            signals = []
            portfolio_values = []
            trades = []
            
            current_position = None
            
            logger.info(f"Starting backtest: {strategy.name} on {product_id}")
            logger.info(f"Period: {market_data.index[0]} to {market_data.index[-1]}")
            
            for i in range(min_history, len(market_data)):
                current_data = market_data.iloc[:i+1]
                current_row = market_data.iloc[i]
                current_price = current_row['close']
                current_time = current_row.name if hasattr(current_row, 'name') else datetime.now()
                
                # Update portfolio with current prices
                self.portfolio.update_positions({product_id: current_price})
                
                # Record portfolio value
                portfolio_value = self.portfolio.get_total_value()
                portfolio_values.append({
                    'timestamp': current_time,
                    'portfolio_value': portfolio_value,
                    'cash': self.portfolio.cash_balance,
                    'positions': self.portfolio.get_total_invested()
                })
                
                # Generate signal
                try:
                    signal = strategy.generate_signal(current_data)
                    signals.append({
                        'timestamp': current_time,
                        'signal': signal.signal.value,
                        'confidence': signal.confidence,
                        'price': current_price,
                        'metadata': signal.metadata
                    })
                except Exception as e:
                    logger.error(f"Error generating signal at {current_time}: {e}")
                    continue
                
                # Execute trades based on signals
                if signal.confidence > 0.5:  # Minimum confidence threshold
                    trade_executed = self._execute_signal(
                        signal, product_id, current_price, current_time, strategy
                    )
                    
                    if trade_executed:
                        trades.append(trade_executed)
                
                # Check exit conditions for existing positions
                position = self.portfolio.get_position(product_id)
                if position:
                    should_exit, reason = strategy.should_exit_position(
                        current_data, position.entry_price, current_price, position.side
                    )
                    
                    if should_exit:
                        pnl = self.portfolio.close_position(product_id, current_price, current_time)
                        if pnl is not None:
                            trades.append({
                                'timestamp': current_time,
                                'action': 'CLOSE',
                                'product_id': product_id,
                                'price': current_price,
                                'quantity': position.quantity,
                                'pnl': pnl,
                                'reason': reason
                            })
            
            # Calculate final results
            self.results = self._calculate_results(
                portfolio_values, signals, trades, market_data, strategy
            )
            
            logger.info(f"Backtest completed. Total return: {self.results['total_return']:.2f}%")
            return self.results
            
        except Exception as e:
            logger.error(f"Backtest failed: {e}")
            raise BacktestError(f"Backtest failed: {e}")
    
    def _filter_by_date_range(self, data: pd.DataFrame, 
                             start_date: Optional[str], 
                             end_date: Optional[str]) -> pd.DataFrame:
        """Filter data by date range"""
        filtered_data = data.copy()
        
        if start_date:
            filtered_data = filtered_data[filtered_data.index >= start_date]
        
        if end_date:
            filtered_data = filtered_data[filtered_data.index <= end_date]
        
        return filtered_data
    
    def _execute_signal(self, signal: TradingSignal, product_id: str, 
                       price: float, timestamp: datetime, 
                       strategy: BaseStrategy) -> Optional[Dict]:
        """
        Execute a trading signal
        
        Args:
            signal: Trading signal
            product_id: Product identifier  
            price: Current price
            timestamp: Current timestamp
            strategy: Trading strategy
            
        Returns:
            Trade information dictionary or None
        """
        try:
            if signal.signal == Signal.HOLD:
                return None
            
            # Apply slippage
            if signal.signal == Signal.BUY:
                execution_price = price * (1 + self.slippage_rate)
            else:
                execution_price = price * (1 - self.slippage_rate)
            
            # Calculate position size
            account_balance = self.portfolio.get_available_cash()
            position_size_usd = strategy.calculate_position_size(
                account_balance, execution_price, signal
            )
            
            if position_size_usd < 10:  # Minimum trade size
                return None
            
            # Calculate quantity
            if signal.signal == Signal.BUY:
                quantity = position_size_usd / execution_price
                # Apply commission
                commission = position_size_usd * self.commission_rate
                effective_size = position_size_usd + commission
                
                if effective_size <= account_balance:
                    self.portfolio.add_position(
                        product_id, 'BUY', quantity, execution_price, timestamp
                    )
                    
                    return {
                        'timestamp': timestamp,
                        'action': 'BUY',
                        'product_id': product_id,
                        'price': execution_price,
                        'quantity': quantity,
                        'value': position_size_usd,
                        'commission': commission,
                        'confidence': signal.confidence
                    }
            
            elif signal.signal == Signal.SELL:
                # For sell signals, check if we have a position to sell
                position = self.portfolio.get_position(product_id)
                if position and position.side == 'BUY':
                    quantity = position.quantity
                    commission = quantity * execution_price * self.commission_rate
                    
                    pnl = self.portfolio.close_position(product_id, execution_price, timestamp)
                    
                    return {
                        'timestamp': timestamp,
                        'action': 'SELL',
                        'product_id': product_id,
                        'price': execution_price,
                        'quantity': quantity,
                        'value': quantity * execution_price,
                        'commission': commission,
                        'pnl': pnl,
                        'confidence': signal.confidence
                    }
            
            return None
            
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None
    
    def _calculate_results(self, portfolio_values: List[Dict], 
                          signals: List[Dict], trades: List[Dict],
                          market_data: pd.DataFrame, 
                          strategy: BaseStrategy) -> Dict[str, Any]:
        """Calculate backtest results and metrics"""
        
        if not portfolio_values:
            return {}
        
        # Convert to DataFrames for easier analysis
        portfolio_df = pd.DataFrame(portfolio_values)
        portfolio_df.set_index('timestamp', inplace=True)
        
        signals_df = pd.DataFrame(signals) if signals else pd.DataFrame()
        trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
        
        # Calculate returns
        portfolio_df['returns'] = portfolio_df['portfolio_value'].pct_change()
        
        # Calculate cumulative returns
        portfolio_df['cumulative_return'] = (1 + portfolio_df['returns']).cumprod()
        
        # Buy and hold benchmark
        initial_price = market_data['close'].iloc[0]
        final_price = market_data['close'].iloc[-1]
        buy_hold_return = (final_price - initial_price) / initial_price * 100
        
        # Strategy metrics
        total_return = (portfolio_df['portfolio_value'].iloc[-1] - self.initial_capital) / self.initial_capital * 100
        
        # Volatility (annualized)
        volatility = portfolio_df['returns'].std() * np.sqrt(252) * 100
        
        # Sharpe ratio (assuming 0% risk-free rate)
        sharpe_ratio = (portfolio_df['returns'].mean() / portfolio_df['returns'].std()) * np.sqrt(252) if portfolio_df['returns'].std() > 0 else 0
        
        # Maximum drawdown
        peak = portfolio_df['portfolio_value'].expanding().max()
        drawdown = (portfolio_df['portfolio_value'] - peak) / peak * 100
        max_drawdown = drawdown.min()
        
        # Trade statistics
        if not trades_df.empty:
            profitable_trades = trades_df[trades_df['pnl'] > 0] if 'pnl' in trades_df.columns else pd.DataFrame()
            losing_trades = trades_df[trades_df['pnl'] < 0] if 'pnl' in trades_df.columns else pd.DataFrame()
            
            win_rate = len(profitable_trades) / len(trades_df) * 100 if len(trades_df) > 0 else 0
            avg_win = profitable_trades['pnl'].mean() if len(profitable_trades) > 0 else 0
            avg_loss = losing_trades['pnl'].mean() if len(losing_trades) > 0 else 0
            profit_factor = abs(profitable_trades['pnl'].sum() / losing_trades['pnl'].sum()) if len(losing_trades) > 0 and losing_trades['pnl'].sum() != 0 else 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
        
        # Signal statistics
        if not signals_df.empty:
            buy_signals = len(signals_df[signals_df['signal'] == 'BUY'])
            sell_signals = len(signals_df[signals_df['signal'] == 'SELL'])
            hold_signals = len(signals_df[signals_df['signal'] == 'HOLD'])
            avg_confidence = signals_df['confidence'].mean()
        else:
            buy_signals = sell_signals = hold_signals = 0
            avg_confidence = 0
        
        results = {
            # Performance metrics
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'excess_return': total_return - buy_hold_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            
            # Portfolio metrics
            'initial_capital': self.initial_capital,
            'final_value': portfolio_df['portfolio_value'].iloc[-1],
            'max_value': portfolio_df['portfolio_value'].max(),
            'min_value': portfolio_df['portfolio_value'].min(),
            
            # Trade metrics
            'total_trades': len(trades_df),
            'winning_trades': len(profitable_trades) if not trades_df.empty else 0,
            'losing_trades': len(losing_trades) if not trades_df.empty else 0,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            
            # Signal metrics
            'total_signals': len(signals_df),
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'hold_signals': hold_signals,
            'avg_confidence': avg_confidence,
            
            # Time metrics
            'start_date': portfolio_df.index[0],
            'end_date': portfolio_df.index[-1],
            'duration_days': (portfolio_df.index[-1] - portfolio_df.index[0]).days,
            
            # Data
            'portfolio_values': portfolio_df,
            'signals': signals_df,
            'trades': trades_df,
            'strategy_name': strategy.name,
            'strategy_params': strategy.get_parameters()
        }
        
        return results
    
    def get_results_summary(self) -> str:
        """Get a formatted summary of backtest results"""
        if not self.results:
            return "No backtest results available"
        
        summary = f"""
=== Backtest Results Summary ===
Strategy: {self.results['strategy_name']}
Period: {self.results['start_date']} to {self.results['end_date']} ({self.results['duration_days']} days)

Performance Metrics:
  Total Return: {self.results['total_return']:.2f}%
  Buy & Hold Return: {self.results['buy_hold_return']:.2f}%
  Excess Return: {self.results['excess_return']:.2f}%
  Volatility: {self.results['volatility']:.2f}%
  Sharpe Ratio: {self.results['sharpe_ratio']:.2f}
  Max Drawdown: {self.results['max_drawdown']:.2f}%

Portfolio Metrics:
  Initial Capital: ${self.results['initial_capital']:,.2f}
  Final Value: ${self.results['final_value']:,.2f}
  Max Value: ${self.results['max_value']:,.2f}

Trade Metrics:
  Total Trades: {self.results['total_trades']}
  Winning Trades: {self.results['winning_trades']}
  Losing Trades: {self.results['losing_trades']}
  Win Rate: {self.results['win_rate']:.1f}%
  Average Win: ${self.results['avg_win']:.2f}
  Average Loss: ${self.results['avg_loss']:.2f}
  Profit Factor: {self.results['profit_factor']:.2f}

Signal Metrics:
  Total Signals: {self.results['total_signals']}
  Buy Signals: {self.results['buy_signals']}
  Sell Signals: {self.results['sell_signals']}
  Hold Signals: {self.results['hold_signals']}
  Average Confidence: {self.results['avg_confidence']:.2f}
        """
        
        return summary.strip()
    
    def save_results(self, filepath: str):
        """Save backtest results to file"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        try:
            # Save summary
            with open(f"{filepath}_summary.txt", 'w') as f:
                f.write(self.get_results_summary())
            
            # Save detailed data
            if 'trades' in self.results and not self.results['trades'].empty:
                self.results['trades'].to_csv(f"{filepath}_trades.csv", index=False)
            
            if 'portfolio_values' in self.results and not self.results['portfolio_values'].empty:
                self.results['portfolio_values'].to_csv(f"{filepath}_portfolio.csv")
            
            if 'signals' in self.results and not self.results['signals'].empty:
                self.results['signals'].to_csv(f"{filepath}_signals.csv", index=False)
            
            logger.info(f"Backtest results saved to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
