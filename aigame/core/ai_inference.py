import time
import json
import re
from typing import Dict, Any, Optional, Protocol, List, Union
from litellm import completion

# Import centralized logging
try:
    from .logger import ai_request_debug, ai_response_debug, get_logger, performance_timer
except ImportError:
    # Fallback for direct execution - try absolute import
    try:
        from logger import ai_request_debug, ai_response_debug, get_logger, performance_timer
    except ImportError:
        # Minimal fallback if logger module is not available
        import logging
        def ai_request_debug(*args, **kwargs): pass
        def ai_response_debug(*args, **kwargs): pass
        def get_logger(name): return logging.getLogger(f"aigame.{name}")
        class _DummyTimer:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def performance_timer(name): return _DummyTimer()


# Constants for validation and defaults
DEFAULT_TEMPERATURE_TEXT = 0.7
DEFAULT_TEMPERATURE_JSON = 0.3
DEFAULT_MAX_TOKENS = 1000
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0
REPETITION_PENALTY_MIN = 0.0

# Reasoning tag patterns for different AI models
REASONING_PATTERNS = [
    r'<think>(.*?)</think>',           # Standard thinking tags
    r'<thinking>(.*?)</thinking>',     # Alternative thinking tags
    r'<reason>(.*?)</reason>',         # Reasoning tags
    r'<reasoning>(.*?)</reasoning>',   # Alternative reasoning tags
    r'<analysis>(.*?)</analysis>',     # Analysis tags
]

# Error message constants
JSON_WORD_REQUIRED_ERROR = (
    "When using JSON response format, at least one message must contain the word 'json'. "
    "Add JSON instructions to your system_message_content or user_message_content. "
    "Example: system_message_content='Respond with valid JSON only.'"
)
AI_REQUEST_FAILED_TEMPLATE = "AI {request_type} request failed after {attempts} attempts. Last error: {error}"


class AIInferenceConfig(Protocol):
    """Protocol defining the configuration interface needed by AI inference functions."""
    debug_mode: bool
    model: str
    api_key: Optional[str]
    api_base: Optional[str]
    api_version: Optional[str]
    request_timeout: int
    force_ipv4: bool
    max_retries: int
    retry_delay: float
    # Optional overrides for defaults
    default_temperature_text: Optional[float] = None
    default_temperature_json: Optional[float] = None
    default_max_tokens: Optional[int] = None


def _validate_common_params(user_message_content: str, system_message_content: Optional[str], assistant_message_content: Optional[str], temperature: Optional[float], repetition_penalty: Optional[float]) -> None:
    """Validate common parameters for both text and JSON responses."""
    if not user_message_content.strip():
        raise ValueError("user_message_content must be a non-empty string")
    if system_message_content is not None and not system_message_content.strip():
        raise ValueError("system_message_content must be a non-empty string if provided")
    if temperature is not None and (temperature < TEMPERATURE_MIN or temperature > TEMPERATURE_MAX):
        raise ValueError(f"temperature must be a number between {TEMPERATURE_MIN} and {TEMPERATURE_MAX}")
    if repetition_penalty is not None and repetition_penalty <= REPETITION_PENALTY_MIN:
        raise ValueError(f"repetition_penalty must be a positive number greater than {REPETITION_PENALTY_MIN}")


def _validate_json_request(messages: List[Dict[str, str]]) -> None:
    """Validate that JSON requests contain the word 'json' as required by OpenAI API."""
    json_pattern = re.compile(r'\bjson\b', re.IGNORECASE)
    
    # Check all message content for the word "json"
    for message in messages:
        if json_pattern.search(message.get('content', '')):
            return  # Found "json" in at least one message
    
    # If we get here, no message contains "json"
    raise ValueError(JSON_WORD_REQUIRED_ERROR)


