"""
Custom exceptions for the trading bot
"""


class TradingError(Exception):
    """Base exception for trading-related errors"""
    pass


class APIError(TradingError):
    """Exception for API-related errors"""
    pass


class ConfigurationError(TradingError):
    """Exception for configuration-related errors"""
    pass


class StrategyError(TradingError):
    """Exception for strategy-related errors"""
    pass


class InsufficientFundsError(TradingError):
    """Exception for insufficient funds"""
    pass


class InvalidOrderError(TradingError):
    """Exception for invalid orders"""
    pass


class MarketDataError(TradingError):
    """Exception for market data related errors"""
    pass


class BacktestError(TradingError):
    """Exception for backtesting related errors"""
    pass
