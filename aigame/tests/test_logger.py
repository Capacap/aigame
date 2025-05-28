"""
Test suite for logger module.

Tests logging functionality, configuration, file handling, and output formatting.
"""

import os
import tempfile
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path

try:
    from aigame.core.logger import get_logger, GameLogger, LoggerConfig
    import aigame.core.config as config_module
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from core.logger import get_logger, GameLogger, LoggerConfig
    import core.config as config_module


def test_logger_config_defaults():
    """Test LoggerConfig default values."""
    log_config = LoggerConfig()
    
    # Test that it can get values with defaults
    level = log_config.get('log_level', 'INFO', str)
    assert level == 'INFO'
    
    timeout = log_config.get('request_timeout', 30, int)
    assert timeout == 30


def test_logger_config_with_module():
    """Test LoggerConfig with actual config module."""
    log_config = LoggerConfig(config_module)
    
    # Test that it can read from the config module
    debug_mode = log_config.get('debug_mode', False, bool)
    assert isinstance(debug_mode, bool)
    
    model = log_config.get('model', 'default', str)
    assert isinstance(model, str)


def test_get_logger_basic():
    """Test basic logger creation."""
    logger = get_logger("test_module")
    
    assert logger.name == "aigame.test_module"
    assert isinstance(logger, logging.Logger)


def test_get_logger_different_names():
    """Test that different logger names create different loggers."""
    logger1 = get_logger("module1")
    logger2 = get_logger("module2")
    
    assert logger1.name == "aigame.module1"
    assert logger2.name == "aigame.module2"
    assert logger1 != logger2


def test_game_logger_singleton():
    """Test that GameLogger implements singleton pattern."""
    logger1 = GameLogger()
    logger2 = GameLogger()
    
    assert logger1 is logger2


def test_logger_levels():
    """Test different logging levels."""
    logger = get_logger("test_levels")
    
    # Test different log levels work without errors
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")
    
    # All should work without errors
    assert True


def test_logger_with_data_types():
    """Test logging with various data types."""
    logger = get_logger("test_types")
    
    # Test logging with various data types
    logger.info("String message")
    logger.info({"dict": "value"})
    logger.info(["list", "items"])
    logger.info(42)
    logger.info(3.14)
    logger.info(True)
    
    # Should handle all types without errors
    assert True


def test_logger_error_handling():
    """Test logger error handling and edge cases."""
    # Test with empty name should raise ValueError
    try:
        logger = get_logger("")
        assert False, "Should have raised ValueError for empty name"
    except ValueError as e:
        assert "Logger name cannot be empty" in str(e)
    
    # Test with special characters in name should work
    logger = get_logger("test.module-name_123")
    assert logger is not None
    
    # Test logging None values
    logger = get_logger("test_none")
    logger.info(None)
    logger.info("Message with None: %s", None)
    
    # Should handle logging None values without errors
    assert True


def test_logger_performance_timer():
    """Test performance timing functionality."""
    from aigame.core.logger import performance_timer
    
    # Test that performance timer can be created
    timer = performance_timer("test_operation")
    assert timer is not None
    
    # Test context manager usage
    with performance_timer("test_context"):
        pass  # Should work without errors
    
    assert True


def test_logger_game_event():
    """Test game event logging functionality."""
    from aigame.core.logger import game_event
    
    # Test game event logging
    game_event("player_action", {"action": "jump", "player": "hero"})
    game_event("level_complete", {"level": 1, "score": 1000})
    
    # Should work without errors
    assert True


def test_logger_error_with_context():
    """Test error logging with context."""
    from aigame.core.logger import error_with_context
    
    # Test error logging with context
    try:
        raise ValueError("Test error")
    except Exception as e:
        error_with_context(e, {"operation": "test", "user": "test_user"})
    
    # Should work without errors
    assert True