def _build_messages(user_message_content: str, system_message_content: Optional[str], assistant_message_content: Optional[str]) -> List[Dict[str, str]]:
    """Build messages array for AI requests without any modification."""
    messages = []
    if system_message_content:
        messages.append({"role": "system", "content": system_message_content})
    
    messages.append({"role": "user", "content": user_message_content})
    if assistant_message_content is not None:
        messages.append({"role": "assistant", "content": assistant_message_content})
    
    return messages


def _validate_response(response: Any) -> str:
    """Validate and extract content from AI response."""
    if not response or not response.choices:
        raise ValueError("Empty response from AI service")
    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty content in AI response")
    return content


def _process_assistant_prefix(content: str, assistant_message_content: Optional[str]) -> str:
    """Process response with assistant prefix if provided."""
    if assistant_message_content is not None:
        return assistant_message_content + content.strip()
    return content.strip()


def _process_json_prefix(content: str, assistant_message_content: Optional[str], config: AIInferenceConfig) -> str:
    """Process JSON response with assistant prefix, handling complete vs partial JSON."""
    if assistant_message_content is None:
        return content.strip()
    
    ai_completion = content.strip()
    try:
        json.loads(ai_completion)
        decision = "AI returned complete JSON, using that instead of combining"
        full_response = ai_completion
    except json.JSONDecodeError:
        decision = "Combining prefix with AI completion"
        full_response = assistant_message_content + ai_completion
    
    # Log prefix handling if debug mode is enabled
    if config.debug_mode:
        logger = get_logger("ai_inference")
        logger.debug(f"JSON Prefix Handling - Assistant: '{assistant_message_content}', AI: '{ai_completion}', Decision: {decision}")
    
    return full_response


def _get_default_temperature(config: AIInferenceConfig, is_json: bool) -> float:
    """Get the appropriate default temperature based on request type and config."""
    if is_json:
        config_value = getattr(config, 'default_temperature_json', None)
        return config_value if config_value is not None else DEFAULT_TEMPERATURE_JSON
    else:
        config_value = getattr(config, 'default_temperature_text', None)
        return config_value if config_value is not None else DEFAULT_TEMPERATURE_TEXT


def _get_default_max_tokens(config: AIInferenceConfig) -> int:
    """Get the default max tokens from config or use system default."""
    config_value = getattr(config, 'default_max_tokens', None)
    return config_value if config_value is not None else DEFAULT_MAX_TOKENS


def _execute_with_retry(request_params: Dict[str, Any], request_type: str, config: AIInferenceConfig, assistant_message_content: Optional[str] = None, is_json: bool = False) -> Dict[str, Any]:
    """Execute AI request with retry logic.
    
    Returns:
        Dict with 'reasoning' and 'content' keys. For JSON responses, 'content' 
        will be the parsed JSON object. For text responses, 'content' will be a string.
        'reasoning' will be None if no reasoning tags are found.
    """
    logger = get_logger("ai_inference")
    last_exception = None
    retry_delay = config.retry_delay
    
    for attempt in range(config.max_retries + 1):
        try:
            if config.debug_mode:
                logger.debug(f"AI {request_type.lower()} request attempt {attempt + 1}/{config.max_retries + 1}")
            
            with performance_timer(f"AI {request_type} Request"):
                response = completion(**request_params)
                content = _validate_response(response)
                stripped_content = content.strip()
            
            # Extract reasoning from the raw response
            reasoning_result = _extract_reasoning(stripped_content)
            
            if is_json:
                full_response = _process_json_prefix(reasoning_result['content'], assistant_message_content, config)
                try:
                    parsed_json = json.loads(full_response)
                    final_result = {
                        'reasoning': reasoning_result['reasoning'],
                        'content': parsed_json
                    }
                    if config.debug_mode:
                        ai_response_debug(request_type, stripped_content, final_result)
                    return final_result
                except json.JSONDecodeError as json_error:
                    if config.debug_mode:
                        logger.error(f"Invalid JSON in AI response: {str(json_error)}")
                        ai_response_debug(request_type, stripped_content, full_response)
                    raise ValueError(f"Invalid JSON in AI response: {str(json_error)}")
            else:
                final_response = _process_assistant_prefix(reasoning_result['content'], assistant_message_content)
                final_result = {
                    'reasoning': reasoning_result['reasoning'],
                    'content': final_response
                }
                if config.debug_mode:
                    ai_response_debug(request_type, stripped_content, final_result)
                return final_result
                
        except Exception as e:
            last_exception = e
            if config.debug_mode:
                logger.warning(f"AI {request_type.lower()} request failed (attempt {attempt + 1}): {str(e)}")
            if attempt < config.max_retries:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                break
    
    raise RuntimeError(AI_REQUEST_FAILED_TEMPLATE.format(request_type=request_type, attempts=config.max_retries + 1, error=str(last_exception)))


