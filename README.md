# AI Text Adventure Game

This project is a Python-based text adventure game driven by Large Language Models (LLMs) with natural language interaction.

## Overview

The game allows players to interact with non-player characters (NPCs) and the game world through **natural language** - no commands or special syntax required. Both player input and NPC responses are powered by AI, providing dynamic and engaging gameplay. 

### Key Features

- **Natural Language Player Input**: Type naturally - "Hello there!", "Here, take my sword", "I'll trade my coins for your key"
- **AI-Powered NPC Actions**: NPCs can perform actions through natural dialogue - "Here, take this ring - you've earned it!"
- **Dynamic Character Interactions**: NPCs respond contextually with changing dispositions and behaviors
- **Flexible Item Trading**: Propose, accept, decline, and counter-propose trades through conversation
- **AI Game Master**: Evaluates victory conditions and provides narrative epilogues
- **Scenario-Based Gameplay**: Structured adventures with defined objectives and victory conditions

### Technical Highlights

- **Two-Step AI Parsing**: Input classification followed by parameter extraction for reliable natural language understanding
- **Intelligent Fallbacks**: Code-level validation ensures graceful handling of edge cases
- **Clean Architecture**: Clear separation between AI responsibilities (understanding intent) and code responsibilities (game state validation)
- **Debug-Friendly**: Optional classification logging for development and testing

## Status

**The core natural language interaction system is complete and functional.** The game successfully demonstrates:
- ✅ Natural language player input parsing
- ✅ AI-powered NPC action extraction from dialogue
- ✅ Dynamic trading and item management
- ✅ Victory condition evaluation
- ✅ Complete game scenarios

The project is ready for expansion with additional scenarios, characters, and game mechanics.

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
Input classified as: dialogue (confidence: 0.95)

Archivist Silas: Greetings! I am well, though I seek a translation cypher for my research.
NPC response classified as: dialogue_only (confidence: 1.00)

Alex the Scholar: Here, take my translation cypher
Input classified as: give_item (confidence: 0.95)
💝 You offer the translation cypher to Archivist Silas

Archivist Silas: Excellent! In return, let me give you this Echo Chamber Key.
NPC actions detected: ['accept_offer', 'give_item'] (confidence: 0.95)
✅ Archivist Silas accepts your translation cypher
🎁 Archivist Silas gives you the Echo Chamber Key

🎉 SUCCESS! Victory condition achieved!
```

## Project Structure

- `main.py`: Main entry point with scenario selection
- `aigame/aigame_core/`: Core game logic modules:
  - `game_loop.py`: Main game interaction flow and UI
  - `input_parser.py`: **AI-powered natural language input parsing**
  - `npc_action_parser.py`: **AI-powered NPC action extraction from dialogue**
  - `character.py`: NPC and player character logic with AI response generation
  - `player.py`: Player class and inventory management
  - `game_master.py`: AI Game Master for narrative and victory evaluation
  - `item.py`: Item properties and behavior
  - `location.py`: Game location definitions
  - `scenario.py`: Scenario structure and loading
  - `interaction_history.py`: Conversation history management
- `aigame/data/`: JSON data files for game entities:
  - `characters/`: Character definitions with personality, goals, and starting items
  - `items/`: Item definitions with names and descriptions
  - `locations/`: Location definitions with names and descriptions
  - `scenarios/`: Scenario definitions with victory conditions and entity references
- `requirements.txt`: Python package dependencies

## Architecture

The game uses a **two-step AI parsing approach**:

1. **Classification**: AI determines the type of action the player wants to perform
2. **Parameter Extraction**: AI extracts specific details (item names, trade terms, etc.)

**Intelligent Fallbacks**: If the AI classifies an action that isn't valid in the current game state (e.g., accepting a trade when no trade exists), the code automatically converts it to dialogue, ensuring the conversation never breaks.

## Dependencies

- `litellm`: LLM API integration (supports OpenAI, Anthropic, and others)
- `rich`: Beautiful console output and formatting
- `pydantic`: Data validation and parsing

## Future Expansion

The game is designed for easy extension:
- Add new scenarios by creating JSON files in `aigame/data/scenarios/`
- Create new characters, items, and locations through JSON definitions
- Extend action types in the input parser for new game mechanics
- Add new victory condition types in the game master