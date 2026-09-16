"""Centralized logging configuration for the expense automation system.

This module provides a singleton logger that can be imported and used
throughout the application, ensuring consistent logging configuration.
"""
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from config import Config


class AppLogger:
    """Singleton logger for the application."""
    
    _instance: Optional[logging.Logger] = None
    _initialized: bool = False
    
    @classmethod
    def get_logger(cls, name: str = "expense_automation") -> logging.Logger:
        """Get or create the application logger.
        
        Args:
            name: Logger name (default: "expense_automation")
            
        Returns:
            Configured logger instance
        """
        if cls._instance is None or not cls._initialized:
            cls._instance = cls._setup_logger(name)
            cls._initialized = True
        
        return cls._instance
    
    @classmethod
    def _setup_logger(cls, name: str) -> logging.Logger:
        """Configure and return a logger instance.
        
        Args:
            name: Logger name
            
        Returns:
            Configured logger
        """
        # Create logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        
        # Avoid duplicate handlers if logger already exists
        if logger.handlers:
            return logger
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler (detailed logs)
        log_file = Config.LOG_FOLDER / f"expense_automation_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        
        # Console handler (simpler logs)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        
        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    @classmethod
    def reset(cls):
        """Reset the logger instance (useful for testing)."""
        if cls._instance:
            # Remove all handlers
            for handler in cls._instance.handlers[:]:
                handler.close()
                cls._instance.removeHandler(handler)
        
        cls._instance = None
        cls._initialized = False


# Convenience function for easy imports
def get_logger(name: str = "expense_automation") -> logging.Logger:
    """Get the application logger.
    
    Usage:
        from src.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("Processing receipt...")
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Configured logger instance
    """
    return AppLogger.get_logger(name)