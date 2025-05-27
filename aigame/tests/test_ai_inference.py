"""
Comprehensive test suite for AI inference module.

This module contains unit tests, integration tests, and test infrastructure
for the AI inference functionality. Tests cover validation, functionality,
error handling, retry logic, and reasoning extraction.

Run tests with:
    python -m pytest aigame/tests/
    python aigame/tests/test_ai_inference.py
"""

import os
import time
from unittest.mock import patch, MagicMock
from dataclasses import dataclass
from typing import List, Dict, Any

# Import the module under test
AI_INFERENCE_MODULE_PATH = None
try:
    from aigame.core.ai_inference import (
        generate_text_response, 
        generate_json_response,
        DEFAULT_TEMPERATURE_TEXT,
        DEFAULT_TEMPERATURE_JSON
    )
    AI_INFERENCE_MODULE_PATH = 'aigame.core.ai_inference'
except ImportError:
    # Fallback for direct execution - add parent directory to path
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from core.ai_inference import (
        generate_text_response, 
        generate_json_response,
        DEFAULT_TEMPERATURE_TEXT,
        DEFAULT_TEMPERATURE_JSON
    )
    AI_INFERENCE_MODULE_PATH = 'core.ai_inference'


# ============================================================================
# TEST CONFIGURATION AND INFRASTRUCTURE
# ============================================================================

@dataclass
class TestConfig:
    """Test configuration with safe defaults for unit testing."""
    debug_mode: bool = False
    model: str = "gpt-4o-mini"
    api_key: str = "test-key"
    api_base: str = None
    api_version: str = None
    request_timeout: int = 30
    force_ipv4: bool = False
    max_retries: int = 1  # Fast tests
    retry_delay: float = 0.1  # Fast tests
    default_temperature_text: float = None
    default_temperature_json: float = None
    default_max_tokens: int = None


def create_test_config(**overrides) -> TestConfig:
    """Create test configuration with optional parameter overrides.
    
    Args:
        **overrides: Configuration attributes to override from defaults
        
    Returns:
        TestConfig: Test configuration object with applied overrides
    """
    config = TestConfig()
    for key, value in overrides.items():
        setattr(config, key, value)
    return config


def mock_completion_response(content: str) -> MagicMock:
    """Create mock LiteLLM response object with specified content.
    
    Args:
        content: Response content to include in the mock
        
    Returns:
        MagicMock: Mock response object matching LiteLLM structure
    """
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = content
    return mock_response


class TestResult:
    """Track test execution results with pass/fail status and error details."""
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.details = None
    
    def success(self, details: str = None):
        self.passed = True
        self.details = details
        
    def failure(self, error: str):
        self.passed = False
        self.error = error


def run_test(test_func) -> TestResult:
    """Execute test function and capture results safely.
    
    Args:
        test_func: Test function to execute (should raise AssertionError on failure)
        
    Returns:
        TestResult: Object containing test execution results and error details
    """
    result = TestResult(test_func.__name__)
    try:
        test_func()
        result.success()
    except Exception as e:
        result.failure(str(e))
    return result


# ============================================================================
# VALIDATION TESTS
# ============================================================================

def test_empty_user_message_validation():
    """Test that empty user messages are rejected."""
    config = create_test_config()
    try:
        generate_text_response([], config)
        raise AssertionError("Should have raised ValueError for empty message list")
    except ValueError as e:
        if "non-empty list" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")


def test_temperature_validation():
    """Test temperature parameter validation."""
    config = create_test_config()
    
    # Test invalid temperature (too high)
    try:
        generate_text_response([{"role": "user", "content": "test"}], config, temperature=3.0)
        raise AssertionError("Should have raised ValueError for temperature > 2.0")
    except ValueError as e:
        if "temperature must be between" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")
    
    # Test invalid temperature (negative)
    try:
        generate_text_response([{"role": "user", "content": "test"}], config, temperature=-1.0)
        raise AssertionError("Should have raised ValueError for negative temperature")
    except ValueError as e:
        if "temperature must be between" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")


