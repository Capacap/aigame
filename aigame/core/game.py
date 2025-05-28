# variable to hold the current game state

# dataframe to hold character data

import json
import pandas as pd
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from collections import deque
import datetime
from enum import Enum

# Fix imports when running directly
import sys
import os
if __name__ == "__main__":
    # Add project root to Python path when running directly
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sys.path.insert(0, project_root)


class EventCategory(Enum):
    """Main event categories"""
    SYSTEM = "system"
    GAMEPLAY = "gameplay"
    CHARACTER = "character"
    DIALOGUE = "dialogue"
    COMBAT = "combat"
    INVENTORY = "inventory"
    WORLD = "world"


class SystemEventType(Enum):
    """System-level events"""
    GAME_INIT = "game_init"
    GAME_START = "game_start"
    GAME_END = "game_end"
    CHARACTER_LOADED = "character_loaded"
    SCENE_LOADED = "scene_loaded"
    SAVE_GAME = "save_game"
    LOAD_GAME = "load_game"
    ERROR = "error"


class GameplayEventType(Enum):
    """Gameplay mechanics events"""
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ROUND_START = "round_start"
    ROUND_END = "round_end"
    DECISION_QUEUED = "decision_queued"
    DECISION_PROCESSED = "decision_processed"
    ACTION_TAKEN = "action_taken"
    SKILL_CHECK = "skill_check"


class CharacterEventType(Enum):
    """Character-specific events"""
    CHARACTER_ENTER = "character_enter"
    CHARACTER_EXIT = "character_exit"
    CHARACTER_MOVE = "character_move"
    STATUS_CHANGE = "status_change"
    HEALTH_CHANGE = "health_change"
    LEVEL_UP = "level_up"
    DEATH = "death"
    REVIVAL = "revival"


class DialogueEventType(Enum):
    """Dialogue and conversation events"""
    DIALOGUE_START = "dialogue_start"
    DIALOGUE_SPEAK = "dialogue_speak"
    DIALOGUE_RESPONSE = "dialogue_response"
    DIALOGUE_END = "dialogue_end"
    MONOLOGUE = "monologue"
    WHISPER = "whisper"
    SHOUT = "shout"


class CombatEventType(Enum):
    """Combat-related events"""
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"
    ATTACK = "attack"
    DEFEND = "defend"
    SPELL_CAST = "spell_cast"
    DAMAGE_DEALT = "damage_dealt"
    DAMAGE_RECEIVED = "damage_received"


class InventoryEventType(Enum):
    """Inventory and item events"""
    ITEM_ACQUIRED = "item_acquired"
    ITEM_LOST = "item_lost"
    ITEM_USED = "item_used"
    ITEM_EQUIPPED = "item_equipped"
    ITEM_UNEQUIPPED = "item_unequipped"
    TRADE_INITIATED = "trade_initiated"
    TRADE_COMPLETED = "trade_completed"


class WorldEventType(Enum):
    """World and environment events"""
    LOCATION_DISCOVERED = "location_discovered"
    WEATHER_CHANGE = "weather_change"
    TIME_CHANGE = "time_change"
    QUEST_START = "quest_start"
    QUEST_COMPLETE = "quest_complete"
    TRIGGER_ACTIVATED = "trigger_activated"


@dataclass
class GameState:
    """Holds the current game state including character data and turn order"""
    characters_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    events_df: pd.DataFrame = field(default_factory=pd.DataFrame)
    current_turn: int = 0
    turn_order: List[str] = field(default_factory=list)
    scene_characters: List[str] = field(default_factory=list)
    decision_queues: Dict[str, deque] = field(default_factory=dict)
    
    def get_current_character(self) -> Optional[str]:
        """Get the name of the character whose turn it is"""
        if not self.turn_order:
            return None
        return self.turn_order[self.current_turn % len(self.turn_order)]
    
    def advance_turn(self):
        """Move to the next character's turn"""
        if self.turn_order:
            self.current_turn = (self.current_turn + 1) % len(self.turn_order)


