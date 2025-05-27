# Debug mode
debug_mode = True

# Logging Configuration
log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL
log_to_file = True  # Enable file logging
log_file_rotation = True  # Enable daily log file rotation
console_rich_output = True  # Use Rich for beautiful console output
show_performance_timers = True  # Show performance timing in console

# API Base Configuration (for custom endpoints)
api_base = None  # Set this to your custom endpoint URL if using a custom LLM server
api_version = None  # For Azure OpenAI or other versioned APIs

# Network Configuration
request_timeout = 600  # Timeout in seconds (LiteLLM 2024+ best practice: 600s instead of 6000s)
force_ipv4 = False  # Set to True if experiencing IPv6 connectivity issues

# AI Model Configuration
model = "openai/gpt-4o-mini"  # Updated to use the latest model name
api_key = None

# AI inference retry settings
max_retries = 3
retry_delay = 1.0

# Advanced LiteLLM Settings
litellm_settings = {
    "set_verbose": False,  # Disable verbose logging in production
    "json_logs": False,  # Set to True for structured logging
    "request_timeout": 600,  # Global timeout setting
    "force_ipv4": False,  # Force IPv4 if needed
}

# Provider-specific settings
provider_settings = {
    # Azure OpenAI specific
    "azure": {
        "api_version": "2024-02-01",  # Latest stable API version
    },
    # OpenAI specific
    "openai": {
        "organization": None,  # Set if using OpenAI organization
    },
    # Custom endpoint specific
    "custom": {
        "api_base": None,  # Custom endpoint URL
        "api_key": None,   # Custom endpoint API key
    }
}