def test_json_word_requirement():
    """Test that JSON requests require 'json' in messages."""
    config = create_test_config()
    
    # Test missing 'json' word
    try:
        generate_json_response([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Generate a character"}
        ], config)
        raise AssertionError("Should have raised ValueError for missing 'json'")
    except ValueError as e:
        if "must contain the word 'json'" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")
    
    # Test 'jsonify' should not work (word boundary)
    try:
        generate_json_response([
            {"role": "user", "content": "Use jsonify method"}
        ], config)
        raise AssertionError("Should have raised ValueError for 'jsonify' (not 'json')")
    except ValueError as e:
        if "must contain the word 'json'" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")


def test_message_structure_validation():
    """Test validation of message structure and content."""
    config = create_test_config()
    
    # Test non-dict message
    try:
        generate_text_response(["invalid message"], config)
        raise AssertionError("Should have raised ValueError for non-dict message")
    except ValueError as e:
        if "must be a dictionary" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")
    
    # Test missing role key
    try:
        generate_text_response([{"content": "test"}], config)
        raise AssertionError("Should have raised ValueError for missing role")
    except ValueError as e:
        if "missing required keys" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")
    
    # Test empty content
    try:
        generate_text_response([{"role": "user", "content": "   "}], config)
        raise AssertionError("Should have raised ValueError for empty content")
    except ValueError as e:
        if "content must be non-empty" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")


def test_repetition_penalty_validation():
    """Test repetition penalty parameter validation."""
    config = create_test_config()
    
    # Test invalid repetition penalty (zero)
    try:
        generate_text_response([{"role": "user", "content": "test"}], config, repetition_penalty=0.0)
        raise AssertionError("Should have raised ValueError for repetition_penalty = 0.0")
    except ValueError as e:
        if "repetition_penalty must be greater than" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")
    
    # Test invalid repetition penalty (negative)
    try:
        generate_text_response([{"role": "user", "content": "test"}], config, repetition_penalty=-0.5)
        raise AssertionError("Should have raised ValueError for negative repetition_penalty")
    except ValueError as e:
        if "repetition_penalty must be greater than" not in str(e):
            raise AssertionError(f"Wrong error message: {e}")


# ============================================================================
# FUNCTIONAL TESTS
# ============================================================================

def test_basic_text_generation():
    """Test basic text generation with mocked response."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("Hello, world!")
        
        result = generate_text_response([{"role": "user", "content": "Say hello"}], config)
        
        if not isinstance(result, dict):
            raise AssertionError(f"Expected dict response, got {type(result)}")
        if 'reasoning' not in result or 'content' not in result:
            raise AssertionError(f"Missing keys in response: {result.keys()}")
        if result['content'] != "Hello, world!":
            raise AssertionError(f"Expected 'Hello, world!', got '{result['content']}'")
        if result['reasoning'] is not None:
            raise AssertionError(f"Expected no reasoning, got: {result['reasoning']}")
        
        # Verify API was called correctly
        mock_completion.assert_called_once()
        call_args = mock_completion.call_args[1]
        if call_args['model'] != 'gpt-4o-mini':
            raise AssertionError(f"Wrong model: {call_args['model']}")
        if len(call_args['messages']) != 1:
            raise AssertionError(f"Wrong message count: {len(call_args['messages'])}")
        if call_args['messages'][0]['content'] != 'Say hello':
            raise AssertionError(f"Wrong message content: {call_args['messages'][0]['content']}")


def test_system_message_inclusion():
    """Test that system messages are properly included."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("Greetings, adventurer!")
        
        result = generate_text_response([
            {"role": "system", "content": "You are a wizard"},
            {"role": "user", "content": "Hello"}
        ], config)
        
        if result['content'] != "Greetings, adventurer!":
            raise AssertionError(f"Expected 'Greetings, adventurer!', got '{result['content']}'")
        
        # Verify system message was included
        call_args = mock_completion.call_args[1]
        messages = call_args['messages']
        if len(messages) != 2:
            raise AssertionError(f"Expected 2 messages, got {len(messages)}")
        if messages[0]['role'] != 'system':
            raise AssertionError(f"First message should be system, got {messages[0]['role']}")
        if messages[0]['content'] != 'You are a wizard':
            raise AssertionError(f"Wrong system content: {messages[0]['content']}")