class GameEngine:
    """Main game engine handling character data and turn management"""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)
        self.game_state = GameState()
        self._initialize_events_df()
        
    def _initialize_events_df(self):
        """Initialize the events DataFrame with proper columns"""
        self.game_state.events_df = pd.DataFrame(columns=[
            'event_id', 'timestamp', 'turn_number', 'category', 'event_type', 
            'character', 'content', 'targets', 'metadata', 'severity'
        ])
        
    def print_events(self, category: EventCategory = None, event_type: Enum = None, 
                    character: str = None, last_n_events: int = None, truncate_lines: int = None):
        """Print events line by line with optional filtering and truncation"""
        events = self.game_state.events_df.copy()
        
        if category:
            events = events[events['category'] == category.value]
        if event_type:
            events = events[events['event_type'] == event_type.value]
        if character:
            events = events[events['character'] == character]
        if last_n_events:
            events = events.tail(last_n_events)
        
        for _, event in events.iterrows():
            timestamp = event['timestamp'].strftime('%H:%M:%S') if pd.notna(event['timestamp']) else 'N/A'
            content = event['content']
            
            if truncate_lines and len(content) > truncate_lines:
                content = content[:truncate_lines] + "..."
            
            print(f"[{timestamp}] {event['category'].upper()}: {event['character']} - {content}")
        
    def load_character_data(self, character_names: List[str] = None) -> pd.DataFrame:
        """Load character data from JSON files into a DataFrame"""
        characters_dir = self.data_path / "characters"
        
        if not characters_dir.exists():
            raise FileNotFoundError(f"Characters directory not found: {characters_dir}")
        
        character_files = list(characters_dir.glob("*.json"))
        
        if character_names:
            character_files = [
                f for f in character_files 
                if f.stem in character_names or any(name in f.stem for name in character_names)
            ]
        
        character_files = character_files[:5]
        
        characters_data = []
        for char_file in character_files:
            try:
                with open(char_file, 'r') as f:
                    char_data = json.load(f)
                    char_data['file_name'] = char_file.stem
                    characters_data.append(char_data)
                    
                    # Add character loaded event
                    self.add_event(
                        category=EventCategory.SYSTEM,
                        event_type=SystemEventType.CHARACTER_LOADED,
                        character=char_data['name'],
                        content=f"Character {char_data['name']} loaded from {char_file.name}",
                        metadata={
                            'file_path': str(char_file),
                            'disposition': char_data.get('disposition', 'unknown'),
                            'items_count': len(char_data.get('items', []))
                        }
                    )
                    
            except (json.JSONDecodeError, FileNotFoundError) as e:
                self.add_event(
                    category=EventCategory.SYSTEM,
                    event_type=SystemEventType.ERROR,
                    character='system',
                    content=f"Failed to load character from {char_file}: {str(e)}",
                    severity='error'
                )
                continue
        
        if not characters_data:
            raise ValueError("No valid character data found")
        
        df = pd.DataFrame(characters_data)
        df['current_hp'] = 100
        df['status'] = 'active'
        df['location'] = 'scene'
        df['last_action'] = None
        
        return df
    
    def add_event(self, category: EventCategory, event_type: Enum, character: str, 
                  content: str, targets: List[str] = None, metadata: Dict[str, Any] = None,
                  severity: str = 'info'):
        """Add a new event to the events DataFrame with proper taxonomy"""
        event_id = len(self.game_state.events_df) + 1
        timestamp = datetime.datetime.now()
        
        new_event = {
            'event_id': event_id,
            'timestamp': timestamp,
            'turn_number': self.game_state.current_turn + 1,
            'category': category.value,
            'event_type': event_type.value,
            'character': character,
            'content': content,
            'targets': targets or [],
            'metadata': metadata or {},
            'severity': severity
        }
        
        # Use loc to add the new row instead of concat to avoid FutureWarning
        new_index = len(self.game_state.events_df)
        self.game_state.events_df.loc[new_index] = new_event
        
        return event_id
    
    def get_events_by_category(self, category: EventCategory, last_n_events: int = None) -> pd.DataFrame:
        """Get events by category"""
        events = self.game_state.events_df[
            self.game_state.events_df['category'] == category.value
        ].copy()
        
        if last_n_events:
            events = events.tail(last_n_events)
        
        return events
    
    def get_dialogue_history(self, character_filter: List[str] = None, 
                           last_n_events: int = None) -> pd.DataFrame:
        """Get dialogue events from the events DataFrame"""
        dialogue_events = self.game_state.events_df[
            self.game_state.events_df['category'] == EventCategory.DIALOGUE.value
        ].copy()
        
        if character_filter:
            dialogue_events = dialogue_events[
                dialogue_events['character'].isin(character_filter)
            ]
        
        if last_n_events:
            dialogue_events = dialogue_events.tail(last_n_events)
        
        return dialogue_events
    
    def get_events_by_type(self, event_type: Enum, last_n_events: int = None) -> pd.DataFrame:
        """Get events of a specific type"""
        events = self.game_state.events_df[
            self.game_state.events_df['event_type'] == event_type.value
        ].copy()
        
        if last_n_events:
            events = events.tail(last_n_events)
        
        return events
    
    def get_character_events(self, character: str, category: EventCategory = None, 
                           event_type: Enum = None) -> pd.DataFrame:
        """Get all events for a specific character"""
        events = self.game_state.events_df[
            self.game_state.events_df['character'] == character
        ].copy()
        
        if category:
            events = events[events['category'] == category.value]
            
        if event_type:
            events = events[events['event_type'] == event_type.value]
        
        return events
    
    def get_system_events(self, event_type: SystemEventType = None) -> pd.DataFrame:
        """Get system events"""
        events = self.get_events_by_category(EventCategory.SYSTEM)
        
        if event_type:
            events = events[events['event_type'] == event_type.value]
        
        return events
    
    def initialize_game(self, character_names: List[str] = None):
        """Initialize the game with character data and set up turn order"""
        # Add game initialization event
        self.add_event(
            category=EventCategory.SYSTEM,
            event_type=SystemEventType.GAME_INIT,
            character='system',
            content="Game engine initialized",
            metadata={'data_path': str(self.data_path)}
        )
        
        self.game_state.characters_df = self.load_character_data(character_names)
        self.game_state.turn_order = self.game_state.characters_df['name'].tolist()
        self.game_state.scene_characters = self.game_state.turn_order.copy()
        
        for char_name in self.game_state.turn_order:
            self.game_state.decision_queues[char_name] = deque()
            
            # Add character enter scene event
            self.add_event(
                category=EventCategory.CHARACTER,
                event_type=CharacterEventType.CHARACTER_ENTER,
                character=char_name,
                content=f"{char_name} enters the scene",
                metadata={'location': 'scene'}
            )
        
        # Add game start event
        self.add_event(
            category=EventCategory.SYSTEM,
            event_type=SystemEventType.GAME_START,
            character='system',
            content=f"Game started with {len(self.game_state.turn_order)} characters",
            metadata={
                'character_count': len(self.game_state.turn_order),
                'characters': self.game_state.turn_order
            }
        )
    
    def get_character_data(self, character_name: str) -> Optional[pd.Series]:
        """Get data for a specific character"""
        mask = self.game_state.characters_df['name'] == character_name
        if mask.any():
            return self.game_state.characters_df[mask].iloc[0]
        return None
    
    def get_other_characters(self, current_character: str) -> pd.DataFrame:
        """Get data for all characters except the current one"""
        return self.game_state.characters_df[
            self.game_state.characters_df['name'] != current_character
        ]
    
    def queue_decision(self, character_name: str, decision: Dict[str, Any]):
        """Add a decision to a character's queue"""
        if character_name in self.game_state.decision_queues:
            self.game_state.decision_queues[character_name].append(decision)
            
            # Add decision queue event
            self.add_event(
                category=EventCategory.GAMEPLAY,
                event_type=GameplayEventType.DECISION_QUEUED,
                character=character_name,
                content=f"Decision queued: {decision.get('type', 'unknown')}",
                metadata=decision
            )
    
    def process_queued_decisions(self, character_name: str) -> List[Dict[str, Any]]:
        """Process and return all queued decisions for a character"""
        if character_name not in self.game_state.decision_queues:
            return []
        
        decisions = []
        queue = self.game_state.decision_queues[character_name]
        
        while queue:
            decision = queue.popleft()
            decisions.append(decision)
            
            # Add decision processing event
            self.add_event(
                category=EventCategory.GAMEPLAY,
                event_type=GameplayEventType.DECISION_PROCESSED,
                character=character_name,
                content=f"Processed decision: {decision.get('type', 'unknown')}",
                metadata=decision
            )
        
        return decisions
    
    def take_character_action(self, character_name: str) -> Dict[str, Any]:
        """Generate a new action for the character"""
        char_data = self.get_character_data(character_name)
        other_chars = self.get_other_characters(character_name)
        recent_dialogue = self.get_dialogue_history(last_n_events=5)

        try:
            from .ai_inference import generate_text_response
            from .config import config
        except ImportError:
            # Fallback for when running directly
            from aigame.core.ai_inference import generate_text_response
            from aigame.core.config import config

        messages = []

        system_message_content = (
            "You are a character in a text-based RPG. Your role is to generate authentic dialogue "
            "that reflects the character's personality, goals, and current situation. "
            "\n\nGuidelines:"
            "\n- Stay true to the character's personality and disposition"
            "\n- Consider the character's goals and motivations"
            "\n- Respond naturally to recent dialogue from other characters"
            "\n- Keep responses concise (1-2 sentences max)"
            "\n- Use dialogue that feels natural and engaging"
            "\n- Show personality through word choice and tone"
            "\n- Avoid exposition; focus on character voice"
        )

        # Format recent dialogue for better context
        dialogue_context = "None"
        if not recent_dialogue.empty:
            dialogue_lines = []
            for _, event in recent_dialogue.iterrows():
                dialogue_lines.append(f"{event['character']}: \"{event['content']}\"")
            dialogue_context = "\n".join(dialogue_lines)

        user_message_content = (
            f"## CHARACTER TO PLAY\n"
            f"**Name:** {char_data['name']}\n"
            f"**Personality:** {char_data['personality']}\n"
            f"**Items:** {', '.join(char_data.get('items', []))}\n"
            f"\n## OTHER CHARACTERS PRESENT\n"
            f"{', '.join(other_chars['name'].tolist()) if not other_chars.empty else 'None'}\n"
            f"\n## RECENT CONVERSATION\n"
            f"{dialogue_context}\n"
            f"\n## TASK\n"
            f"Generate a single line of dialogue for {char_data['name']} that:"
            f"\n- Reflects their {char_data['disposition']} disposition"
            f"\n- Advances their goal: {char_data['goal']}"
            f"\n- Responds naturally to the conversation context"
            f"\n\nRespond with ONLY the dialogue (no quotes, no character name prefix)."
        )

        messages.append({
            "role": "system",
            "content": system_message_content
        })

        messages.append({
            "role": "user",
            "content": user_message_content
        })

        try:
            response = generate_text_response(messages, config, temperature=0.8, max_tokens=100)
            dialogue_content = response["content"].strip()
            
            # Clean up any unwanted formatting
            dialogue_content = dialogue_content.strip('"\'')
            if dialogue_content.startswith(f"{character_name}:"):
                dialogue_content = dialogue_content[len(f"{character_name}:"):].strip()
                
        except Exception as e:
            # Fallback to simple dialogue if AI fails
            dialogue_content = f"*{character_name} speaks with a {char_data['disposition']} tone*"

        action = {
            'type': 'dialogue',
            'character': character_name,
            'disposition': char_data['disposition'],
            'content': dialogue_content,
            'targets': other_chars['name'].tolist() if not other_chars.empty else []
        }

        # Add dialogue event to events DataFrame
        self.add_event(
            category=EventCategory.DIALOGUE,
            event_type=DialogueEventType.DIALOGUE_SPEAK,
            character=character_name,
            content=dialogue_content,
            targets=action['targets'],
            metadata={'disposition': char_data['disposition'], 'turn': self.game_state.current_turn + 1}
        )

        # Add action taken event
        self.add_event(
            category=EventCategory.GAMEPLAY,
            event_type=GameplayEventType.ACTION_TAKEN,
            character=character_name,
            content=f"{character_name} took action: {action['type']}",
            metadata=action
        )

        mask = self.game_state.characters_df['name'] == character_name
        self.game_state.characters_df.loc[mask, 'last_action'] = action['type']

        return action
    
    def _generate_dialogue_content(self, character_name: str, disposition: str, 
                                 recent_dialogue: pd.DataFrame) -> str:
        """Generate dialogue content based on character and conversation history"""
        if recent_dialogue.empty:
            return f"{character_name} speaks with a {disposition} tone, starting the conversation."
        
        # Check if character has spoken recently
        char_recent_dialogue = recent_dialogue[recent_dialogue['character'] == character_name]
        
        if char_recent_dialogue.empty:
            return f"{character_name} joins the conversation with a {disposition} demeanor."
        else:
            return f"{character_name} continues speaking with {disposition} intent, building on the ongoing discussion."
    
    def execute_turn(self) -> Dict[str, Any]:
        """Execute a single character turn"""
        current_char = self.game_state.get_current_character()
        
        if not current_char:
            return {'error': 'No characters in turn order'}
        
        # Add turn start event
        self.add_event(
            category=EventCategory.GAMEPLAY,
            event_type=GameplayEventType.TURN_START,
            character=current_char,
            content=f"{current_char} begins their turn",
            metadata={'turn_number': self.game_state.current_turn + 1}
        )
        
        processed_decisions = self.process_queued_decisions(current_char)
        new_action = self.take_character_action(current_char)
        
        # Add turn end event
        self.add_event(
            category=EventCategory.GAMEPLAY,
            event_type=GameplayEventType.TURN_END,
            character=current_char,
            content=f"{current_char} ends their turn",
            metadata={'actions_taken': 1, 'decisions_processed': len(processed_decisions)}
        )
        
        self.game_state.advance_turn()
        
        return {
            'character': current_char,
            'processed_decisions': processed_decisions,
            'new_action': new_action,
            'next_character': self.game_state.get_current_character()
        }
    
    def run_game_loop(self, max_turns: int = 10):
        """Run the main game loop for a specified number of turns"""
        for turn_num in range(max_turns):
            turn_result = self.execute_turn()
            
            if 'error' in turn_result:
                break
            
            if turn_num == 2:
                next_char = turn_result['next_character']
                if next_char:
                    self.queue_decision(next_char, {
                        'type': 'react_to_dialogue',
                        'trigger': turn_result['new_action']
                    })

    def analyze_conversation(self) -> Dict[str, Any]:
        """Analyze the conversation patterns and character interactions"""
        dialogue_events = self.get_dialogue_history()
        
        if dialogue_events.empty:
            return {"error": "No dialogue to analyze"}
        
        analysis = {
            "total_exchanges": len(dialogue_events),
            "characters": {},
            "conversation_flow": [],
            "themes": []
        }
        
        # Character participation analysis
        for character in self.game_state.turn_order:
            char_dialogue = dialogue_events[dialogue_events['character'] == character]
            char_data = self.get_character_data(character)
            
            analysis["characters"][character] = {
                "lines_spoken": len(char_dialogue),
                "disposition": char_data['disposition'],
                "goal": char_data['goal'],
                "avg_words_per_line": sum(len(line.split()) for line in char_dialogue['content']) / len(char_dialogue) if len(char_dialogue) > 0 else 0
            }
        
        # Conversation flow (who spoke to whom)
        for i, (_, event) in enumerate(dialogue_events.iterrows()):
            analysis["conversation_flow"].append({
                "turn": i + 1,
                "speaker": event['character'],
                "content_preview": event['content'][:50] + "..." if len(event['content']) > 50 else event['content']
            })
        
        return analysis

    def print_conversation_analysis(self):
        """Print a detailed analysis of the conversation"""
        analysis = self.analyze_conversation()
        
        if "error" in analysis:
            print(f"Analysis Error: {analysis['error']}")
            return
        
        print("\n" + "="*60)
        print("📊 CONVERSATION ANALYSIS")
        print("="*60)
        
        print(f"\n📈 Overview:")
        print(f"   Total exchanges: {analysis['total_exchanges']}")
        print(f"   Active characters: {len(analysis['characters'])}")
        
        print(f"\n👥 Character Participation:")
        for char_name, stats in analysis['characters'].items():
            participation = (stats['lines_spoken'] / analysis['total_exchanges']) * 100
            print(f"   {char_name:15} | {stats['lines_spoken']:2d} lines ({participation:4.1f}%) | {stats['disposition']:10} | Avg {stats['avg_words_per_line']:.1f} words/line")
        
        print(f"\n🔄 Conversation Flow:")
        for turn in analysis['conversation_flow']:
            print(f"   {turn['turn']:2d}. {turn['speaker']:15} → \"{turn['content_preview']}\"")
        
        print("="*60)


if __name__ == "__main__":
    print("This is the core game engine module.")
    print("Use 'python test_game_conversation.py' to run conversation tests.")
    print("Use 'python -m aigame.core.game' for module testing.")