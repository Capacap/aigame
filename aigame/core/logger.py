"""
Centralized logging system for the AI Game.

Provides clean, structured logging with optional Rich console enhancement:
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Colored console output (when Rich is available)
- File logging with rotation
- Performance timing utilities
- Thread-safe singleton pattern
- Proper resource management
"""

# ============================================================================
# IMPORTS
# ============================================================================

from __future__ import annotations

import logging
import sys
import threading
import warnings
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from rich.console import Console as RichConsole

# Rich imports with graceful fallback
try:
    from rich.console import Console
    from rich.logging import RichHandler
    from rich.traceback import install as install_rich_traceback
    RICH_AVAILABLE = True
except ImportError:
    Console = RichHandler = install_rich_traceback = None
    RICH_AVAILABLE = False

# Import config settings
try:
    from . import config
except ImportError:
    config = None


# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

class LoggingDefaults:
    """Default logging configuration values."""
    CONSOLE_LEVEL = "INFO"
    FILE_LEVEL = "DEBUG"

class TextSettings:
    """Text truncation and display settings."""
    TRUNCATE_LENGTH = 100
    CONTENT_PREVIEW_LENGTH = 50

class FileSettings:
    """File logging configuration."""
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    BACKUP_COUNT = 5

class ExternalLoggers:
    """External library loggers to manage for console clutter reduction."""
    NAMES = (
        'LiteLLM', 'LiteLLM.Router', 'LiteLLM.Proxy',
        'httpx', 'openai._base_client', 'httpcore.connection',
        'httpcore.http11', 'urllib3.connectionpool',
        'requests.packages.urllib3.connectionpool'
    )

class ErrorMessages:
    """Centralized error message templates with examples."""
    
    EMPTY_LOGGER_NAME = (
        "Logger name cannot be empty. "
        "Provide a descriptive component name for the logger. "
        "Example: get_logger('game_engine') or get_logger('ai_inference')"
    )
    
    INVALID_LOG_LEVEL = (
        "Invalid log level: '{level}'. "
        "Valid levels are: DEBUG, INFO, WARNING, ERROR, CRITICAL. "
        "Example: set_log_level('DEBUG') or set_log_level('INFO')"
    )
    
    EMPTY_OPERATION_NAME = (
        "Operation name cannot be empty. "
        "Provide a descriptive name for the operation being timed. "
        "Example: performance_timer('Database query') or performance_timer('AI request')"
    )
    
    INVALID_GAME_EVENT_PARAMS = (
        "Invalid game event parameters. "
        "Event type must be a non-empty string and details must be a dictionary. "
        "Example: game_event('player_levelup', {{'player': 'Hero', 'new_level': 5}})"
    )
    
    INVALID_ERROR_CONTEXT_PARAMS = (
        "Invalid error context parameters. "
        "Error must be an Exception instance and context must be a dictionary. "
        "Example: error_with_context(exception, {{'user_id': 123, 'operation': 'save_game'}})"
    )
    
    INVALID_AI_DEBUG_PARAMS = (
        "Invalid AI debug parameters. "
        "request_type must be a non-empty string, messages must be a list, and params must be a dictionary. "
        "Example: ai_request_debug('TEXT', [{{'role': 'user', 'content': 'Hello'}}], {{'model': 'gpt-4'}})"
    )
    
    INVALID_AI_RESPONSE_PARAMS = (
        "Invalid AI response debug parameters. "
        "request_type must be a non-empty string and raw_response must be a string. "
        "Example: ai_response_debug('TEXT', 'Hello world', {{'content': 'Hello world'}})"
    )

# Backward compatibility aliases (can be removed in future versions)
DEFAULT_CONSOLE_LEVEL = LoggingDefaults.CONSOLE_LEVEL
DEFAULT_FILE_LEVEL = LoggingDefaults.FILE_LEVEL
DEFAULT_TRUNCATE_LENGTH = TextSettings.TRUNCATE_LENGTH
DEFAULT_CONTENT_PREVIEW_LENGTH = TextSettings.CONTENT_PREVIEW_LENGTH
MAX_LOG_FILE_SIZE = FileSettings.MAX_SIZE
LOG_BACKUP_COUNT = FileSettings.BACKUP_COUNT
EXTERNAL_LOGGERS = ExternalLoggers.NAMES


