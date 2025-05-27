# ============================================================================
# IMPORTS
# ============================================================================

import time
import json
import re
from typing import Dict, Any, Optional, Protocol, List
from litellm import completion
from .logger import ai_request_debug, ai_response_debug, get_logger, performance_timer


# ============================================================================
# CONSTANTS AND CONFIGURATION
# ============================================================================

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
    "Add JSON instructions to your messages. "
    "Example: {'role': 'system', 'content': 'Respond with valid JSON only.'}"
)
AI_REQUEST_FAILED_TEMPLATE = (
    "AI {request_type} request failed after {attempts} attempts. "
    "Last error: {error}. "
    "This may indicate network issues, API rate limits, invalid API key, or service outage. "
    "Check your configuration, wait a moment, and try again."
)


# ============================================================================
# PROTOCOLS AND INTERFACES
# ============================================================================

class AIInferenceConfig(Protocol):
    """Configuration interface for AI inference functions.
    
    Defines required and optional configuration parameters for AI requests.
    Use dependency injection pattern to provide configuration to inference functions.
    
    Required Attributes:
        debug_mode: Enable detailed logging and debug output
        model: AI model name (e.g., 'gpt-4o-mini', 'claude-3-sonnet')
        api_key: API key for the AI service (None for environment variable)
        api_base: Custom API endpoint URL (None for default)
        api_version: API version string (None for default)
        request_timeout: Request timeout in seconds
        force_ipv4: Force IPv4 connections for connectivity issues
        max_retries: Maximum retry attempts on failure
        retry_delay: Initial delay between retries (exponential backoff)
        
    Optional Overrides:
        default_temperature_text: Override default text temperature (0.7)
        default_temperature_json: Override default JSON temperature (0.3)
        default_max_tokens: Override default max tokens (1000)
    """
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


# ============================================================================
# PUBLIC API FUNCTIONS
# ============================================================================

