from __future__ import annotations
import json
import litellm
from typing import Dict, Any, Optional
from rich import print as rprint
from rich.text import Text

from .player import Player
from .character import Character
from .location import Location


class InputParser:
    """
    AI-powered natural language input parser for the game.
    Uses a two-step process: classification then parameter extraction.
    """
    
    def __init__(self):
        pass
    
    def parse_player_input(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        current_location: Location
    ) -> Dict[str, Any]:
        """
        Parses natural language player input into structured commands.
        
        Returns a dictionary with:
        - 'action_type': str (dialogue, give_item, trade_proposal, accept_trade, decline_trade, quit, help, unknown)
        - 'parameters': dict with action-specific parameters
        - 'success': bool indicating if parsing was successful
        - 'error_message': str with error details if parsing failed
        """
        if not isinstance(player_input, str) or not player_input.strip():
            return {
                'action_type': 'unknown',
                'parameters': {},
                'success': False,
                'error_message': 'Input cannot be empty'
            }
        
        # Backward compatibility: Handle slash commands directly
        if player_input.strip().startswith('/'):
            return self._parse_slash_command(player_input.strip(), player, npc)
        
        # Step 1: Classify the input type
        classification = self._classify_input(player_input, player, npc, current_location)
        
        if not classification['success']:
            return {
                'action_type': 'unknown',
                'parameters': {},
                'success': False,
                'error_message': classification.get('error_message', 'Failed to classify input')
            }
        
        action_type = classification['action_type']
        
        # Step 2: Extract parameters based on classification
        # Add fallback logic for accept/decline when no valid trade exists
        if action_type == 'accept_trade':
            # Check if there's actually a valid trade to accept
            if not npc.active_trade_proposal or npc.active_trade_proposal.get("offered_by_name") != npc.name:
                # No valid trade to accept, treat as dialogue instead
                action_type = 'dialogue'
        elif action_type == 'decline_trade':
            # Check if there's actually a valid trade to decline
            if not npc.active_trade_proposal or npc.active_trade_proposal.get("offered_by_name") != npc.name:
                # No valid trade to decline, treat as dialogue instead
                action_type = 'dialogue'
        
        if action_type == 'dialogue':
            return self._extract_dialogue_parameters(player_input, classification)
        elif action_type == 'give_item':
            return self._extract_give_parameters(player_input, player, npc, classification)
        elif action_type == 'trade_proposal':
            return self._extract_trade_parameters(player_input, player, npc, classification)
        elif action_type == 'request_item':
            return self._extract_request_parameters(player_input, player, npc, classification)
        elif action_type == 'accept_trade':
            return self._extract_accept_parameters(player_input, npc, classification)
        elif action_type == 'decline_trade':
            return self._extract_decline_parameters(player_input, npc, classification)
        else:
            # Default unknown inputs to dialogue for more natural conversation
            return self._extract_dialogue_parameters(player_input, classification)
    
    def _parse_slash_command(self, player_input: str, player: Player, npc: Character) -> Dict[str, Any]:
        """
        Backward compatibility: Parse old-style slash commands.
        """
        # Remove the leading slash and split
        command_part = player_input[1:].strip()
        parts = command_part.split(maxsplit=1)
        command_verb = parts[0].lower()
        command_args = parts[1].strip() if len(parts) > 1 else ""
        
        if command_verb == "say":
            if not command_args:
                return {
                    'action_type': 'dialogue',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Message cannot be empty'
                }
            return {
                'action_type': 'dialogue',
                'parameters': {'message': command_args},
                'success': True,
                'error_message': ''
            }
        
        elif command_verb == "give":
            if not command_args:
                return {
                    'action_type': 'give_item',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Item name cannot be empty'
                }
            if not player.has_item(command_args):
                return {
                    'action_type': 'give_item',
                    'parameters': {},
                    'success': False,
                    'error_message': f"You don't have '{command_args}' to give"
                }
            return {
                'action_type': 'give_item',
                'parameters': {
                    'item_name': command_args,
                    'original_message': f"Here, take my {command_args}"
                },
                'success': True,
                'error_message': ''
            }
        
        elif command_verb == "trade":
            if not command_args:
                return {
                    'action_type': 'trade_proposal',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Trade proposal cannot be empty'
                }
            # Use the existing trade parsing logic
            return self._extract_trade_parameters(command_args, player, npc, {})
        
        elif command_verb == "request":
            if not command_args:
                return {
                    'action_type': 'request_item',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Item request cannot be empty'
                }
            # Use the existing request parsing logic
            return self._extract_request_parameters(command_args, player, npc, {})
        
        elif command_verb == "accept":
            return {
                'action_type': 'accept_trade',
                'parameters': {'custom_message': command_args if command_args else None},
                'success': True,
                'error_message': ''
            }
        
        elif command_verb == "decline":
            return {
                'action_type': 'decline_trade',
                'parameters': {'custom_message': command_args if command_args else None},
                'success': True,
                'error_message': ''
            }
        
        else:
            # Default unknown slash commands to dialogue for more natural conversation
            return {
                'action_type': 'dialogue',
                'parameters': {'message': player_input},
                'success': True,
                'error_message': ''
            }
    
    def _classify_input(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        current_location: Location
    ) -> Dict[str, Any]:
        """
        First step: Classify the type of input using AI.
        """
        # Get context for classification
        player_items = [item.name for item in player.items]
        npc_items = [item.name for item in npc.items]
        has_active_trade = bool(npc.active_trade_proposal)
        
        system_prompt = (
            "You are an AI that classifies player input in a text adventure game. "
            "Analyze the player's message and determine what type of action they want to perform. "
            "Focus on the player's intent, not game state validation. "
            "The possible action types are:\n"
            "- 'dialogue': Player wants to talk/speak to the NPC (greetings, questions, statements, etc.)\n"
            "- 'give_item': Player wants to offer/give an item to the NPC\n"
            "- 'trade_proposal': Player wants to propose trading items (offering one item for another)\n"
            "- 'request_item': Player wants to ask for a specific item without offering anything in return\n"
            "- 'accept_trade': Player wants to accept a trade or counter-proposal\n"
            "- 'decline_trade': Player wants to decline a trade or counter-proposal\n"
            "- 'unknown': Input doesn't clearly match any category\n\n"
            "Consider context clues like:\n"
            "- Words like 'say', 'tell', 'ask', 'hello' suggest dialogue\n"
            "- Words like 'give', 'offer', 'take this', 'here' suggest give_item\n"
            "- Words like 'trade', 'exchange', 'swap', 'for your' suggest trade_proposal\n"
            "- Words like 'can I have', 'please give me', 'I need', 'may I borrow' suggest request_item\n"
            "- Words like 'accept', 'yes', 'deal', 'agreed', 'okay', 'sure' suggest accept_trade\n"
            "- Words like 'decline', 'no', 'refuse', 'reject' suggest decline_trade\n\n"
            "Be flexible - players might phrase things naturally. For example:\n"
            "- 'Here, take my sword' = give_item\n"
            "- 'I'll trade my coins for your key' = trade_proposal\n"
            "- 'Can I have your map?' = request_item\n"
            "- 'I really need that potion' = request_item\n"
            "- 'Hello there, how are you?' = dialogue\n"
            "- 'Yes please' = accept_trade (if it sounds like agreement)\n"
            "- 'That sounds good, I accept' = accept_trade\n"
            "- 'No thanks' = decline_trade\n\n"
            "Respond ONLY with a JSON object containing:\n"
            "- 'action_type': one of the types listed above\n"
            "- 'confidence': number from 0.0 to 1.0 indicating confidence in classification\n"
            "- 'reasoning': brief explanation of why you chose this classification"
        )
        
        user_prompt = (
            f"Game Context:\n"
            f"- Player ({player.name}) has items: {player_items if player_items else ['None']}\n"
            f"- NPC ({npc.name}) has items: {npc_items if npc_items else ['None']}\n"
            f"- Location: {current_location.name}\n\n"
            f"Player input to classify: \"{player_input}\"\n\n"
            "What type of action does the player want to perform?"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.2,  # Low temperature for consistent classification
                response_format={"type": "json_object"}
            )
            
            raw_response = response.choices[0].message.content
            if not raw_response:
                return {'success': False, 'error_message': 'Empty response from classifier'}
            
            parsed = json.loads(raw_response)
            action_type = parsed.get('action_type', 'unknown')
            confidence = parsed.get('confidence', 0.0)
            reasoning = parsed.get('reasoning', '')
            
            # Log classification for debugging
            rprint(Text(f"Input classified as: {action_type} (confidence: {confidence:.2f})", style="dim cyan"))
            
            return {
                'success': True,
                'action_type': action_type,
                'confidence': confidence,
                'reasoning': reasoning
            }
            
        except json.JSONDecodeError as e:
            return {'success': False, 'error_message': f'JSON decode error: {e}'}
        except Exception as e:
            return {'success': False, 'error_message': f'Classification error: {e}'}
    
    def _extract_dialogue_parameters(self, player_input: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Extract parameters for dialogue action."""
        return {
            'action_type': 'dialogue',
            'parameters': {
                'message': player_input.strip()
            },
            'success': True,
            'error_message': ''
        }
    
    def _extract_give_parameters(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for give_item action."""
        system_prompt = (
            "You are extracting the item name from a player's give/offer message. "
            "The player wants to give an item to an NPC. Look for the specific item they mention. "
            "Match the mentioned item to the player's actual inventory, being flexible with naming "
            "(e.g., 'sword' might match 'Iron Sword', 'coins' might match 'Bag of Coins'). "
            "Respond ONLY with a JSON object containing:\n"
            "- 'item_name': exact name from player's inventory, or empty string if not found\n"
            "- 'confidence': number from 0.0 to 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        player_items = [item.name for item in player.items]
        user_prompt = (
            f"Player's inventory: {player_items}\n"
            f"Player's message: \"{player_input}\"\n\n"
            "What item is the player trying to give?"
        )
        
        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(response.choices[0].message.content)
            item_name = parsed.get('item_name', '')
            
            if not item_name:
                return {
                    'action_type': 'give_item',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Could not identify which item you want to give'
                }
            
            # Verify player has the item
            if not player.has_item(item_name):
                return {
                    'action_type': 'give_item',
                    'parameters': {},
                    'success': False,
                    'error_message': f"You don't have '{item_name}' to give"
                }
            
            return {
                'action_type': 'give_item',
                'parameters': {
                    'item_name': item_name,
                    'original_message': player_input
                },
                'success': True,
                'error_message': ''
            }
            
        except Exception as e:
            return {
                'action_type': 'give_item',
                'parameters': {},
                'success': False,
                'error_message': f'Error parsing give command: {e}'
            }
    
    def _extract_trade_parameters(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for trade_proposal action."""
        system_prompt = (
            "You are extracting trade details from a player's trade proposal message. "
            "The player wants to trade one of their items for one of the NPC's items. "
            "Look for what the player is offering and what they want in return. "
            "Match mentioned items to actual inventories, being flexible with naming. "
            "Respond ONLY with a JSON object containing:\n"
            "- 'player_item': exact name from player's inventory\n"
            "- 'npc_item': exact name from NPC's inventory\n"
            "- 'confidence': number from 0.0 to 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        player_items = [item.name for item in player.items]
        npc_items = [item.name for item in npc.items]
        
        user_prompt = (
            f"Player's inventory: {player_items}\n"
            f"NPC's inventory: {npc_items}\n"
            f"Player's trade message: \"{player_input}\"\n\n"
            "What trade is the player proposing? (What are they offering and what do they want?)"
        )
        
        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(response.choices[0].message.content)
            player_item = parsed.get('player_item', '')
            npc_item = parsed.get('npc_item', '')
            
            if not player_item or not npc_item:
                return {
                    'action_type': 'trade_proposal',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Could not identify the items you want to trade'
                }
            
            # Verify items exist
            if not player.has_item(player_item):
                return {
                    'action_type': 'trade_proposal',
                    'parameters': {},
                    'success': False,
                    'error_message': f"You don't have '{player_item}' to trade"
                }
            
            if not npc.has_item(npc_item):
                return {
                    'action_type': 'trade_proposal',
                    'parameters': {},
                    'success': False,
                    'error_message': f"The NPC doesn't have '{npc_item}' to trade"
                }
            
            return {
                'action_type': 'trade_proposal',
                'parameters': {
                    'player_item': player_item,
                    'npc_item': npc_item,
                    'original_message': player_input
                },
                'success': True,
                'error_message': ''
            }
            
        except Exception as e:
            return {
                'action_type': 'trade_proposal',
                'parameters': {},
                'success': False,
                'error_message': f'Error parsing trade proposal: {e}'
            }
    
    def _extract_request_parameters(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for request_item action."""
        system_prompt = (
            "You are extracting the item name from a player's request message. "
            "The player wants to ask for a specific item from the NPC without offering anything in return. "
            "Look for the specific item they mention. "
            "Match the mentioned item to the NPC's actual inventory, being flexible with naming "
            "(e.g., 'sword' might match 'Iron Sword', 'coins' might match 'Bag of Coins'). "
            "Respond ONLY with a JSON object containing:\n"
            "- 'item_name': exact name from NPC's inventory, or empty string if not found\n"
            "- 'confidence': number from 0.0 to 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        npc_items = [item.name for item in npc.items]
        user_prompt = (
            f"NPC's inventory: {npc_items}\n"
            f"Player's request message: \"{player_input}\"\n\n"
            "What item is the player asking for from the NPC?"
        )
        
        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            parsed = json.loads(response.choices[0].message.content)
            item_name = parsed.get('item_name', '')
            
            if not item_name:
                return {
                    'action_type': 'request_item',
                    'parameters': {},
                    'success': False,
                    'error_message': 'Could not identify which item you want to ask for'
                }
            
            # Verify NPC has the item
            if not npc.has_item(item_name):
                return {
                    'action_type': 'request_item',
                    'parameters': {},
                    'success': False,
                    'error_message': f"The NPC doesn't have '{item_name}' to give"
                }
            
            return {
                'action_type': 'request_item',
                'parameters': {
                    'item_name': item_name,
                    'original_message': player_input
                },
                'success': True,
                'error_message': ''
            }
            
        except Exception as e:
            return {
                'action_type': 'request_item',
                'parameters': {},
                'success': False,
                'error_message': f'Error parsing request command: {e}'
            }
    
    def _extract_accept_parameters(
        self, 
        player_input: str, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for accept_trade action."""
        if not npc.active_trade_proposal:
            return {
                'action_type': 'accept_trade',
                'parameters': {},
                'success': False,
                'error_message': 'There is no active trade proposal to accept'
            }
        
        # Check if this is an NPC counter-proposal
        offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
        if offered_by_name != npc.name:
            return {
                'action_type': 'accept_trade',
                'parameters': {},
                'success': False,
                'error_message': 'There is no NPC counter-proposal to accept'
            }
        
        return {
            'action_type': 'accept_trade',
            'parameters': {
                'custom_message': player_input.strip() if player_input.strip() else None
            },
            'success': True,
            'error_message': ''
        }
    
    def _extract_decline_parameters(
        self, 
        player_input: str, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for decline_trade action."""
        if not npc.active_trade_proposal:
            return {
                'action_type': 'decline_trade',
                'parameters': {},
                'success': False,
                'error_message': 'There is no active trade proposal to decline'
            }
        
        # Check if this is an NPC counter-proposal
        offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
        if offered_by_name != npc.name:
            return {
                'action_type': 'decline_trade',
                'parameters': {},
                'success': False,
                'error_message': 'There is no NPC counter-proposal to decline'
            }
        
        return {
            'action_type': 'decline_trade',
            'parameters': {
                'custom_message': player_input.strip() if player_input.strip() else None
            },
            'success': True,
            'error_message': ''
        } 