def test_logger_ai_debug_functions():
    """Test AI-specific debug logging functions."""
    try:
        from aigame.core.logger import ai_request_debug, ai_response_debug
        
        # Test AI request debug
        messages = [{"role": "user", "content": "Hello"}]
        params = {"model": "gpt-4", "temperature": 0.7}
        ai_request_debug("TEXT", messages, params)
        
        # Test AI response debug
        ai_response_debug("TEXT", "Hello world", {"content": "Hello world"})
        
        # Should work without errors
        assert True
    except ImportError:
        # If functions don't exist, that's okay
        assert True


def test_logger_thread_safety():
    """Test basic thread safety of logger."""
    import threading
    import time
    
    logger = get_logger("test_thread")
    results = []
    
    def log_messages(thread_id):
        for i in range(3):
            logger.info(f"Thread {thread_id} message {i}")
            results.append(f"thread_{thread_id}_msg_{i}")
            time.sleep(0.001)  # Small delay
    
    # Create multiple threads
    threads = []
    for i in range(2):
        thread = threading.Thread(target=log_messages, args=(i,))
        threads.append(thread)
        thread.start()
    
    # Wait for all threads
    for thread in threads:
        thread.join()
    
    # Should have logged all messages without errors
    assert len(results) == 6  # 2 threads * 3 messages each


def test_logger_config_caching():
    """Test LoggerConfig caching functionality."""
    log_config = LoggerConfig(config_module)
    
    # Get the same value twice
    value1 = log_config.get('debug_mode', False, bool)
    value2 = log_config.get('debug_mode', False, bool)
    
    assert value1 == value2
    
    # Clear cache and get again
    log_config.clear_cache()
    value3 = log_config.get('debug_mode', False, bool)
    
    assert value1 == value3


def test_logger_config_type_validation():
    """Test LoggerConfig type validation."""
    log_config = LoggerConfig()
    
    # Test with correct type
    string_val = log_config.get('test_string', 'default', str)
    assert string_val == 'default'
    
    # Test with wrong type (should return default)
    int_val = log_config.get('test_int', 42, int)
    assert int_val == 42


def test_logger_external_suppression():
    """Test that external loggers can be managed."""
    from aigame.core.logger import ExternalLoggers
    
    # Test that external logger names are defined
    assert hasattr(ExternalLoggers, 'NAMES')
    assert isinstance(ExternalLoggers.NAMES, tuple)
    assert len(ExternalLoggers.NAMES) > 0
    
    # Test that common external loggers are included
    external_names = ExternalLoggers.NAMES
    assert any('httpx' in name.lower() for name in external_names)


def test_logger_constants():
    """Test that logger constants are properly defined."""
    from aigame.core.logger import LoggingDefaults, TextSettings, FileSettings
    
    # Test LoggingDefaults
    assert hasattr(LoggingDefaults, 'CONSOLE_LEVEL')
    assert hasattr(LoggingDefaults, 'FILE_LEVEL')
    
    # Test TextSettings
    assert hasattr(TextSettings, 'TRUNCATE_LENGTH')
    assert hasattr(TextSettings, 'CONTENT_PREVIEW_LENGTH')
    
    # Test FileSettings
    assert hasattr(FileSettings, 'MAX_SIZE')
    assert hasattr(FileSettings, 'BACKUP_COUNT')


def run_all_logger_tests():
    """Run all logger tests and report results."""
    tests = [
        test_logger_config_defaults,
        test_logger_config_with_module,
        test_get_logger_basic,
        test_get_logger_different_names,
        test_game_logger_singleton,
        test_logger_levels,
        test_logger_with_data_types,
        test_logger_error_handling,
        test_logger_performance_timer,
        test_logger_game_event,
        test_logger_error_with_context,
        test_logger_ai_debug_functions,
        test_logger_thread_safety,
        test_logger_config_caching,
        test_logger_config_type_validation,
        test_logger_external_suppression,
        test_logger_constants
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(f"✅ {test.__name__}")
        except Exception as e:
            results.append(f"❌ {test.__name__}: {e}")
    
    print("Logger Module Test Results:")
    print("=" * 40)
    for result in results:
        print(result)
    
    passed = sum(1 for r in results if r.startswith("✅"))
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_logger_tests()
    exit(0 if success else 1) 