def generate_text_response(messages: List[Dict[str, str]], config: AIInferenceConfig, temperature: Optional[float] = None, repetition_penalty: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Generate text response from AI with automatic reasoning extraction.
    
    Sends messages to AI model and returns structured response with reasoning
    automatically extracted from <think>, <reasoning>, and similar tags.
    
    Args:
        messages: Conversation messages [{'role': 'user', 'content': 'Hello'}]
        config: AI configuration (model, API key, retry settings)
        temperature: Response creativity (0.1=focused, 1.5=creative, default=0.7)
        repetition_penalty: Reduce repetition (1.0=none, 1.2=moderate, default=none)
        max_tokens: Maximum response length (default=1000)
    
    Returns:
        Dict with keys:
            - 'reasoning': Extracted AI reasoning (None if not found)
            - 'content': Main response text
    
    Raises:
        ValueError: If messages are invalid or parameters out of range
        RuntimeError: If AI request fails after all retries
        
    Example:
        >>> messages = [{'role': 'user', 'content': 'Explain quantum physics'}]
        >>> result = generate_text_response(messages, config)
        >>> print(result['content'])  # Main explanation
        >>> print(result['reasoning'])  # AI's thinking process (if any)
    """
    _validate_messages_and_params(messages, temperature, repetition_penalty)
    
    request_params = _build_request_params(messages, config, temperature, repetition_penalty, max_tokens=max_tokens, is_json=False)
    
    return _execute_with_retry(request_params, config, messages, is_json=False)


def generate_json_response(messages: List[Dict[str, str]], config: AIInferenceConfig, temperature: Optional[float] = None, repetition_penalty: Optional[float] = None, max_tokens: Optional[int] = None) -> Dict[str, Any]:
    """Generate JSON response from AI with automatic reasoning extraction.
    
    Sends messages to AI model with JSON response format enforced. Automatically
    extracts reasoning and parses JSON content. Requires 'json' keyword in messages.
    
    Args:
        messages: Conversation messages (must contain 'json' keyword)
        config: AI configuration (model, API key, retry settings)
        temperature: Response creativity (0.1=focused, 1.5=creative, default=0.3)
        repetition_penalty: Reduce repetition (1.0=none, 1.2=moderate, default=none)
        max_tokens: Maximum response length (default=1000)
    
    Returns:
        Dict with keys:
            - 'reasoning': Extracted AI reasoning (None if not found)
            - 'content': Parsed JSON object (dict/list)
    
    Raises:
        ValueError: If messages lack 'json' keyword, invalid JSON, or bad parameters
        RuntimeError: If AI request fails after all retries
        
    Example:
        >>> messages = [
        ...     {'role': 'system', 'content': 'Respond with valid JSON only'},
        ...     {'role': 'user', 'content': 'Create character in JSON format'}
        ... ]
        >>> result = generate_json_response(messages, config)
        >>> character = result['content']  # {'name': 'Hero', 'level': 1}
    """
    _validate_messages_and_params(messages, temperature, repetition_penalty)
    _validate_json_request(messages)  # Additional validation for JSON requests
    
    response_format = {"type": "json_object"}
    request_params = _build_request_params(messages, config, temperature, repetition_penalty, response_format, max_tokens, is_json=True)
    
    return _execute_with_retry(request_params, config, messages, is_json=True)


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _validate_json_request(messages: List[Dict[str, str]]) -> None:
    """Ensure JSON requests contain 'json' keyword as required by OpenAI API.
    
    Args:
        messages: List of message dictionaries to check for 'json' keyword
    
    Raises:
        ValueError: If no message contains the word 'json' (case-insensitive).
    """
    json_pattern = re.compile(r'\bjson\b', re.IGNORECASE)
    
    # Check all message content for the word "json"
    for message in messages:
        if json_pattern.search(message.get('content', '')):
            return  # Found "json" in at least one message
    
    # If we get here, no message contains "json"
    raise ValueError(JSON_WORD_REQUIRED_ERROR)


def _validate_messages_and_params(messages: List[Dict[str, str]], temperature: Optional[float], repetition_penalty: Optional[float]) -> None:
    """Validate message structure and AI parameters.
    
    Args:
        messages: List of message dictionaries to validate
        temperature: Temperature parameter to validate (0.0-2.0)
        repetition_penalty: Repetition penalty to validate (>0.0)
        
    Raises:
        ValueError: If any validation fails with detailed error message.
    """
    if not messages or not isinstance(messages, list):
        raise ValueError(
            "messages must be a non-empty list of dictionaries. "
            "Example: [{'role': 'user', 'content': 'Hello'}]"
        )
    
    # Validate message structure
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(
                f"Message {i} must be a dictionary with 'role' and 'content' keys. "
                f"Got {type(msg).__name__}: {msg}"
            )
        if 'role' not in msg or 'content' not in msg:
            missing_keys = [key for key in ['role', 'content'] if key not in msg]
            raise ValueError(
                f"Message {i} missing required keys: {missing_keys}. "
                f"Message has keys: {list(msg.keys())}. "
                f"Example: {{'role': 'user', 'content': 'Hello'}}"
            )
        if not msg['content'].strip():
            raise ValueError(
                f"Message {i} content must be non-empty. "
                f"Got role='{msg['role']}' with empty/whitespace content."
            )
    
    # Validate temperature and repetition_penalty
    if temperature is not None and (temperature < TEMPERATURE_MIN or temperature > TEMPERATURE_MAX):
        raise ValueError(
            f"temperature must be between {TEMPERATURE_MIN} and {TEMPERATURE_MAX}, got {temperature}. "
            f"Use lower values (0.1-0.3) for focused responses, higher values (0.7-1.5) for creative responses."
        )
    if repetition_penalty is not None and repetition_penalty <= REPETITION_PENALTY_MIN:
        raise ValueError(
            f"repetition_penalty must be greater than {REPETITION_PENALTY_MIN}, got {repetition_penalty}. "
            f"Typical values are 1.0-1.2 (1.0 = no penalty, higher = more penalty)."
        )


def _validate_response(response: Any) -> str:
    """Extract and validate content from AI service response.
    
    Args:
        response: Raw response object from LiteLLM completion call
        
    Returns:
        str: Validated content string from the AI response
        
    Raises:
        ValueError: If response is empty, invalid, or contains no content.
    """
    if not response or not response.choices:
        raise ValueError(
            "Empty or invalid response from AI service. "
            "This may indicate a network issue, API key problem, or service outage. "
            "Check your configuration and try again."
        )
    content = response.choices[0].message.content
    if not content:
        raise ValueError(
            "AI service returned empty content. "
            "This may happen if the request was filtered, the model refused to respond, "
            "or there was an issue with the prompt. Try rephrasing your request."
        )
    return content


def _get_default_temperature(config: AIInferenceConfig, is_json: bool) -> float:
    """Get appropriate default temperature based on request type and configuration.
    
    Args:
        config: Configuration object with optional temperature overrides
        is_json: Whether this is for a JSON request (uses lower default)
        
    Returns:
        float: Default temperature (0.3 for JSON, 0.7 for text)
    """
    if is_json:
        config_value = getattr(config, 'default_temperature_json', None)
        return config_value if config_value is not None else DEFAULT_TEMPERATURE_JSON
    else:
        config_value = getattr(config, 'default_temperature_text', None)
        return config_value if config_value is not None else DEFAULT_TEMPERATURE_TEXT


def _get_default_max_tokens(config: AIInferenceConfig) -> int:
    """Get default max tokens from configuration or system default.
    
    Args:
        config: Configuration object with optional max_tokens override
        
    Returns:
        int: Maximum tokens to generate (default: 1000)
    """
    config_value = getattr(config, 'default_max_tokens', None)
    return config_value if config_value is not None else DEFAULT_MAX_TOKENS


def _execute_with_retry(request_params: Dict[str, Any], config: AIInferenceConfig, messages: List[Dict[str, str]], is_json: bool = False) -> Dict[str, Any]:
    """Execute AI request with exponential backoff retry logic and reasoning extraction.
    
    Handles request execution, retry logic, debug logging, reasoning extraction,
    and JSON parsing. Automatically extracts reasoning from <think>, <reasoning>,
    and similar tags in AI responses.
    
    Args:
        request_params: Complete LiteLLM request parameters
        config: AI inference configuration with retry settings
        messages: Original messages for debug logging
        is_json: Whether to parse response as JSON
        
    Returns:
        Dict with keys:
            - 'reasoning': Extracted reasoning content (None if not found)
            - 'content': Main response (str for text, dict for JSON)
            
    Raises:
        ValueError: If JSON parsing fails or response validation fails
        RuntimeError: If all retry attempts are exhausted
    """
    logger = get_logger("ai_inference")
    request_type = "JSON" if is_json else "TEXT"
    
    # Debug request logging
    if config.debug_mode:
        ai_request_debug(request_type, messages, request_params)
    
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
            
            # Prepare final content based on request type
            if is_json:
                try:
                    final_content = json.loads(reasoning_result['content'])
                except json.JSONDecodeError as json_error:
                    if config.debug_mode:
                        logger.error(f"Invalid JSON in AI response: {str(json_error)}")
                        ai_response_debug(request_type, stripped_content, reasoning_result['content'])
                    raise ValueError(
                        f"AI returned invalid JSON: {str(json_error)}. "
                        f"Response content: '{reasoning_result['content'][:200]}{'...' if len(reasoning_result['content']) > 200 else ''}'. "
                        f"Ensure your prompt clearly requests valid JSON format. "
                        f"Example: 'Respond with valid JSON only: {{\"key\": \"value\"}}'"
                    )
            else:
                final_content = reasoning_result['content']
            
            # Create final result (consolidated logic)
            final_result = {
                'reasoning': reasoning_result['reasoning'],
                'content': final_content
            }
            
            # Debug response logging
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
    """Build complete LiteLLM request parameters with best practices and defaults.
    
    Combines user parameters with configuration settings, applies appropriate
    defaults based on request type, and includes all optional API parameters.
    
    Args:
        messages: Conversation messages for the AI
        config: Configuration with model, API keys, and settings
        temperature: Override default temperature (None uses config/system default)
        repetition_penalty: Penalty for repetitive text (None = no penalty)
        response_format: JSON response format specification
        max_tokens: Maximum tokens to generate (None uses config/system default)
        is_json: Whether this is a JSON request (affects temperature default)
        
    Returns:
        Dict: Complete request parameters ready for LiteLLM completion call
    """
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


def _extract_reasoning(content: str) -> Dict[str, Any]:
    """Extract reasoning content from AI response using multiple tag patterns.
    
    Searches for reasoning in <think>, <thinking>, <reason>, <reasoning>, and
    <analysis> tags. Removes tags from content and combines multiple reasoning
    sections with separators.
    
    Args:
        content: Raw AI response text that may contain reasoning tags
        
    Returns:
        Dict with keys:
            - 'reasoning': Combined reasoning text (None if no tags found)
            - 'content': Original text with reasoning tags removed
            
    Example:
        >>> text = "<think>Let me consider...</think>The answer is 42."
        >>> result = _extract_reasoning(text)
        >>> result['reasoning']  # "Let me consider..."
        >>> result['content']    # "The answer is 42."
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