# ============================================================================
# CONFIGURATION INTERFACE
# ============================================================================

class LoggerConfig:
    """Configuration container with caching and validation.
    
    Provides a centralized interface for accessing configuration values with
    automatic caching and type validation. Falls back gracefully when config
    module is not available.
    """
    
    def __init__(self, config_module: Optional[Any] = None) -> None:
        """Initialize the configuration container.
        
        Args:
            config_module: Optional configuration module containing settings.
                          If None, all values will use defaults.
        
        Returns:
            None
        
        Raises:
            None: This method does not raise exceptions.
        """
        self._config_module = config_module
        self._cache: Dict[str, Any] = {}
    
    def get(self, key: str, default: Any, validate_type: Optional[type] = None) -> Any:
        """Get configuration value with caching and type validation.
        
        Args:
            key: Configuration key to retrieve.
            default: Default value to return if key is not found or invalid.
            validate_type: Optional type to validate against. If provided and
                          the value doesn't match this type, default is returned.
        
        Returns:
            Any: Configuration value from module, or default if not found/invalid.
        
        Raises:
            None: This method does not raise exceptions, returns default on errors.
        
        Example:
            >>> config = LoggerConfig(my_config_module)
            >>> level = config.get('log_level', 'INFO', str)
            >>> timeout = config.get('timeout', 30, int)
        """
        if key in self._cache:
            return self._cache[key]
        
        # Get value from config module or use default
        value = (getattr(self._config_module, key, default) 
                if self._config_module and hasattr(self._config_module, key) 
                else default)
        
        # Type validation - use default if type doesn't match
        if validate_type and value is not None and not isinstance(value, validate_type):
            value = default
        
        return self._cache.setdefault(key, value)
    
    def clear_cache(self) -> None:
        """Clear configuration cache.
        
        Args:
            None
        
        Returns:
            None
        
        Raises:
            None: This method does not raise exceptions.
        
        Example:
            >>> config.clear_cache()  # Force reload of all cached values
        """
        self._cache.clear()


# ============================================================================
# UTILITY CLASSES
# ============================================================================

