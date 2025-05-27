"""
AI Game Project

A comprehensive AI-powered game development framework with advanced
inference capabilities, logging, and modular architecture.

Quick Start:
    from aigame import generate_text_response
    
    response = generate_text_response(
        messages=[{"role": "user", "content": "Hello, AI!"}],
        config=your_config
    )

Modules:
    - core: Core AI inference and logging functionality
    - tests: Comprehensive test suite
    - data: Game data and assets
"""

# Import the most commonly used functions for convenience
from .core import (
    generate_text_response,
    generate_json_response,
    get_logger
)

# Package metadata
__version__ = '1.0.0'
__author__ = 'AI Game Project'
__description__ = 'AI-powered game development framework'

# Define public API for top-level imports
__all__ = [
    'generate_text_response',
    'generate_json_response', 
    'get_logger',
] 