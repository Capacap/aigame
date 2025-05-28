"""
Configuration module for the AI Game project.

Contains all configuration settings for the application including:
- Debug and logging settings
- API configuration and endpoints
- Network and timeout settings
- AI model configuration
- LiteLLM and provider-specific settings

All settings are module-level variables that can be imported and modified
as needed by other modules in the application.
"""

# Alternative approach - create a proper config class
class AIGameConfig:
    """Main configuration class that implements AIInferenceConfig protocol"""
    
    # Debug mode
    debug_mode = True
    
    # AI Model Configuration
    model = "openai/gpt-4.1-nano"
    api_key = None
    api_base = None
    api_version = None
    
    # Network Configuration
    request_timeout = 600
    force_ipv4 = False
    
    # AI inference retry settings
    max_retries = 3
    retry_delay = 1.0
    
    # Logging Configuration
    log_level = "INFO"
    log_to_file = True
    log_file_rotation = True
    log_directory = "logs"
    console_rich_output = True
    show_performance_timers = False
    
    # Console Output Control
    console_debug_level = "INFO"
    show_ai_debug_panels = False
    show_litellm_console_logs = False
    console_minimal_mode = True

# Create a global instance for easy importing
config = AIGameConfig()

# Keep the old module-level variables for backward compatibility
debug_mode = config.debug_mode
model = config.model
api_key = config.api_key
api_base = config.api_base
api_version = config.api_version
request_timeout = config.request_timeout
force_ipv4 = config.force_ipv4
max_retries = config.max_retries
retry_delay = config.retry_delay
log_level = config.log_level
log_to_file = config.log_to_file
log_file_rotation = config.log_file_rotation
log_directory = config.log_directory
console_rich_output = config.console_rich_output
show_performance_timers = config.show_performance_timers
console_debug_level = config.console_debug_level
show_ai_debug_panels = config.show_ai_debug_panels
show_litellm_console_logs = config.show_litellm_console_logs
console_minimal_mode = config.console_minimal_mode

# Advanced LiteLLM Settings
litellm_settings = {
    "set_verbose": False,
    "json_logs": False,
    "request_timeout": 600,
    "force_ipv4": False,
}

# Provider-specific settings
provider_settings = {
    "azure": {
        "api_version": "2024-02-01",
    },
    "openai": {
        "organization": None,
    },
    "custom": {
        "api_base": None,
        "api_key": None,
    }
}