class PerformanceTimer:
    """Context manager for timing operations with optional Rich output.
    
    Provides a clean interface for timing operations with automatic logging
    and optional console output. Supports both Rich-formatted and plain text
    output depending on availability.
    """
    
    def __init__(
        self,
        operation_name: str,
        logger: logging.Logger,
        console: Optional[RichConsole],
        show_in_console: bool = True
    ) -> None:
        """Initialize the performance timer.
        
        Args:
            operation_name: Descriptive name for the operation being timed.
                           Must be non-empty string.
            logger: Logger instance to write timing information to.
            console: Optional Rich console for formatted output. Can be None.
            show_in_console: Whether to display timing info in console.
                           Defaults to True.
        
        Returns:
            None
        
        Raises:
            ValueError: If operation_name is empty or None.
        
        Example:
            >>> timer = PerformanceTimer('Database query', logger, console)
            >>> with timer:
            ...     # Your timed operation here
            ...     pass
        """
        if not operation_name:
            raise ValueError(ErrorMessages.EMPTY_OPERATION_NAME.format())
        
        self.operation_name = operation_name
        self.logger = logger
        self.console = console
        self.show_in_console = show_in_console
        self.start_time: Optional[datetime] = None
    
    def __enter__(self) -> PerformanceTimer:
        """Enter the timing context and start the timer.
        
        Args:
            None
        
        Returns:
            PerformanceTimer: Self reference for context manager protocol.
        
        Raises:
            None: This method does not raise exceptions.
        
        Example:
            >>> with PerformanceTimer('operation', logger, console) as timer:
            ...     # timer is the same instance
            ...     pass
        """
        self.start_time = datetime.now()
        if self.show_in_console:
            if self.console and RICH_AVAILABLE:
                self.console.print(f"⏱️  Starting: [cyan]{self.operation_name}[/cyan]")
            else:
                print(f"⏱️  Starting: {self.operation_name}")
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the timing context and log the duration.
        
        Args:
            exc_type: Exception type if an exception occurred, None otherwise.
            exc_val: Exception value if an exception occurred, None otherwise.
            exc_tb: Exception traceback if an exception occurred, None otherwise.
        
        Returns:
            None
        
        Raises:
            None: This method does not raise exceptions.
        
        Note:
            Duration is always logged to file. Console output depends on
            show_in_console setting and Rich availability.
        """
        if not self.start_time:
            return
            
        duration_ms = (datetime.now() - self.start_time).total_seconds() * 1000
        
        # Always log to file
        self.logger.debug(f"Operation '{self.operation_name}' completed in {duration_ms:.2f}ms")
        
        # Console output
        if self.show_in_console:
            if self.console and RICH_AVAILABLE:
                color = "green" if duration_ms < 100 else "yellow" if duration_ms < 1000 else "red"
                self.console.print(
                    f"✅ Completed: [cyan]{self.operation_name}[/cyan] "
                    f"in [{color}]{duration_ms:.2f}ms[/{color}]"
                )
            else:
                print(f"✅ Completed: {self.operation_name} in {duration_ms:.2f}ms")


class GameLogger:
    """Thread-safe centralized logger with optional Rich integration.
    
    Implements singleton pattern to provide a unified logging interface across
    the entire application. Supports both file and console logging with Rich
    formatting when available. Automatically configures external library loggers
    to reduce console clutter while preserving file logs.
    
    Features:
        - Thread-safe singleton pattern
        - Rich console formatting (when available)
        - Rotating file logs with size limits
        - External library log management
        - Performance timing utilities
        - Configurable log levels and output
    
    Example:
        >>> logger = GameLogger()
        >>> game_log = logger.get_logger('game')
        >>> game_log.info('Game started')
    """
    
    _instance: Optional[GameLogger] = None
    _lock = threading.Lock()
    
    def __new__(cls) -> GameLogger:
        """Create or return the singleton instance.
        
        Args:
            None
            
        Returns:
            GameLogger: The singleton GameLogger instance.
            
        Raises:
            None: This method does not raise exceptions.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Initialize the GameLogger singleton.
        
        Args:
            None
            
        Returns:
            None
            
        Raises:
            None: This method does not raise exceptions.
            
        Note:
            Uses double-checked locking to ensure thread-safe initialization.
            Only initializes once even if called multiple times.
        """
        if hasattr(self, '_initialized'):
            return
        
        with self._lock:
            if hasattr(self, '_initialized'):
                return
            
            self._initialized = True
            self._loggers: Dict[str, logging.Logger] = {}
            self._handlers_added = False
            
            # Initialize components
            self._config = self._load_config()
            self.console = Console() if RICH_AVAILABLE else None
            
            # Setup logging system
            self._setup_rich_traceback()
            self._setup_base_logging()
    
    def _load_config(self) -> LoggerConfig:
        """Load configuration with proper error handling.
        
        Args:
            None
            
        Returns:
            LoggerConfig: Configuration container with loaded settings.
            
        Raises:
            None: Returns empty config on import errors.
        """
        try:
            from . import config
            return LoggerConfig(config)
        except ImportError:
            return LoggerConfig(None)
    
    def _setup_rich_traceback(self) -> None:
        """Setup rich traceback for better error display.
        
        Args:
            None
            
        Returns:
            None
            
        Raises:
            None: This method does not raise exceptions.
            
        Note:
            Only configures Rich traceback if Rich is available and console exists.
        """
        if RICH_AVAILABLE and self.console:
            install_rich_traceback(console=self.console, show_locals=True)
    
    def _setup_base_logging(self) -> None:
        """Setup base logging configuration with proper handler management.
        
        Args:
            None
            
        Returns:
            None
            
        Raises:
            OSError: If log directory cannot be created.
            
        Note:
            Configures both console and file handlers, and manages external loggers.
            Only runs once to prevent duplicate handlers.
        """
        if self._handlers_added:
            return
        
        log_dir_str = self._config.get('log_directory', 'logs', str)
        log_dir = Path(log_dir_str)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.handlers.clear()
        
        self._add_console_handler(root_logger)
        self._add_file_handler(root_logger, log_dir)
        self._configure_external_loggers()
        
        self._handlers_added = True
    
    def _add_console_handler(self, root_logger: logging.Logger) -> None:
        """Add console handler with appropriate configuration.
        
        Args:
            root_logger: Root logger instance to add handler to.
            
        Returns:
            None
            
        Raises:
            None: This method does not raise exceptions.
            
        Note:
            Uses RichHandler if available, otherwise falls back to StreamHandler.
        """
        console_level_str = self._config.get('console_debug_level', LoggingDefaults.CONSOLE_LEVEL, str)
        console_level = getattr(logging, console_level_str.upper(), logging.INFO)
        
        # Create handler based on Rich availability
        if RICH_AVAILABLE and self.console:
            handler = RichHandler(
                console=self.console,
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True
            )
        else:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
        
        handler.setLevel(console_level)
        root_logger.addHandler(handler)
    
    def _add_file_handler(self, root_logger: logging.Logger, log_dir: Path) -> None:
        """Add rotating file handler for persistent logging.
        
        Args:
            root_logger: Root logger instance to add handler to.
            log_dir: Directory path where log files will be stored.
            
        Returns:
            None
            
        Raises:
            OSError: If log file cannot be created or accessed.
            
        Note:
            Creates daily log files with rotation based on size limits.
        """
        log_file = log_dir / f"aigame_{datetime.now().strftime('%Y%m%d')}.log"
        
        handler = RotatingFileHandler(
            log_file,
            maxBytes=FileSettings.MAX_SIZE,
            backupCount=FileSettings.BACKUP_COUNT,
            encoding='utf-8'
        )
        
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        ))
        root_logger.addHandler(handler)
    
    def _configure_external_loggers(self) -> None:
        """Configure external library loggers to reduce console clutter.
        
        Args:
            None
            
        Returns:
            None
            
        Raises:
            None: This method does not raise exceptions.
            
        Note:
            Suppresses console output from external libraries while preserving
            file logging. Behavior controlled by show_litellm_console_logs config.
        """
        show_external_logs = self._config.get('show_litellm_console_logs', False, bool)
        
        for logger_name in ExternalLoggers.NAMES:
            logger = logging.getLogger(logger_name)
            
            if not show_external_logs:
                logger.setLevel(logging.WARNING)
                
                # Remove only console handlers, preserve file logging
                for handler in logger.handlers[:]:
                    if isinstance(handler, (logging.StreamHandler, RichHandler)):
                        if not isinstance(handler, RotatingFileHandler):
                            logger.removeHandler(handler)
                
                logger.propagate = True
    
    def _should_use_minimal_console(self) -> bool:
        """Check if minimal console mode is enabled.
        
        Args:
            None
            
        Returns:
            bool: True if minimal console mode is enabled, False otherwise.
            
        Raises:
            None: This method does not raise exceptions.
        """
        return self._config.get('console_minimal_mode', True, bool)
    
    def get_logger(self, name: str) -> logging.Logger:
        """Get or create a logger for a specific component.
        
        Args:
            name: Component name for the logger. Must be non-empty string.
                 Will be prefixed with 'aigame.' for namespacing.
        
        Returns:
            logging.Logger: Configured logger instance for the component.
        
        Raises:
            ValueError: If name is empty, None, or not a string.
        
        Example:
            >>> game_logger = GameLogger()
            >>> logger = game_logger.get_logger('ai_inference')
            >>> logger.info('AI request started')
        """
        if not name:
            raise ValueError(ErrorMessages.EMPTY_LOGGER_NAME.format())
        
        full_name = f"aigame.{name}"
        return self._loggers.setdefault(full_name, logging.getLogger(full_name))
    
    def set_level(self, level: str) -> None:
        """Set the logging level for all loggers and handlers.
        
        Args:
            level: Log level string. Must be one of: DEBUG, INFO, WARNING, 
                  ERROR, CRITICAL (case insensitive).
        
        Returns:
            None
        
        Raises:
            ValueError: If level is not a string or not a valid log level.
        
        Example:
            >>> game_logger = GameLogger()
            >>> game_logger.set_level('DEBUG')  # Enable debug output
            >>> game_logger.set_level('WARNING')  # Only warnings and above
        """
        if not isinstance(level, str):
            raise ValueError("Level must be a string")
        
        try:
            numeric_level = getattr(logging, level.upper())
        except AttributeError:
            raise ValueError(ErrorMessages.INVALID_LOG_LEVEL.format(level=level))
        
        root_logger = logging.getLogger()
        root_logger.setLevel(numeric_level)
        
        # Update all handlers
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                handler.setLevel(numeric_level)
    
    def performance_timer(self, operation_name: str, logger_name: str = "performance") -> PerformanceTimer:
        """Create a context manager for timing operations.
        
        Args:
            operation_name: Descriptive name for the operation being timed.
                           Must be non-empty string.
            logger_name: Name of the logger component to use for timing logs.
                        Defaults to "performance".
        
        Returns:
            PerformanceTimer: Context manager for timing the operation.
        
        Raises:
            ValueError: If operation_name is empty or None.
        
        Example:
            >>> game_logger = GameLogger()
            >>> with game_logger.performance_timer('Database query'):
            ...     # Your timed operation here
            ...     result = database.query()
        """
        if not operation_name:
            raise ValueError(ErrorMessages.EMPTY_OPERATION_NAME.format())
        
        show_timers = self._config.get('show_performance_timers', True, bool)
        return PerformanceTimer(operation_name, self.get_logger(logger_name), self.console, show_timers)


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific component.
    
    Args:
        name: Component name for the logger (e.g., 'ai_inference', 'game').
              Must be non-empty string. Will be prefixed with 'aigame.'.
        
    Returns:
        logging.Logger: Configured logger instance with file and console handlers.
        
    Raises:
        ValueError: If name is empty, None, or not a string.
        
    Example:
        >>> logger = get_logger('game_engine')
        >>> logger.info('Game started')
        >>> logger.debug('Debug information')
    """
    return _get_logger_instance().get_logger(name)


