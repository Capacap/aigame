"""
Global configuration settings for the AI Game.
"""

# LLM Model Configuration
DEFAULT_LLM_MODEL = "openai/gpt-4.1-mini"

# You can change this to use different models:
# DEFAULT_LLM_MODEL = "openai/gpt-4o-mini"
# DEFAULT_LLM_MODEL = "anthropic/claude-3-haiku-20240307"
# DEFAULT_LLM_MODEL = "openai/gpt-3.5-turbo"
# DEFAULT_LLM_MODEL = "ollama/llama2"  # For local models

# Game Configuration
MAX_INTERACTION_HISTORY = 256  # Maximum number of conversation turns to keep
DEBUG_MODE = False  # Set to True to enable debug output 