def test_assistant_prefix_combination():
    """Test multi-turn conversation with assistant messages."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("wanted to get to the other side!")
        
        result = generate_text_response([
            {"role": "user", "content": "Why did the chicken cross the road?"},
            {"role": "assistant", "content": "Because it "}
        ], config)
        
        # The AI should complete the response naturally
        expected = "wanted to get to the other side!"
        if result['content'] != expected:
            raise AssertionError(f"Expected '{expected}', got '{result['content']}'")
        
        # Verify the conversation history was passed correctly
        call_args = mock_completion.call_args[1]
        messages = call_args['messages']
        if len(messages) != 2:
            raise AssertionError(f"Expected 2 messages, got {len(messages)}")
        if messages[1]['role'] != 'assistant':
            raise AssertionError(f"Second message should be assistant, got {messages[1]['role']}")
        if messages[1]['content'] != 'Because it ':
            raise AssertionError(f"Wrong assistant content: {messages[1]['content']}")


def test_json_generation_with_valid_prompt():
    """Test JSON generation with valid 'json' in prompt."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response('{"name": "Test", "level": 1}')
        
        result = generate_json_response([
            {"role": "user", "content": "Generate character in JSON format"}
        ], config)
        
        expected = {"name": "Test", "level": 1}
        if not isinstance(result, dict):
            raise AssertionError(f"Expected dict response, got {type(result)}")
        if 'reasoning' not in result or 'content' not in result:
            raise AssertionError(f"Missing keys in response: {result.keys()}")
        if result['content'] != expected:
            raise AssertionError(f"Expected {expected}, got {result['content']}")
        if result['reasoning'] is not None:
            raise AssertionError(f"Expected no reasoning, got: {result['reasoning']}")
        
        # Verify JSON response format was set
        call_args = mock_completion.call_args[1]
        if 'response_format' not in call_args:
            raise AssertionError("response_format not set")
        if call_args['response_format'] != {"type": "json_object"}:
            raise AssertionError(f"Wrong response_format: {call_args['response_format']}")


def test_json_prefix_handling():
    """Test multi-turn JSON conversation with assistant messages."""
    config = create_test_config(debug_mode=False)  # Disable debug to avoid print output
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        # Test: AI completes a JSON object in conversation
        mock_completion.return_value = mock_completion_response('{"name": "Aragorn", "class": "Ranger", "level": 10}')
        
        result = generate_json_response([
            {"role": "system", "content": "Complete the JSON object."},
            {"role": "user", "content": "Add level field with value 10 to this character"},
            {"role": "assistant", "content": '{"name": "Aragorn", "class": "Ranger"'}
        ], config)
        
        expected = {"name": "Aragorn", "class": "Ranger", "level": 10}
        if result['content'] != expected:
            raise AssertionError(f"Expected {expected}, got {result['content']}")
        
        # Verify the conversation history was passed correctly
        call_args = mock_completion.call_args[1]
        messages = call_args['messages']
        if len(messages) != 3:
            raise AssertionError(f"Expected 3 messages, got {len(messages)}")
        if messages[2]['role'] != 'assistant':
            raise AssertionError(f"Third message should be assistant, got {messages[2]['role']}")
        if '"name": "Aragorn"' not in messages[2]['content']:
            raise AssertionError(f"Wrong assistant content: {messages[2]['content']}")


def test_temperature_defaults():
    """Test that temperature defaults work correctly."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        # Test text default temperature
        mock_completion.return_value = mock_completion_response("test")
        generate_text_response([{"role": "user", "content": "test"}], config)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != DEFAULT_TEMPERATURE_TEXT:
            raise AssertionError(f"Wrong text temperature: {call_args['temperature']}")
        
        # Test JSON default temperature
        mock_completion.return_value = mock_completion_response('{"result": "test"}')
        generate_json_response([{"role": "user", "content": "test json"}], config)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != DEFAULT_TEMPERATURE_JSON:
            raise AssertionError(f"Wrong JSON temperature: {call_args['temperature']}")


def test_custom_temperature_override():
    """Test that custom temperature values override defaults."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("test")
        
        # Test custom temperature for text
        generate_text_response([{"role": "user", "content": "test"}], config, temperature=1.2)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != 1.2:
            raise AssertionError(f"Expected temperature 1.2, got {call_args['temperature']}")
        
        # Test custom temperature for JSON
        mock_completion.return_value = mock_completion_response('{"result": "test"}')
        generate_json_response([{"role": "user", "content": "test json"}], config, temperature=0.8)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != 0.8:
            raise AssertionError(f"Expected temperature 0.8, got {call_args['temperature']}")