def set_log_level(level: str) -> None:
    """Set the global logging level.
    
    Args:
        level: Log level string. Must be one of: DEBUG, INFO, WARNING, 
              ERROR, CRITICAL (case insensitive).
        
    Returns:
        None
        
    Raises:
        ValueError: If level is not a string or not a valid log level.
        
    Example:
        >>> set_log_level('DEBUG')  # Enable debug output
        >>> set_log_level('INFO')   # Standard logging level
        >>> set_log_level('ERROR')  # Only errors and critical
    """
    _get_logger_instance().set_level(level)


def performance_timer(operation_name: str) -> PerformanceTimer:
    """Time an operation with clean output.
    
    Args:
        operation_name: Description of the operation being timed.
                       Must be non-empty string.
        
    Returns:
        PerformanceTimer: Context manager for timing the operation.
                         Logs to file and optionally displays in console.
        
    Raises:
        ValueError: If operation_name is empty or None.
        
    Example:
        >>> with performance_timer('Database query'):
        ...     result = database.execute_query()
        >>> with performance_timer('AI inference'):
        ...     response = ai_model.generate(prompt)
    """
    return _get_logger_instance().performance_timer(operation_name)


def game_event(event_type: str, details: Dict[str, Any]) -> None:
    """Log game events with structured data.
    
    Args:
        event_type: Type of game event (e.g., 'player_action', 'combat_start').
                   Must be non-empty string.
        details: Event details dictionary containing relevant information.
                Must be a dictionary with string keys.
        
    Returns:
        None
        
    Raises:
        ValueError: If event_type is empty/None or details is not a dictionary.
        
    Example:
        >>> game_event('player_levelup', {'player': 'Hero', 'new_level': 5})
        >>> game_event('combat_start', {'enemy': 'Dragon', 'location': 'Cave'})
        >>> game_event('item_found', {'item': 'Sword', 'rarity': 'Epic'})
    """
    if not event_type or not isinstance(details, dict):
        raise ValueError(ErrorMessages.INVALID_GAME_EVENT_PARAMS.format())
    
    get_logger("game").info(f"Game event: {event_type} - {details}")


