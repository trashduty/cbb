# logger_setup.py

import logging
import os
from datetime import datetime
from functools import wraps
import traceback
from rich.logging import RichHandler
from rich.console import Console
from rich.traceback import install
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
import time

# Install rich traceback handler
install(show_locals=True)

# Create rich console
console = Console()

def setup_logger(scraper_name):
    """
    Set up a logger with both file and rich console handlers for a specific scraper.
    
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
    
    # File handler - daily rotating log file
    today = datetime.now().strftime('%Y-%m-%d')
    file_handler = logging.FileHandler(
        os.path.join(log_dir, f'{scraper_name}_{today}.log')
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)
    
    # Rich console handler
    console_handler = RichHandler(
        rich_tracebacks=True,
        console=console,
        show_time=False,
        show_path=False,
        markup=True
    )
    console_handler.setLevel(logging.INFO)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_scraper_execution(func):
    """
    Decorator to log the execution of scraper functions with rich progress bars
    and better error handling.
    
    Args:
        func: The scraper function to be decorated
        
    Returns:
        wrapper: The decorated function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        scraper_name = func.__module__.split('.')[-1]
        logger = setup_logger(scraper_name)
        
        # Create a progress context
        with Progress(
            SpinnerColumn(),
            *Progress.get_default_columns(),
            TimeElapsedColumn(),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"[cyan]Running {func.__name__}...", total=None)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                
                # Log DataFrame info if result is a pandas DataFrame
                if hasattr(result, 'shape'):
                    logger.info(f"[green]✓[/green] Scraped {result.shape[0]} rows and {result.shape[1]} columns")
                
                execution_time = time.time() - start_time
                logger.info(f"[green]✓[/green] Completed {func.__name__} in {execution_time:.2f} seconds")
                
                return result
                
            except Exception as e:
                logger.error(f"[red]✗[/red] Error in {func.__name__}: {str(e)}")
                logger.error(f"[red]Traceback:[/red]\n{traceback.format_exc()}")
                raise
            finally:
                progress.update(task, completed=True)
                
    return wrapper