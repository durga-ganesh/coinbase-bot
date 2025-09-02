"""
Configuration management for the trading bot
"""

import os
import yaml
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from src.utils.exceptions import ConfigurationError
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TradingConfig:
    """Trading configuration settings"""
    default_position_size: float = 100.0
    max_position_size: float = 1000.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.10
    max_slippage_pct: float = 0.01


@dataclass
class RiskManagementConfig:
    """Risk management configuration settings"""
    max_daily_loss: float = 500.0
    max_open_positions: int = 5
    max_portfolio_risk_pct: float = 0.02
    position_sizing_method: str = "fixed"  # "fixed", "percentage", "kelly"


@dataclass
class BacktestConfig:
    """Backtesting configuration settings"""
    initial_capital: float = 10000.0
    commission_rate: float = 0.005
    slippage_rate: float = 0.001
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@dataclass
class LoggingConfig:
    """Logging configuration settings"""
    level: str = "INFO"
    file: str = "logs/trading.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class Config:
    """Main configuration class"""
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk_management: RiskManagementConfig = field(default_factory=RiskManagementConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    strategies: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'Config':
        """
        Load configuration from YAML file
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Config instance
        """
        try:
            if not os.path.exists(config_path):
                logger.warning(f"[CONF ] Config file {config_path} not found, using defaults")
                return cls()
                
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f) or {}
            
            # Create config sections
            trading_config = TradingConfig(**config_data.get('trading', {}))
            risk_config = RiskManagementConfig(**config_data.get('risk_management', {}))
            backtest_config = BacktestConfig(**config_data.get('backtest', {}))
            logging_config = LoggingConfig(**config_data.get('logging', {}))
            
            config = cls(
                trading=trading_config,
                risk_management=risk_config,
                backtest=backtest_config,
                logging=logging_config,
                strategies=config_data.get('strategies', {})
            )
            
            logger.info(f"[CONF ] Configuration loaded from {config_path}")
            return config
            
        except Exception as e:
            logger.error(f"[CONF ] Failed to load configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    @classmethod
    def from_env(cls) -> 'Config':
        """
        Load configuration from environment variables
        
        Returns:
            Config instance
        """
        try:
            trading_config = TradingConfig(
                default_position_size=float(os.getenv('DEFAULT_POSITION_SIZE', 100.0)),
                max_position_size=float(os.getenv('MAX_POSITION_SIZE', 1000.0)),
                stop_loss_pct=float(os.getenv('STOP_LOSS_PCT', 0.05)),
                take_profit_pct=float(os.getenv('TAKE_PROFIT_PCT', 0.10)),
                max_slippage_pct=float(os.getenv('MAX_SLIPPAGE_PCT', 0.01))
            )
            
            risk_config = RiskManagementConfig(
                max_daily_loss=float(os.getenv('MAX_DAILY_LOSS', 500.0)),
                max_open_positions=int(os.getenv('MAX_OPEN_POSITIONS', 5)),
                max_portfolio_risk_pct=float(os.getenv('MAX_PORTFOLIO_RISK_PCT', 0.02)),
                position_sizing_method=os.getenv('POSITION_SIZING_METHOD', 'fixed')
            )
            
            backtest_config = BacktestConfig(
                initial_capital=float(os.getenv('INITIAL_CAPITAL', 10000.0)),
                commission_rate=float(os.getenv('COMMISSION_RATE', 0.005)),
                slippage_rate=float(os.getenv('SLIPPAGE_RATE', 0.001))
            )
            
            logging_config = LoggingConfig(
                level=os.getenv('LOG_LEVEL', 'INFO'),
                file=os.getenv('LOG_FILE', 'logs/trading.log')
            )
            
            return cls(
                trading=trading_config,
                risk_management=risk_config,
                backtest=backtest_config,
                logging=logging_config
            )
            
        except Exception as e:
            logger.error(f"[CONF ] Failed to load configuration from environment: {e}")
            raise ConfigurationError(f"Failed to load configuration from environment: {e}")
    
    def to_file(self, config_path: str):
        """
        Save configuration to YAML file
        
        Args:
            config_path: Path to save configuration file
        """
        try:
            config_data = {
                'trading': {
                    'default_position_size': self.trading.default_position_size,
                    'max_position_size': self.trading.max_position_size,
                    'stop_loss_pct': self.trading.stop_loss_pct,
                    'take_profit_pct': self.trading.take_profit_pct,
                    'max_slippage_pct': self.trading.max_slippage_pct
                },
                'risk_management': {
                    'max_daily_loss': self.risk_management.max_daily_loss,
                    'max_open_positions': self.risk_management.max_open_positions,
                    'max_portfolio_risk_pct': self.risk_management.max_portfolio_risk_pct,
                    'position_sizing_method': self.risk_management.position_sizing_method
                },
                'backtest': {
                    'initial_capital': self.backtest.initial_capital,
                    'commission_rate': self.backtest.commission_rate,
                    'slippage_rate': self.backtest.slippage_rate,
                    'start_date': self.backtest.start_date,
                    'end_date': self.backtest.end_date
                },
                'logging': {
                    'level': self.logging.level,
                    'file': self.logging.file,
                    'format': self.logging.format
                },
                'strategies': self.strategies
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, indent=2)
            
            logger.info(f"[CONF ] Configuration saved to {config_path}")
            
        except Exception as e:
            logger.error(f"[CONF ] Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """
        Get configuration for a specific strategy
        
        Args:
            strategy_name: Name of the strategy
            
        Returns:
            Strategy configuration dictionary
        """
        return self.strategies.get(strategy_name, {})
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]):
        """
        Update configuration for a specific strategy
        
        Args:
            strategy_name: Name of the strategy
            config: Strategy configuration dictionary
        """
        self.strategies[strategy_name] = config
        logger.info(f"[CONF ] Updated configuration for strategy: {strategy_name}")


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from file or environment
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Config instance
    """
    if config_path:
        return Config.from_file(config_path)
    
    # Try default config file
    default_path = "config/config.yaml"
    if os.path.exists(default_path):
        return Config.from_file(default_path)
    
    # Fall back to environment variables
    return Config.from_env()
