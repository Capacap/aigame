# AI Adventure Game

A sophisticated text-based adventure game powered by Large Language Models (LLMs). Experience dynamic conversations, intelligent NPCs, and emergent storytelling where every interaction shapes your journey.

## Features

- **Dynamic Conversations**: NPCs powered by AI respond naturally to any input
- **Intelligent Action Parsing**: Natural language commands are understood contextually
- **Rich Storytelling**: AI-generated scenarios with meaningful character interactions
- **Flexible Item System**: Trade, give, and request items through natural dialogue
- **Adaptive NPCs**: Character dispositions change based on your interactions
- **Victory Conditions**: Each scenario has unique objectives to achieve
- **Beautiful Console Interface**: Rich text formatting and intuitive displays
- **Multiple AI Models**: Support for OpenAI, Anthropic, and local models via LiteLLM
- **LLM Debug Mode**: Track AI invocations for development and understanding

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up API Key**:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

3. **Run the Game**:
   ```bash
   python main.py
   ```

4. **Enable Debug Mode** (optional):
   ```bash
   python main.py --debug
   # or
   export AIGAME_DEBUG=true
   python main.py
   ```

## Debug Mode

The game includes a comprehensive debug system that tracks all LLM invocations. When enabled, you'll see concise messages showing:

- Which component is making an LLM call
- The purpose of each call
- The model being used
- The order of operations

**Enable Debug Mode:**
- Command line: `python main.py --debug` or `python main.py -d`
- Environment variable: `export AIGAME_DEBUG=true`
- **In-game toggle**: Type `debug` in the scenario selection menu to toggle debug mode on/off

**Example Debug Output:**
```
🤖 LLM Call: InputParser → Input classification [openai/gpt-4.1-mini]
🤖 LLM Call: Character → Dialogue generation for Keeper Dusttome [openai/gpt-4.1-mini]
🤖 LLM Call: GameMaster → Disposition analysis for Keeper Dusttome [openai/gpt-4.1-mini]
```

This helps developers understand the AI decision-making process and optimize performance.

## Running the Game

1. Ensure you have Python 3.12+ installed.
2. Install the necessary dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up your OpenAI API key:
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```
4. Run the game:
   ```bash
   python main.py
   ```

## Model Configuration

The game uses a global configuration system that makes it easy to switch between different AI models. By default, the game uses `openai/gpt-4.1-mini`, but you can easily change this.

### Changing the Model

**Option 1: Edit the configuration file (permanent change)**
```python
# Edit aigame/aigame_core/config.py
DEFAULT_LLM_MODEL = "openai/gpt-4o-mini"  # or any other supported model
```

**Option 2: Change programmatically (temporary change)**
```python
from aigame.aigame_core import config
config.DEFAULT_LLM_MODEL = "anthropic/claude-3-haiku-20240307"
```

### Supported Models

The game supports any model compatible with LiteLLM, including:
- **OpenAI**: `openai/gpt-4.1-mini`, `openai/gpt-4o-mini`, `openai/gpt-3.5-turbo`
- **Anthropic**: `anthropic/claude-3-haiku-20240307`, `anthropic/claude-3-sonnet-20240229`
- **Local models**: `ollama/llama2`, `ollama/mistral` (requires Ollama setup)
- **Other providers**: See [LiteLLM documentation](https://docs.litellm.ai/docs/providers) for full list

### Testing Model Changes

Run the included example script to see how model configuration works:
```bash
python change_model_example.py
```

**Note**: Different models may have varying performance characteristics. GPT-4 models generally provide the best results for complex natural language understanding, while smaller models like GPT-3.5-turbo or Claude Haiku offer faster responses at lower cost.

## Example Gameplay

```
Alex the Scholar: Hello there, how are you?
🤖 LLM Call: InputParser → Input classification [openai/gpt-4.1-mini]
🤖 LLM Call: Character → Dialogue generation for Archivist Silas [openai/gpt-4.1-mini]

Archivist Silas: Greetings! I am well, though I seek a translation cypher for my research.

Alex the Scholar: I have a translation cypher! Would you like to trade for your key?
🤖 LLM Call: InputParser → Input classification [openai/gpt-4.1-mini]
🤖 LLM Call: GameMaster → Trade proposal parsing [openai/gpt-4.1-mini]
🤖 LLM Call: Character → Trade decision for Archivist Silas [openai/gpt-4.1-mini]

Archivist Silas: Excellent! That cypher would be invaluable for my work. I accept your trade.
```

## Game Mechanics

### Natural Language Processing
- **Input Classification**: AI determines whether you're trying to talk, trade, give items, or perform other actions
- **Contextual Understanding**: The game understands references, implications, and natural speech patterns
- **Intelligent Fallbacks**: If the AI classifies an action that isn't valid in the current game state (e.g., accepting a trade when no trade exists), the code automatically converts it to dialogue, ensuring the conversation never breaks.

## Dependencies

- `litellm`: LLM API integration (supports OpenAI, Anthropic, and others)
- `rich`: Beautiful console output and formatting
- `pydantic`: Data validation and parsing

## Future Expansion

The game is designed for easy extension:
- Add new scenarios by creating JSON files in `data/scenarios/`
- Create new characters, items, and locations through JSON definitions
- Extend action types in the input parser for new game mechanics
- Add new victory condition types in the game master
- Implement new AI models through LiteLLM configuration

## Development

### Debug Mode for Development

The debug system is particularly useful for:
- Understanding AI decision flows
- Optimizing prompt engineering
- Debugging unexpected behavior
- Performance analysis
- Educational purposes

### Architecture

The game follows a modular architecture:
- **Game Loop**: Main game flow and state management
- **Characters**: AI-powered NPCs with dynamic personalities
- **Input Parser**: Natural language understanding for player commands
- **Game Master**: Scenario management and victory condition evaluation
- **Action Parser**: Extracts actions from NPC natural language responses

Each component that interacts with LLMs includes debug tracking for transparency.