# logger_setup.py

import logging
import os
from datetime import datetime
from functools import wraps
import traceback

def setup_logger(scraper_name):
    """
    Set up a logger with both file and console handlers for a specific scraper.
    
    Args:
        scraper_name (str): Name of the scraper (e.g., 'kenpom', 'barttorvik', 'evanmiya')
        
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(scraper_name)
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers if any
    if logger.handlers:
        logger.handlers.clear()
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter(
        '%(name)s | %(levelname)s | %(message)s'
    )
    
    # File handler - daily rotating log file
    today = datetime.now().strftime('%Y-%m-%d')
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f'{scraper_name}_{today}.log')
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_scraper_execution(func):
    """
    Decorator to log the execution of scraper functions.
    
    Args:
        func: The scraper function to be decorated
        
    Returns:
        wrapper: The decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        scraper_name = func.__module__.split('.')[-1]
        logger = setup_logger(scraper_name)
        
        logger.info(f"Starting {func.__name__}")
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            
            # Log DataFrame info if result is a pandas DataFrame
            if hasattr(result, 'shape'):
                logger.info(f"Scraped {result.shape[0]} rows and {result.shape[1]} columns")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Completed {func.__name__} in {execution_time:.2f} seconds")
            return result
            
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
            
    return wrapper