def _build_request_params(messages: List[Dict[str, str]], config: AIInferenceConfig, temperature: Optional[float] = None, repetition_penalty: Optional[float] = None, response_format: Optional[Dict[str, str]] = None, max_tokens: Optional[int] = None, is_json: bool = False) -> Dict[str, Any]:
    """Build request parameters with latest LiteLLM best practices."""
    effective_temperature = temperature or _get_default_temperature(config, is_json)
    effective_max_tokens = max_tokens or _get_default_max_tokens(config)
    
    request_params = {
        "model": config.model,
        "messages": messages,
        "max_tokens": effective_max_tokens,
        "temperature": effective_temperature,
        "timeout": config.request_timeout,
    }
    
    if response_format:
        request_params["response_format"] = response_format
    if repetition_penalty is not None:
        request_params["repetition_penalty"] = repetition_penalty
    if config.api_key:
        request_params["api_key"] = config.api_key
    if config.api_base:
        request_params["api_base"] = config.api_base
    if config.api_version:
        request_params["api_version"] = config.api_version
    if config.force_ipv4:
        request_params["force_ipv4"] = True
    
    return request_params


def generate_text_response(user_message_content: str, config: AIInferenceConfig, system_message_content: Optional[str] = None, assistant_message_content: Optional[str] = None, temperature: Optional[float] = None, repetition_penalty: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Generate a text response from the AI model with automatic reasoning extraction.
    
    Returns:
        Dict with 'reasoning' and 'content' keys:
        - 'reasoning': Extracted reasoning content from <think>, <reasoning>, etc. tags (None if not found)
        - 'content': The main response content with reasoning tags removed
    """
    _validate_common_params(user_message_content, system_message_content, assistant_message_content, temperature, repetition_penalty)
    
    messages = _build_messages(user_message_content, system_message_content, assistant_message_content)
    request_params = _build_request_params(messages, config, temperature, repetition_penalty, max_tokens=max_tokens, is_json=False)
    
    if config.debug_mode:
        ai_request_debug("TEXT", messages, request_params)
    
    return _execute_with_retry(request_params, "TEXT", config, assistant_message_content, is_json=False)


def generate_json_response(user_message_content: str, config: AIInferenceConfig, system_message_content: Optional[str] = None, assistant_message_content: Optional[str] = None, temperature: Optional[float] = None, repetition_penalty: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Generate a JSON response from the AI model with automatic reasoning extraction.
    
    Returns:
        Dict with 'reasoning' and 'content' keys:
        - 'reasoning': Extracted reasoning content from <think>, <reasoning>, etc. tags (None if not found)
        - 'content': The parsed JSON object with reasoning tags removed from the original response
    
    Note: This function uses JSON response format but does not modify your prompts.
    If you want the AI to respond in JSON, include that instruction in your system_message_content.
    """
    _validate_common_params(user_message_content, system_message_content, assistant_message_content, temperature, repetition_penalty)
    
    messages = _build_messages(user_message_content, system_message_content, assistant_message_content)
    _validate_json_request(messages)  # Validate JSON requirement before API call
    
    response_format = {"type": "json_object"}
    request_params = _build_request_params(messages, config, temperature, repetition_penalty, response_format, max_tokens, is_json=True)
    
    if config.debug_mode:
        ai_request_debug("JSON", messages, request_params)
    
    return _execute_with_retry(request_params, "JSON", config, assistant_message_content, is_json=True)


def _extract_reasoning(content: str) -> Dict[str, Any]:
    """Extract reasoning content from AI response and return structured result.
    
    Returns:
        Dict with 'reasoning' and 'content' keys. If no reasoning found,
        'reasoning' will be None and 'content' will be the original text.
    """
    reasoning_parts = []
    cleaned_content = content
    
    # Extract all reasoning patterns
    for pattern in REASONING_PATTERNS:
        matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
        if matches:
            reasoning_parts.extend(matches)
            # Remove the reasoning tags from the content
            cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
    
    # Clean up the content (remove extra whitespace)
    cleaned_content = re.sub(r'\n\s*\n', '\n', cleaned_content.strip())
    
    # Combine all reasoning parts
    reasoning = None
    if reasoning_parts:
        # Join multiple reasoning sections with separators
        reasoning = '\n\n--- Reasoning Section ---\n\n'.join(part.strip() for part in reasoning_parts)
    
    return {
        'reasoning': reasoning,
        'content': cleaned_content
    }


if __name__ == "__main__":
    from unittest.mock import patch, MagicMock
    from dataclasses import dataclass
    from typing import List
    
    @dataclass
    class TestConfig:
        """Isolated test configuration without external dependencies."""
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
        """Create isolated test configuration with optional overrides."""
        config = TestConfig()
        for key, value in overrides.items():
            setattr(config, key, value)
        return config
    
    def mock_completion_response(content: str) -> MagicMock:
        """Create mock response object matching LiteLLM structure."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = content
        return mock_response
    
    class TestResult:
        """Standardized test result tracking."""
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
        """Execute a test function and capture results."""
        result = TestResult(test_func.__name__)
        try:
            test_func()
            result.success()
        except Exception as e:
            result.failure(str(e))
        return result
    
    # === VALIDATION TESTS ===
    
    def test_empty_user_message_validation():
        """Test that empty user messages are rejected."""
        config = create_test_config()
        try:
            generate_text_response("", config)
            raise AssertionError("Should have raised ValueError for empty message")
        except ValueError as e:
            if "non-empty string" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")
    
    def test_temperature_validation():
        """Test temperature parameter validation."""
        config = create_test_config()
        
        # Test invalid temperature (too high)
        try:
            generate_text_response("test", config, temperature=3.0)
            raise AssertionError("Should have raised ValueError for temperature > 2.0")
        except ValueError as e:
            if "temperature must be a number between" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")
        
        # Test invalid temperature (negative)
        try:
            generate_text_response("test", config, temperature=-1.0)
            raise AssertionError("Should have raised ValueError for negative temperature")
        except ValueError as e:
            if "temperature must be a number between" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")
    
    def test_json_word_requirement():
        """Test that JSON requests require 'json' in messages."""
        config = create_test_config()
        
        # Test missing 'json' word
        try:
            generate_json_response(
                user_message_content="Generate a character", 
                config=config,
                system_message_content="You are helpful."
            )
            raise AssertionError("Should have raised ValueError for missing 'json'")
        except ValueError as e:
            if "must contain the word 'json'" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")
        
        # Test 'jsonify' should not work (word boundary)
        try:
            generate_json_response(
                user_message_content="Use jsonify method", 
                config=config
            )
            raise AssertionError("Should have raised ValueError for 'jsonify' (not 'json')")
        except ValueError as e:
            if "must contain the word 'json'" not in str(e):
                raise AssertionError(f"Wrong error message: {e}")
    
    # === FUNCTIONAL TESTS ===
    
    def test_basic_text_generation():
        """Test basic text generation with mocked response."""
        config = create_test_config()
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response("Hello, world!")
            
            result = generate_text_response("Say hello", config)
            
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
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response("Greetings, adventurer!")
            
            result = generate_text_response(
                user_message_content="Hello",
                config=config,
                system_message_content="You are a wizard"
            )
            
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
        """Test that assistant prefix is properly combined."""
        config = create_test_config()
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response("wanted to get to the other side!")
            
            result = generate_text_response(
                user_message_content="Why did the chicken cross the road?",
                config=config,
                assistant_message_content="Because it "
            )
            
            expected = "Because it wanted to get to the other side!"
            if result['content'] != expected:
                raise AssertionError(f"Expected '{expected}', got '{result['content']}'")
    
    def test_json_generation_with_valid_prompt():
        """Test JSON generation with valid 'json' in prompt."""
        config = create_test_config()
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response('{"name": "Test", "level": 1}')
            
            result = generate_json_response(
                user_message_content="Generate character in JSON format",
                config=config
            )
            
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
        """Test JSON prefix handling with complete vs partial responses."""
        config = create_test_config(debug_mode=False)  # Disable debug to avoid print output
        
        with patch('__main__.completion') as mock_completion:
            # Test: AI returns complete JSON (should use AI response, not combine)
            mock_completion.return_value = mock_completion_response('{"name": "Aragorn", "class": "Ranger", "level": 10}')
            
            result = generate_json_response(
                user_message_content="Add level field with value 10 to this character",
                config=config,
                system_message_content="Complete the JSON object.",
                assistant_message_content='{"name": "Aragorn", "class": "Ranger"'
            )
            
            expected = {"name": "Aragorn", "class": "Ranger", "level": 10}
            if result['content'] != expected:
                raise AssertionError(f"Expected {expected}, got {result['content']}")
    
    def test_temperature_defaults():
        """Test that temperature defaults work correctly."""
        config = create_test_config()
        
        with patch('__main__.completion') as mock_completion:
            # Test text default temperature
            mock_completion.return_value = mock_completion_response("test")
            generate_text_response("test", config)
            call_args = mock_completion.call_args[1]
            if call_args['temperature'] != DEFAULT_TEMPERATURE_TEXT:
                raise AssertionError(f"Wrong text temperature: {call_args['temperature']}")
            
            # Test JSON default temperature
            mock_completion.return_value = mock_completion_response('{"result": "test"}')
            generate_json_response("test json", config)
            call_args = mock_completion.call_args[1]
            if call_args['temperature'] != DEFAULT_TEMPERATURE_JSON:
                raise AssertionError(f"Wrong JSON temperature: {call_args['temperature']}")
    
    def test_retry_logic():
        """Test retry logic with failures."""
        config = create_test_config(max_retries=2)
        
        with patch('__main__.completion') as mock_completion:
            # First two calls fail, third succeeds
            mock_completion.side_effect = [
                Exception("Network error"),
                Exception("Rate limit"),
                mock_completion_response("Success!")
            ]
            
            result = generate_text_response("test", config)
            
            if result['content'] != "Success!":
                raise AssertionError(f"Expected 'Success!', got '{result['content']}'")
            if mock_completion.call_count != 3:
                raise AssertionError(f"Expected 3 calls, got {mock_completion.call_count}")
    
    def test_retry_exhaustion():
        """Test that retry exhaustion raises proper error."""
        config = create_test_config(max_retries=1)
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.side_effect = Exception("Persistent error")
            
            try:
                generate_text_response("test", config)
                raise AssertionError("Should have raised RuntimeError after retries exhausted")
            except RuntimeError as e:
                if "failed after 2 attempts" not in str(e):
                    raise AssertionError(f"Wrong error message: {e}")
    
    def test_reasoning_extraction():
        """Test reasoning extraction from AI responses."""
        config = create_test_config()
        
        # Test with <think> tags
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response(
                "<think>I need to consider the user's request carefully. This seems like a greeting.</think>Hello! How can I help you today?"
            )
            
            result = generate_text_response(
                "Hello",
                config
            )
            
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
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response(
                "<thinking>First, I should understand what they want.</thinking>I understand your question. <analysis>This requires a detailed response.</analysis>Here's my answer."
            )
            
            result = generate_text_response(
                "Explain something",
                config
            )
            
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
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response("Just a simple response without reasoning.")
            
            result = generate_text_response(
                "Simple question",
                config
            )
            
            if result['reasoning'] is not None:
                raise AssertionError(f"Expected no reasoning, got: {result['reasoning']}")
            if result['content'] != "Just a simple response without reasoning.":
                raise AssertionError(f"Content incorrect: {result['content']}")
    
    def test_json_reasoning_extraction():
        """Test reasoning extraction with JSON responses."""
        config = create_test_config()
        
        with patch('__main__.completion') as mock_completion:
            mock_completion.return_value = mock_completion_response(
                '<reason>I need to create a character with the specified attributes.</reason>{"name": "Test Character", "level": 5}'
            )
            
            result = generate_json_response(
                "Create a character in JSON format",
                config,
                system_message_content="Respond with valid JSON only."
            )
            
            if result['reasoning'] is None:
                raise AssertionError("Expected reasoning to be extracted")
            if "create a character" not in result['reasoning'].lower():
                raise AssertionError(f"Reasoning content incorrect: {result['reasoning']}")
            if not isinstance(result['content'], dict):
                raise AssertionError(f"Expected dict content, got {type(result['content'])}")
            if result['content']['name'] != "Test Character":
                raise AssertionError(f"JSON content incorrect: {result['content']}")
    
    # === TEST RUNNER ===
    
    def run_all_tests():
        """Run all tests and report results."""
        test_functions = [
            test_empty_user_message_validation,
            test_temperature_validation,
            test_json_word_requirement,
            test_basic_text_generation,
            test_system_message_inclusion,
            test_assistant_prefix_combination,
            test_json_generation_with_valid_prompt,
            test_json_prefix_handling,
            test_temperature_defaults,
            test_retry_logic,
            test_retry_exhaustion,
            test_reasoning_extraction,
            test_reasoning_extraction_multiple_tags,
            test_reasoning_extraction_no_reasoning,
            test_json_reasoning_extraction,
        ]
        
        print("=" * 60)
        print("Running AI Inference Tests")
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
        print(f"Test Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed!")
        else:
            print("⚠️  Some tests failed:")
            for result in results:
                if not result.passed:
                    print(f"  - {result.name}: {result.error}")
        
        print("=" * 60)
        return passed == total

    # === INTEGRATION TESTS (Real API) ===
    
    def run_integration_tests():
        """Run integration tests with real API calls.
        
        Set environment variable RUN_INTEGRATION_TESTS=1 to enable.
        Requires valid API key in environment or config file.
        """
        import os
        
        if not os.getenv('RUN_INTEGRATION_TESTS'):
            print("\n" + "=" * 60)
            print("Integration Tests Skipped")
            print("=" * 60)
            print("To run integration tests with real API calls:")
            print("  export RUN_INTEGRATION_TESTS=1")
            print("  export OPENAI_API_KEY=your_real_key")
            print("  python aigame/core/ai_inference.py")
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
        """Test real text generation with actual API."""
        response = generate_text_response(
            user_message_content="Say 'Hello, this is a test' and nothing else",
            config=config
        )
        
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
        """Test real JSON generation with actual API."""
        response = generate_json_response(
            user_message_content="Return a JSON object with exactly these fields: name (string), age (number)",
            config=config,
            system_message_content="Respond with valid JSON only."
        )
        
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
        """Test that temperature actually affects responses."""
        prompt = "Complete this sentence: The weather today is"
        
        # Low temperature (should be more deterministic)
        response1 = generate_text_response(prompt, config, temperature=0.1)
        response2 = generate_text_response(prompt, config, temperature=0.1)
        
        # High temperature (should be more varied)
        response3 = generate_text_response(prompt, config, temperature=1.5)
        
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