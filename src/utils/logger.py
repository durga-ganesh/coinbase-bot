"""
Logging configuration for the trading bot
"""

import os
import logging
import logging.config
from datetime import datetime
from typing import Optional


def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (typically __name__)
        level: Optional log level override
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Create logs directory if it doesn't exist
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Set level from environment or parameter
        log_level = level or os.getenv('LOG_LEVEL', 'INFO')
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(log_dir, f'trading-{today}.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger


def setup_logging(config_file: Optional[str] = None):
    """
    Setup logging configuration
    
    Args:
        config_file: Optional path to logging config file
    """
    if config_file and os.path.exists(config_file):
        logging.config.fileConfig(config_file)
    else:
        # Default configuration
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(f'logs/trading-{datetime.now().strftime("%Y-%m-%d")}.log')
            ]
        )


# Create default logger
logger = get_logger(__name__)