def test_max_tokens_parameter():
    """Test max_tokens parameter handling."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("test")
        
        # Test custom max_tokens
        generate_text_response([{"role": "user", "content": "test"}], config, max_tokens=500)
        call_args = mock_completion.call_args[1]
        if call_args['max_tokens'] != 500:
            raise AssertionError(f"Expected max_tokens 500, got {call_args['max_tokens']}")


def test_repetition_penalty_parameter():
    """Test repetition_penalty parameter handling."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("test")
        
        # Test repetition penalty
        generate_text_response([{"role": "user", "content": "test"}], config, repetition_penalty=1.1)
        call_args = mock_completion.call_args[1]
        if call_args['repetition_penalty'] != 1.1:
            raise AssertionError(f"Expected repetition_penalty 1.1, got {call_args['repetition_penalty']}")


# ============================================================================
# ERROR HANDLING AND RETRY TESTS
# ============================================================================

def test_retry_logic():
    """Test retry logic with failures."""
    config = create_test_config(max_retries=2)
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        # First two calls fail, third succeeds
        mock_completion.side_effect = [
            Exception("Network error"),
            Exception("Rate limit"),
            mock_completion_response("Success!")
        ]
        
        result = generate_text_response([{"role": "user", "content": "test"}], config)
        
        if result['content'] != "Success!":
            raise AssertionError(f"Expected 'Success!', got '{result['content']}'")
        if mock_completion.call_count != 3:
            raise AssertionError(f"Expected 3 calls, got {mock_completion.call_count}")


def test_retry_exhaustion():
    """Test that retry exhaustion raises proper error."""
    config = create_test_config(max_retries=1)
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.side_effect = Exception("Persistent error")
        
        try:
            generate_text_response([{"role": "user", "content": "test"}], config)
            raise AssertionError("Should have raised RuntimeError after retries exhausted")
        except RuntimeError as e:
            if "failed after 2 attempts" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")


def test_invalid_json_response():
    """Test handling of invalid JSON responses."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response('{"invalid": json}')
        
        try:
            generate_json_response([{"role": "user", "content": "Generate JSON"}], config)
            raise AssertionError("Should have raised RuntimeError for invalid JSON after retries")
        except RuntimeError as e:
            if "failed after" not in str(e) or "invalid JSON" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")


def test_empty_response_handling():
    """Test handling of empty responses from AI service."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        # Mock empty response
        mock_response = MagicMock()
        mock_response.choices = []
        mock_completion.return_value = mock_response
        
        try:
            generate_text_response([{"role": "user", "content": "test"}], config)
            raise AssertionError("Should have raised RuntimeError for empty response after retries")
        except RuntimeError as e:
            if "failed after" not in str(e) or "Empty or invalid response" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")


# ============================================================================
# REASONING EXTRACTION TESTS
# ============================================================================

def test_reasoning_extraction():
    """Test reasoning extraction from AI responses."""
    config = create_test_config()
    
    # Test with <think> tags
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response(
            "<think>I need to consider the user's request carefully. This seems like a greeting.</think>Hello! How can I help you today?"
        )
        
        result = generate_text_response([{"role": "user", "content": "Hello"}], config)
        
        if not isinstance(result, dict):
            raise AssertionError(f"Expected dict response, got {type(result)}")
        if 'reasoning' not in result or 'content' not in result:
            raise AssertionError(f"Missing keys in response: {result.keys()}")
        if result['reasoning'] is None:
            raise AssertionError("Expected reasoning to be extracted")
        if "consider the user's request" not in result['reasoning']:
            raise AssertionError(f"Reasoning content incorrect: {result['reasoning']}")
        if result['content'] != "Hello! How can I help you today?":
            raise AssertionError(f"Content incorrect: {result['content']}")


