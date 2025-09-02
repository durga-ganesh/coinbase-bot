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
        # Get log file from environment or use default
        log_file = os.getenv('LOG_FILE', 'logs/bot.log')
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Set level from environment or parameter
        log_level = level or os.getenv('LOG_LEVEL', 'INFO')
        logger.setLevel(getattr(logging, log_level.upper()))
        
        # Create formatter with fixed-width columns for better readability
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-5s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
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
        # Get log file from environment or use default
        log_file = os.getenv('LOG_FILE', 'logs/bot.log')
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Default configuration
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s | %(levelname)-5s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(log_file)
            ]
        )


# Create default logger
logger = get_logger(__name__)
