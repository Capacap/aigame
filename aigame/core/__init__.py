"""
AI Game Core Package

This package contains the core functionality for the AI Game project,
including AI inference, logging, and configuration management.

Public API:
    - generate_text_response: Generate text responses from AI models
    - generate_json_response: Generate structured JSON responses from AI models
    - get_logger: Get a configured logger instance
    - ai_request_debug: Log AI request details
    - ai_response_debug: Log AI response details
    - performance_timer: Context manager for performance timing

Example:
    from aigame.core import generate_text_response, get_logger
    
    logger = get_logger(__name__)
    response = generate_text_response(
        messages=[{"role": "user", "content": "Hello"}],
        config=my_config
    )
"""

# Import main AI inference functions
from .ai_inference import (
    generate_text_response,
    generate_json_response,
    DEFAULT_TEMPERATURE_TEXT,
    DEFAULT_TEMPERATURE_JSON
)

# Import logging utilities
from .logger import (
    get_logger,
    ai_request_debug,
    ai_response_debug,
    performance_timer
)

# Define what gets imported with "from aigame.core import *"
__all__ = [
    # AI Inference
    'generate_text_response',
    'generate_json_response',
    'DEFAULT_TEMPERATURE_TEXT',
    'DEFAULT_TEMPERATURE_JSON',
    
    # Logging
    'get_logger',
    'ai_request_debug',
    'ai_response_debug',
    'performance_timer',
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'AI Game Project'
__description__ = 'Core AI functionality for the AI Game project' 