def test_reasoning_extraction_multiple_tags():
    """Test reasoning extraction with multiple reasoning sections."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response(
            "<thinking>First, I should understand what they want.</thinking>I understand your question. <analysis>This requires a detailed response.</analysis>Here's my answer."
        )
        
        result = generate_text_response([{"role": "user", "content": "Explain something"}], config)
        
        if result['reasoning'] is None:
            raise AssertionError("Expected reasoning to be extracted")
        if "First, I should understand" not in result['reasoning']:
            raise AssertionError("Missing first reasoning section")
        if "This requires a detailed response" not in result['reasoning']:
            raise AssertionError("Missing second reasoning section")
        if result['content'] != "I understand your question. Here's my answer.":
            raise AssertionError(f"Content incorrect: {result['content']}")


def test_reasoning_extraction_no_reasoning():
    """Test reasoning extraction when no reasoning tags are present."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("Just a simple response without reasoning.")
        
        result = generate_text_response([{"role": "user", "content": "Simple question"}], config)
        
        if result['reasoning'] is not None:
            raise AssertionError(f"Expected no reasoning, got: {result['reasoning']}")
        if result['content'] != "Just a simple response without reasoning.":
            raise AssertionError(f"Content incorrect: {result['content']}")


def test_json_reasoning_extraction():
    """Test reasoning extraction with JSON responses."""
    config = create_test_config()
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response(
            '<reason>I need to create a character with the specified attributes.</reason>{"name": "Test Character", "level": 5}'
        )
        
        result = generate_json_response([
            {"role": "system", "content": "Respond with valid JSON only."},
            {"role": "user", "content": "Create a character in JSON format"}
        ], config)
        
        if result['reasoning'] is None:
            raise AssertionError("Expected reasoning to be extracted")
        if "create a character" not in result['reasoning'].lower():
            raise AssertionError(f"Reasoning content incorrect: {result['reasoning']}")
        if not isinstance(result['content'], dict):
            raise AssertionError(f"Expected dict content, got {type(result['content'])}")
        if result['content']['name'] != "Test Character":
            raise AssertionError(f"JSON content incorrect: {result['content']}")


def test_reasoning_patterns():
    """Test all supported reasoning tag patterns."""
    config = create_test_config()
    
    patterns = [
        ("<think>Thinking content</think>Response", "Thinking content"),
        ("<thinking>Thinking content</thinking>Response", "Thinking content"),
        ("<reason>Reason content</reason>Response", "Reason content"),
        ("<reasoning>Reasoning content</reasoning>Response", "Reasoning content"),
        ("<analysis>Analysis content</analysis>Response", "Analysis content"),
    ]
    
    for response_text, expected_reasoning in patterns:
        with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response(response_text)
            
            result = generate_text_response([{"role": "user", "content": "test"}], config)
            
            if result['reasoning'] != expected_reasoning:
                raise AssertionError(f"Expected reasoning '{expected_reasoning}', got '{result['reasoning']}'")
            if result['content'] != "Response":
                raise AssertionError(f"Expected content 'Response', got '{result['content']}'")


# ============================================================================
# CONFIGURATION TESTS
# ============================================================================

def test_config_overrides():
    """Test configuration parameter overrides."""
    config = create_test_config(
        default_temperature_text=0.9,
        default_temperature_json=0.1,
        default_max_tokens=2000
    )
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("test")
        
        # Test text temperature override
        generate_text_response([{"role": "user", "content": "test"}], config)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != 0.9:
            raise AssertionError(f"Expected temperature 0.9, got {call_args['temperature']}")
        if call_args['max_tokens'] != 2000:
            raise AssertionError(f"Expected max_tokens 2000, got {call_args['max_tokens']}")
        
        # Test JSON temperature override
        mock_completion.return_value = mock_completion_response('{"test": "value"}')
        generate_json_response([{"role": "user", "content": "test json"}], config)
        call_args = mock_completion.call_args[1]
        if call_args['temperature'] != 0.1:
            raise AssertionError(f"Expected temperature 0.1, got {call_args['temperature']}")


