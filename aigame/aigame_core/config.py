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

# Debug Configuration
LLM_DEBUG_MODE = True  # Set to True to enable LLM invocation tracking

# Debug utility function
def debug_llm_call(component: str, purpose: str, model: str = None):
    """Print debug information for LLM calls when debug mode is enabled."""
    if LLM_DEBUG_MODE:
        from rich import print as rprint
        from rich.text import Text
        model_info = f" [{model}]" if model else ""
        rprint(Text(f"🤖 LLM Call: {component} → {purpose}{model_info}", style="dim bright_blue")) 