def error_with_context(error: Exception, context: Dict[str, Any]) -> None:
    """Log errors with additional context.
    
    Args:
        error: Exception instance that occurred. Must be an Exception subclass.
        context: Additional context information as a dictionary.
                Must contain relevant debugging information.
        
    Returns:
        None
        
    Raises:
        ValueError: If error is not an Exception instance or context is not a dict.
        
    Example:
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     error_with_context(e, {'user_id': 123, 'operation': 'save_game'})
        >>> 
        >>> try:
        ...     ai_request()
        ... except APIError as e:
        ...     error_with_context(e, {'model': 'gpt-4', 'retry_count': 3})
    """
    if not isinstance(error, Exception) or not isinstance(context, dict):
        raise ValueError(ErrorMessages.INVALID_ERROR_CONTEXT_PARAMS.format())
    
    get_logger("error").error(f"Error: {error} | Context: {context}", exc_info=True)


def ai_request_debug(
    request_type: str, 
    messages: list, 
    params: dict, 
    logger_name: str = "ai_inference"
) -> None:
    """Log AI request debug information.
    
    Args:
        request_type: Type of AI request ('TEXT', 'JSON', etc.).
                     Must be non-empty string.
        messages: List of conversation messages for the AI request.
                 Each message should be a dictionary with 'role' and 'content'.
        params: Request parameters dictionary containing model settings.
               Must include at least 'model' key.
        logger_name: Name of the logger component to use.
                    Defaults to "ai_inference".
        
    Returns:
        None
        
    Raises:
        ValueError: If request_type is empty, messages is not a list, 
                   or params is not a dictionary.
        
    Example:
        >>> messages = [{'role': 'user', 'content': 'Hello'}]
        >>> params = {'model': 'gpt-4', 'temperature': 0.7}
        >>> ai_request_debug('TEXT', messages, params)
        >>> 
        >>> json_messages = [{'role': 'user', 'content': 'Generate JSON'}]
        >>> json_params = {'model': 'gpt-4', 'response_format': {'type': 'json_object'}}
        >>> ai_request_debug('JSON', json_messages, json_params)
    """
    if not request_type or not isinstance(messages, list) or not isinstance(params, dict):
        raise ValueError(ErrorMessages.INVALID_AI_DEBUG_PARAMS.format())
    
    logger = get_logger(logger_name)
    
    # Always log to file with full details
    logger.debug(f"AI {request_type} Request - Messages: {len(messages)}, Params: {params}")
    for i, msg in enumerate(messages, 1):
        logger.debug(f"Message {i}: {msg}")
    
    # Simple console output
    if _get_logger_instance()._should_use_minimal_console():
        model = params.get('model', 'unknown')
        logger.info(f"🤖 AI {request_type} request → {model} ({len(messages)} messages)")
    else:
        logger.debug(f"AI {request_type} Request - Messages: {len(messages)}, Params: {params}")


