"""
Centralized logging system for the AI Game.

Provides beautiful, structured logging using Rich console output with support for:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Colored and formatted output
- Structured logging for different components
- File logging with rotation
- Performance timing utilities
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install as install_rich_traceback
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None
    RichHandler = None


class GameLogger:
    """Centralized logger for the AI Game with Rich integration."""
    
    _instance: Optional['GameLogger'] = None
    _loggers: Dict[str, logging.Logger] = {}
    
    def __new__(cls) -> 'GameLogger':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        self.console = Console() if RICH_AVAILABLE else None
        self._setup_rich_traceback()
        self._setup_base_logging()
    
    def _setup_rich_traceback(self):
        """Setup rich traceback for better error display."""
        if RICH_AVAILABLE:
            install_rich_traceback(console=self.console, show_locals=True)
    
    def _setup_base_logging(self):
        """Setup base logging configuration."""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        root_logger.handlers.clear()
        
        # Add Rich handler for console output
        if RICH_AVAILABLE:
            rich_handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=True,
                markup=True,
                rich_tracebacks=True
            )
            rich_handler.setLevel(logging.INFO)
            root_logger.addHandler(rich_handler)
        else:
            # Fallback to standard console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            root_logger.addHandler(console_handler)
        
        # Add file handler for persistent logging
        file_handler = logging.FileHandler(
            log_dir / f"aigame_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger for a specific component."""
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(f"aigame.{name}")
        return self._loggers[name]
    
    def set_level(self, level: str):
        """Set the logging level for all loggers."""
        numeric_level = getattr(logging, level.upper(), logging.INFO)
        logging.getLogger().setLevel(numeric_level)
        
        # Update all handlers
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(numeric_level)
    
    def debug_panel(self, title: str, content: Dict[str, Any], logger_name: str = "debug"):
        """Display a debug panel with structured information."""
        if not RICH_AVAILABLE:
            logger = self.get_logger(logger_name)
            logger.debug(f"{title}: {content}")
            return
        
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        for key, value in content.items():
            # Format complex values
            if isinstance(value, (dict, list)):
                value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
            else:
                value_str = str(value)
            table.add_row(key, value_str)
        
        panel = Panel(table, title=f"[bold green]{title}[/bold green]", border_style="blue")
        self.console.print(panel)
    
    def ai_request_debug(self, request_type: str, messages: list, params: dict, logger_name: str = "ai_inference"):
        """Specialized debug output for AI requests."""
        logger = self.get_logger(logger_name)
        
        if not RICH_AVAILABLE:
            logger.debug(f"AI {request_type} Request - Messages: {len(messages)}, Params: {params}")
            return
        
        # Create messages table
        msg_table = Table(show_header=True, header_style="bold magenta")
        msg_table.add_column("#", style="dim", width=3)
        msg_table.add_column("Role", style="cyan", width=10)
        msg_table.add_column("Content", style="white")
        
        for i, msg in enumerate(messages, 1):
            content = msg.get('content', '')
            # Truncate long content
            if len(content) > 80:
                content = content[:77] + "..."
            msg_table.add_row(str(i), msg.get('role', '').upper(), content)
        
        # Create params table
        param_table = Table(show_header=True, header_style="bold yellow")
        param_table.add_column("Parameter", style="cyan")
        param_table.add_column("Value", style="white")
        
        for key, value in params.items():
            if key != 'messages':  # Already shown above
                param_table.add_row(key, str(value))
        
        # Display in panels
        self.console.print(Panel(msg_table, title=f"[bold green]AI {request_type} Request - Messages[/bold green]"))
        self.console.print(Panel(param_table, title=f"[bold green]AI {request_type} Request - Parameters[/bold green]"))
        
        # Log to file as well
        logger.debug(f"AI {request_type} request with {len(messages)} messages and params: {params}")
    
    def ai_response_debug(self, request_type: str, raw_response: str, final_response: Any, logger_name: str = "ai_inference"):
        """Specialized debug output for AI responses."""
        logger = self.get_logger(logger_name)
        
        if not RICH_AVAILABLE:
            logger.debug(f"AI {request_type} Response - Raw: {raw_response[:100]}..., Final: {str(final_response)[:100]}...")
            return
        
        # Create response table
        response_table = Table(show_header=True, header_style="bold green")
        response_table.add_column("Type", style="cyan", width=15)
        response_table.add_column("Content", style="white")
        
        # Truncate long responses for display
        raw_display = raw_response[:200] + "..." if len(raw_response) > 200 else raw_response
        final_display = str(final_response)[:200] + "..." if len(str(final_response)) > 200 else str(final_response)
        
        response_table.add_row("Raw AI Output", raw_display)
        response_table.add_row("Final Response", final_display)
        
        if isinstance(final_response, dict):
            response_table.add_row("Response Type", "JSON Object")
            response_table.add_row("JSON Keys", ", ".join(final_response.keys()))
        else:
            response_table.add_row("Response Type", "Text String")
            response_table.add_row("Length", f"{len(final_response)} characters")
        
        panel = Panel(response_table, title=f"[bold green]AI {request_type} Response[/bold green]", border_style="green")
        self.console.print(panel)
        
        # Log to file as well
        logger.debug(f"AI {request_type} response - Raw length: {len(raw_response)}, Final type: {type(final_response)}")
    
    def performance_timer(self, operation_name: str, logger_name: str = "performance"):
        """Context manager for timing operations."""
        return PerformanceTimer(operation_name, self.get_logger(logger_name), self.console)
    
    def game_event(self, event_type: str, details: Dict[str, Any], logger_name: str = "game"):
        """Log game events with structured data."""
        logger = self.get_logger(logger_name)
        
        if RICH_AVAILABLE:
            self.debug_panel(f"Game Event: {event_type}", details, logger_name)
        
        logger.info(f"Game event: {event_type} - {details}")
    
    def error_with_context(self, error: Exception, context: Dict[str, Any], logger_name: str = "error"):
        """Log errors with additional context."""
        logger = self.get_logger(logger_name)
        
        if RICH_AVAILABLE:
            error_info = {
                "Error Type": type(error).__name__,
                "Error Message": str(error),
                **context
            }
            self.debug_panel("Error Context", error_info, logger_name)
        
        logger.error(f"Error: {error}", extra=context, exc_info=True)


