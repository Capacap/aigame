import json
import os
from typing import List, Dict, Any, Optional


class Character:
    """Base class for all game characters."""
    
    def __init__(self, name: str, description: str = "", 
                 personality: str = "", goal: str = "", disposition: str = "", 
                 items: Optional[List[str]] = None):
        if not name:
            raise ValueError("Character name must be a non-empty string")
        
        self.name = name
        self.description = description
        self.personality = personality
        self.goal = goal
        self.disposition = disposition
        self.items = items or []
    
    @classmethod
    def from_json_file(cls, file_path: str):
        """Load a Character from a character JSON file."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Character file not found: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return cls.from_dict(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create a Character from a dictionary."""
        if 'name' not in data:
            raise ValueError("Character data must contain 'name' field")
        
        return cls(
            name=data['name'],
            personality=data.get('personality', ''),
            goal=data.get('goal', ''),
            disposition=data.get('disposition', ''),
            items=data.get('items', [])
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the Character to a dictionary."""
        return {
            'name': self.name,
            'personality': self.personality,
            'goal': self.goal,
            'disposition': self.disposition,
            'items': self.items.copy()
        }
    
    def add_item(self, item: str) -> None:
        """Add an item to the character's inventory."""
        if item and item not in self.items:
            self.items.append(item)
    
    def remove_item(self, item: str) -> bool:
        """Remove an item from the character's inventory."""
        if item in self.items:
            self.items.remove(item)
            return True
        return False
    
    def has_item(self, item: str) -> bool:
        """Check if the character has a specific item."""
        return item in self.items
    
    def get_full_description(self) -> str:
        """Get a comprehensive description of the character."""
        parts = [f"Name: {self.name}"]
        
        for attr, label in [
            ('personality', 'Personality'),
            ('goal', 'Goal'), 
            ('disposition', 'Disposition'),
            ('character_description', 'Description')
        ]:
            value = getattr(self, attr)
            if value:
                parts.append(f"{label}: {value}")
        
        if self.items:
            parts.append(f"Items: {', '.join(self.items)}")
        
        return "\n".join(parts)
    
    def __str__(self) -> str:
        """String representation of the character."""
        class_name = self.__class__.__name__
        return f"{class_name}(name='{self.name}', items={len(self.items)})"
    
    def __repr__(self) -> str:
        """Detailed string representation for debugging."""
        class_name = self.__class__.__name__
        return (f"{class_name}(character_name='{self.name}', "
                f"personality='{self.personality[:50]}...', "
                f"goal='{self.goal[:50]}...', "
                f"disposition='{self.disposition}', "
                f"items={self.items})")


class PlayerCharacter(Character):
    """Character controlled by the player."""
    pass


class AICharacter(Character):
    """Character controlled by AI."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._conversation_history: List[str] = []
    
    def add_to_conversation_history(self, message: str) -> None:
        """Add a message to the character's conversation history."""
        if message:
            self._conversation_history.append(message)
    
    def get_conversation_history(self) -> List[str]:
        """Get the character's conversation history."""
        return self._conversation_history.copy()
    
    def clear_conversation_history(self) -> None:
        """Clear the character's conversation history."""
        self._conversation_history.clear()
    
    def update_disposition(self, new_disposition: str) -> None:
        """Update the character's disposition based on interactions."""
        if new_disposition:
            self.disposition = new_disposition
    
    def get_ai_context(self) -> Dict[str, Any]:
        """Get context information for AI generation."""
        return {
            'name': self.name,
            'personality': self.personality,
            'goal': self.goal,
            'disposition': self.disposition,
            'items': self.items,
            'conversation_history': self._conversation_history
        }