def ai_response_debug(
    request_type: str, 
    raw_response: str, 
    final_response: Any, 
    logger_name: str = "ai_inference"
) -> None:
    """Log AI response debug information.
    
    Args:
        request_type: Type of AI request ('TEXT', 'JSON', etc.).
                     Must be non-empty string.
        raw_response: Raw response string from the AI model.
                     Must be a string.
        final_response: Processed final response (parsed JSON, extracted text, etc.).
                       Can be any type depending on processing.
        logger_name: Name of the logger component to use.
                    Defaults to "ai_inference".
        
    Returns:
        None
        
    Raises:
        ValueError: If request_type is empty or raw_response is not a string.
        
    Example:
        >>> ai_response_debug('TEXT', 'Hello world', {'content': 'Hello world'})
        >>> 
        >>> json_raw = '{"name": "John", "age": 30}'
        >>> json_parsed = {"name": "John", "age": 30}
        >>> ai_response_debug('JSON', json_raw, json_parsed)
    """
    if not request_type or not isinstance(raw_response, str):
        raise ValueError(ErrorMessages.INVALID_AI_RESPONSE_PARAMS.format())
    
    logger = get_logger(logger_name)
    
    # Always log to file with full details
    logger.debug(f"AI {request_type} response - Raw length: {len(raw_response)}, Final type: {type(final_response)}")
    logger.debug(f"Raw response: {raw_response}")
    logger.debug(f"Final response: {final_response}")
    
    # Simple console output
    if _get_logger_instance()._should_use_minimal_console():
        preview = _get_response_preview(final_response)
        logger.info(f"✅ AI {request_type} response: {preview}")
    else:
        logger.debug(f"AI {request_type} Response - Raw: {_truncate_text(raw_response)}, "
                    f"Final: {_truncate_text(str(final_response))}")


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _get_logger_instance() -> GameLogger:
    """Get the singleton logger instance.
    
    Args:
        None
        
    Returns:
        GameLogger: The singleton GameLogger instance, creating it if needed.
        
    Raises:
        None: This function does not raise exceptions.
        
    Note:
        This function implements lazy initialization of the global logger instance.
        Thread-safe singleton pattern is handled by the GameLogger class itself.
    """
    global _game_logger
    return _game_logger or (_game_logger := GameLogger())