class PerformanceTimer:
    """Context manager for timing operations with rich output."""
    
    def __init__(self, operation_name: str, logger: logging.Logger, console: Optional[Console]):
        self.operation_name = operation_name
        self.logger = logger
        self.console = console
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        if self.console and RICH_AVAILABLE:
            self.console.print(f"⏱️  Starting: [cyan]{self.operation_name}[/cyan]")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = datetime.now() - self.start_time
            duration_ms = duration.total_seconds() * 1000
            
            if self.console and RICH_AVAILABLE:
                if duration_ms < 100:
                    color = "green"
                elif duration_ms < 1000:
                    color = "yellow"
                else:
                    color = "red"
                
                self.console.print(f"✅ Completed: [cyan]{self.operation_name}[/cyan] in [{color}]{duration_ms:.2f}ms[/{color}]")
            
            self.logger.debug(f"Operation '{self.operation_name}' completed in {duration_ms:.2f}ms")


# Global logger instance
game_logger = GameLogger()

# Convenience functions for common use cases
def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific component."""
    return game_logger.get_logger(name)

def set_log_level(level: str):
    """Set the global logging level."""
    game_logger.set_level(level)

def debug_panel(title: str, content: Dict[str, Any], logger_name: str = "debug"):
    """Display a debug panel with structured information."""
    game_logger.debug_panel(title, content, logger_name)

def ai_request_debug(request_type: str, messages: list, params: dict):
    """Log AI request debug information."""
    game_logger.ai_request_debug(request_type, messages, params)

def ai_response_debug(request_type: str, raw_response: str, final_response: Any):
    """Log AI response debug information."""
    game_logger.ai_response_debug(request_type, raw_response, final_response)

def performance_timer(operation_name: str):
    """Time an operation with beautiful output."""
    return game_logger.performance_timer(operation_name)

def game_event(event_type: str, details: Dict[str, Any]):
    """Log a game event."""
    game_logger.game_event(event_type, details)

def error_with_context(error: Exception, context: Dict[str, Any]):
    """Log an error with context."""
    game_logger.error_with_context(error, context)


# Fallback implementations for when this module is imported but Rich is not available
# These are already handled gracefully in the GameLogger class, but this ensures
# the module can always be imported successfully
if not RICH_AVAILABLE:
    import warnings
    warnings.warn(
        "Rich library not found. Logging will use standard Python logging without enhanced formatting. "
        "Install rich with: pip install rich",
        ImportWarning,
        stacklevel=2
    ) 