def test_api_configuration():
    """Test API configuration parameters."""
    config = create_test_config(
        api_base="https://custom.api.com",
        api_version="v2",
        force_ipv4=True
    )
    
    with patch(f'{AI_INFERENCE_MODULE_PATH}.completion') as mock_completion:
        mock_completion.return_value = mock_completion_response("test")
        
        generate_text_response([{"role": "user", "content": "test"}], config)
        call_args = mock_completion.call_args[1]
        
        if call_args['api_base'] != "https://custom.api.com":
            raise AssertionError(f"Wrong api_base: {call_args['api_base']}")
        if call_args['api_version'] != "v2":
            raise AssertionError(f"Wrong api_version: {call_args['api_version']}")
        if not call_args['force_ipv4']:
            raise AssertionError("force_ipv4 should be True")


# ============================================================================
# TEST RUNNER
# ============================================================================

def run_all_tests():
    """Execute all unit tests and display comprehensive results summary.
    
    Returns:
        bool: True if all tests passed, False if any failed
    """
    test_functions = [
        # Validation tests
        test_empty_user_message_validation,
        test_temperature_validation,
        test_json_word_requirement,
        test_message_structure_validation,
        test_repetition_penalty_validation,
        
        # Functional tests
        test_basic_text_generation,
        test_system_message_inclusion,
        test_assistant_prefix_combination,
        test_json_generation_with_valid_prompt,
        test_json_prefix_handling,
        test_temperature_defaults,
        test_custom_temperature_override,
        test_max_tokens_parameter,
        test_repetition_penalty_parameter,
        
        # Error handling tests
        test_retry_logic,
        test_retry_exhaustion,
        test_invalid_json_response,
        test_empty_response_handling,
        
        # Reasoning extraction tests
        test_reasoning_extraction,
        test_reasoning_extraction_multiple_tags,
        test_reasoning_extraction_no_reasoning,
        test_json_reasoning_extraction,
        test_reasoning_patterns,
        
        # Configuration tests
        test_config_overrides,
        test_api_configuration,
    ]
    
    print("=" * 60)
    print("Running AI Inference Unit Tests")
    print("=" * 60)
    
    results = []
    for test_func in test_functions:
        print(f"Running {test_func.__name__}...", end=" ")
        result = run_test(test_func)
        results.append(result)
        
        if result.passed:
            print("✓ PASS")
        else:
            print("✗ FAIL")
            print(f"  Error: {result.error}")
    
    # Summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print("\n" + "=" * 60)
    print(f"Unit Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All unit tests passed!")
    else:
        print("⚠️  Some unit tests failed:")
        for result in results:
            if not result.passed:
                print(f"  - {result.name}: {result.error}")
    
    print("=" * 60)
    return passed == total


# ============================================================================
# INTEGRATION TESTS (Real API)
# ============================================================================

def run_integration_tests():
    """Execute integration tests with real AI API calls (requires API key).
    
    Set environment variable RUN_INTEGRATION_TESTS=1 to enable.
    Requires valid API key in environment or config file.
    These tests make actual API calls and may incur costs.
    
    Returns:
        bool: True if all integration tests passed, False if any failed or skipped
    """
    if not os.getenv('RUN_INTEGRATION_TESTS'):
        print("\n" + "=" * 60)
        print("Integration Tests Skipped")
        print("=" * 60)
        print("To run integration tests with real API calls:")
        print("  export RUN_INTEGRATION_TESTS=1")
        print("  export OPENAI_API_KEY=your_real_key")
        print("  python aigame/tests/test_ai_inference.py")
        print("=" * 60)
        return True
    
    # Try to get real API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n" + "=" * 60)
        print("Integration Tests Failed")
        print("=" * 60)
        print("OPENAI_API_KEY environment variable not set")
        print("Set it to run integration tests with real API")
        print("=" * 60)
        return False
    
    print("\n" + "=" * 60)
    print("Running Integration Tests (Real API)")
    print("=" * 60)
    print("⚠️  These tests make real API calls and may cost money")
    
    # Create config with real API key
    real_config = create_test_config(
        api_key=api_key,
        max_retries=1,  # Don't retry on real API to save costs
        debug_mode=False  # Reduce output noise
    )
    
    integration_tests = [
        lambda: test_real_text_generation(real_config),
        lambda: test_real_json_generation(real_config),
        lambda: test_real_temperature_effect(real_config),
    ]
    
    results = []
    for i, test_func in enumerate(integration_tests):
        test_name = test_func.__name__ if hasattr(test_func, '__name__') else f"integration_test_{i+1}"
        print(f"Running {test_name}...", end=" ")
        result = run_test(test_func)
        results.append(result)
        
        if result.passed:
            print("✓ PASS")
        else:
            print("✗ FAIL")
            print(f"  Error: {result.error}")
    
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print(f"\nIntegration Results: {passed}/{total} tests passed")
    print("=" * 60)
    return passed == total