def _truncate_text(text: str, max_length: int = TextSettings.TRUNCATE_LENGTH) -> str:
    """Safely truncate text with ellipsis.
    
    Args:
        text: Text to truncate. Will be converted to string if not already.
        max_length: Maximum length before truncation. Defaults to 
                   TextSettings.TRUNCATE_LENGTH (100 characters).
        
    Returns:
        str: Truncated text with "..." suffix if truncation occurred,
             or original text if within length limit.
        
    Raises:
        None: This function does not raise exceptions.
        
    Example:
        >>> _truncate_text("Short text")
        'Short text'
        >>> _truncate_text("Very long text" * 10, 20)
        'Very long textVe...'
    """
    text = str(text) if not isinstance(text, str) else text
    return text[:max_length-3] + "..." if len(text) > max_length else text


def _get_response_preview(final_response: Any) -> str:
    """Get a preview of the response for minimal console output.
    
    Args:
        final_response: Response object to create preview from.
                       Can be dict with 'content' key or any other type.
        
    Returns:
        str: Preview string for console display. Either truncated content
             or generic "response received" message.
        
    Raises:
        None: This function does not raise exceptions.
        
    Example:
        >>> _get_response_preview({'content': 'Hello world'})
        'Hello world'
        >>> _get_response_preview({'data': 'some data'})
        'response received'
        >>> _get_response_preview("Plain text response")
        'response received'
    """
    return (_truncate_text(str(final_response['content']), TextSettings.CONTENT_PREVIEW_LENGTH)
            if isinstance(final_response, dict) and 'content' in final_response
            else "response received")


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================

# Module-level singleton instance
_game_logger: Optional[GameLogger] = None

# Graceful fallback for missing Rich library
if not RICH_AVAILABLE:
    warnings.warn(
        "Rich library not found. Logging will use standard Python logging without enhanced formatting. "
        "Install rich with: pip install rich",
        ImportWarning,
        stacklevel=2
    ) 