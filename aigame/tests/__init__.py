"""
Test suite for the AI Game project.

This package contains comprehensive tests for all modules in the aigame project.
Tests are organized by functionality and include both unit and integration tests.

Test Modules:
    - test_config.py: Configuration loading and validation tests
    - test_logger.py: Logging functionality and output tests  
    - test_ai_inference.py: AI inference and API interaction tests
    - test_main.py: Main script and demo functionality tests
    - test_package.py: Package structure and import tests
    - test_runner.py: Comprehensive test runner with reporting

Run all tests:
    python aigame/tests/test_runner.py
    python -m aigame.tests.test_runner

Run specific test modules:
    python aigame/tests/test_config.py
    python aigame/tests/test_logger.py
    python aigame/tests/test_ai_inference.py
    python aigame/tests/test_main.py
    python aigame/tests/test_package.py

Run with different modes:
    python aigame/tests/test_runner.py --mode unit        # Unit tests only
    python aigame/tests/test_runner.py --mode integration # Integration tests only
    python aigame/tests/test_runner.py --mode quick       # Quick tests only
    python aigame/tests/test_runner.py --mode all         # All tests (default)

Test categories:
    - Unit tests: Fast, isolated tests for individual functions
    - Integration tests: Tests with real API calls (require API key)
    - Package tests: Import and structure validation
    - Configuration tests: Config loading and validation
    - Logger tests: Logging functionality and output
    - Main script tests: Demo workflow validation

Requirements:
    - Unit tests: No external dependencies
    - Integration tests: Require OPENAI_API_KEY environment variable
""" 

# Import test runner for convenience
from .test_runner import TestRunner, main as run_tests

__all__ = ['TestRunner', 'run_tests'] 