def test_real_text_generation(config):
    """Verify text generation works with real AI API and returns expected structure.
    
    Args:
        config: Test configuration with real API key and settings
    """
    response = generate_text_response([
        {"role": "user", "content": "Say 'Hello, this is a test' and nothing else"}
    ], config)
    
    if not isinstance(response, dict):
        raise AssertionError(f"Expected dict response, got {type(response)}")
    if 'reasoning' not in response or 'content' not in response:
        raise AssertionError(f"Missing keys in response: {response.keys()}")
    if not isinstance(response['content'], str):
        raise AssertionError(f"Expected string content, got {type(response['content'])}")
    if len(response['content'].strip()) == 0:
        raise AssertionError("Got empty content from API")
    if "test" not in response['content'].lower():
        raise AssertionError(f"Content doesn't contain 'test': {response['content']}")


def test_real_json_generation(config):
    """Verify JSON generation works with real AI API and parses correctly.
    
    Args:
        config: Test configuration with real API key and settings
    """
    response = generate_json_response([
        {"role": "system", "content": "Respond with valid JSON only."},
        {"role": "user", "content": "Return a JSON object with exactly these fields: name (string), age (number)"}
    ], config)
    
    if not isinstance(response, dict):
        raise AssertionError(f"Expected dict response, got {type(response)}")
    if 'reasoning' not in response or 'content' not in response:
        raise AssertionError(f"Missing keys in response: {response.keys()}")
    if not isinstance(response['content'], dict):
        raise AssertionError(f"Expected dict content, got {type(response['content'])}")
    if 'name' not in response['content']:
        raise AssertionError(f"Response missing 'name' field: {response['content']}")
    if 'age' not in response['content']:
        raise AssertionError(f"Response missing 'age' field: {response['content']}")
    if not isinstance(response['content']['name'], str):
        raise AssertionError(f"Name should be string, got {type(response['content']['name'])}")
    if not isinstance(response['content']['age'], (int, float)):
        raise AssertionError(f"Age should be number, got {type(response['content']['age'])}")


def test_real_temperature_effect(config):
    """Verify temperature parameter affects response variability with real AI API.
    
    Args:
        config: Test configuration with real API key and settings
    """
    prompt = "Complete this sentence: The weather today is"
    
    # Low temperature (should be more deterministic)
    response1 = generate_text_response([{"role": "user", "content": prompt}], config, temperature=0.1)
    response2 = generate_text_response([{"role": "user", "content": prompt}], config, temperature=0.1)
    
    # High temperature (should be more varied)
    response3 = generate_text_response([{"role": "user", "content": prompt}], config, temperature=1.5)
    
    # Basic validation - all should be dicts with string content
    for i, resp in enumerate([response1, response2, response3], 1):
        if not isinstance(resp, dict):
            raise AssertionError(f"Response {i} should be dict, got {type(resp)}")
        if 'content' not in resp:
            raise AssertionError(f"Response {i} missing content key")
        if not isinstance(resp['content'], str):
            raise AssertionError(f"Response {i} content should be string, got {type(resp['content'])}")
        if len(resp['content'].strip()) == 0:
            raise AssertionError(f"Response {i} content is empty")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Run both test suites
    unit_tests_passed = run_all_tests()
    integration_tests_passed = run_integration_tests()
    
    if unit_tests_passed and integration_tests_passed:
        print("\n🎉 All test suites passed!")
    else:
        print("\n⚠️  Some test suites failed")
        if not unit_tests_passed:
            print("  - Unit tests failed")
        if not integration_tests_passed:
            print("  - Integration tests failed")
    
    # Exit with appropriate code for CI/CD
    exit(0 if unit_tests_passed and integration_tests_passed else 1) 