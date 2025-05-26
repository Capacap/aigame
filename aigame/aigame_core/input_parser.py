from __future__ import annotations
import json
import litellm
from typing import Dict, Any, Optional
from rich import print as rprint
from rich.text import Text
from .config import DEFAULT_LLM_MODEL, debug_llm_call

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
        Uses AI to classify the type of player input.
        Returns classification result with action_type, confidence, and reasoning.
        """
        
        # Build context for classification
        player_items = [item.name for item in player.items]
        npc_items = [item.name for item in npc.items]
        
        # Check for active proposals that might affect classification
        has_active_trade_proposal = bool(npc.active_trade_proposal)
        
        system_prompt = (
            "You are an expert natural language classifier for a text-based adventure game. "
            "Your task is to classify player input into specific action types.\n\n"
            "AVAILABLE ACTION TYPES:\n"
            "- 'dialogue': General conversation, questions, comments, or statements\n"
            "- 'give_item': Player wants to give/offer one of their items to the NPC\n"
            "- 'trade_proposal': Player proposes trading one of their items for one of NPC's items\n"
            "- 'request_item': Player asks for or wants one of the NPC's items (without offering anything)\n"
            "- 'accept_trade': Player accepts a trade proposal (only valid if there's an active proposal)\n"
            "- 'decline_trade': Player declines a trade proposal (only valid if there's an active proposal)\n"
            "- 'quit': Player wants to quit/exit the game\n"
            "- 'help': Player wants help or instructions\n"
            "- 'unknown': Input doesn't fit any category or is unclear\n\n"
            "CLASSIFICATION GUIDELINES:\n"
            "- Be generous with 'dialogue' - when in doubt, classify as dialogue\n"
            "- 'give_item' requires clear intent to give/offer something\n"
            "- 'trade_proposal' requires mentioning both what player offers AND what they want\n"
            "- 'request_item' is asking for something without offering anything in return\n"
            "- 'accept_trade'/'decline_trade' only if there's an active trade proposal\n"
            "- Consider context and be flexible with natural language variations\n\n"
            "Respond with JSON containing:\n"
            "- 'action_type': one of the types above\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "- 'reasoning': brief explanation of your classification"
        )
        
        user_prompt = (
            f"GAME CONTEXT:\n"
            f"Player items: {player_items}\n"
            f"NPC items: {npc_items}\n"
            f"Active trade proposal: {has_active_trade_proposal}\n"
            f"Location: {current_location.name}\n\n"
            f"PLAYER INPUT TO CLASSIFY:\n"
            f'"{player_input}"\n\n'
            f"Classify this input into one of the action types."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        debug_llm_call("InputParser", "Input classification", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
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
            'error_message': '',
            'confidence': classification.get('confidence', 0.0),
            'reasoning': classification.get('reasoning', '')
        }
    
    def _extract_give_parameters(
        self, 
        player_input: str, 
        player: Player, 
        npc: Character, 
        classification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract parameters for give_item action."""
        
        player_items = [item.name for item in player.items]
        
        system_prompt = (
            "You are an item extraction specialist. Extract the specific item name that the player "
            "wants to give/offer to the NPC from their natural language input.\n\n"
            "GUIDELINES:\n"
            "- Extract the EXACT item name as it appears in the player's inventory\n"
            "- Be flexible with partial matches (e.g., 'coins' matches 'Bag of Coins')\n"
            "- If multiple items could match, choose the most likely one\n"
            "- If no clear item can be identified, return empty string\n\n"
            "Respond with JSON containing:\n"
            "- 'item_name': exact name from inventory or empty string\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        user_prompt = (
            f"Player inventory: {player_items}\n"
            f"Player input: \"{player_input}\"\n\n"
            f"What item does the player want to give?"
        )
        
        debug_llm_call("InputParser", "Give item extraction", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
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
                'error_message': '',
                'confidence': parsed.get('confidence', 0.0),
                'reasoning': parsed.get('reasoning', '')
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
        
        player_items = [item.name for item in player.items]
        npc_items = [item.name for item in npc.items]
        
        system_prompt = (
            "You are a trade proposal analyzer. Extract the two items involved in a trade proposal: "
            "what the player is offering and what they want from the NPC.\n\n"
            "GUIDELINES:\n"
            "- Extract EXACT item names as they appear in inventories\n"
            "- Be flexible with partial matches\n"
            "- Player item must be from player inventory\n"
            "- NPC item must be from NPC inventory\n"
            "- If either item can't be clearly identified, return empty strings\n\n"
            "Respond with JSON containing:\n"
            "- 'player_item': exact name from player inventory\n"
            "- 'npc_item': exact name from NPC inventory\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        user_prompt = (
            f"Player inventory: {player_items}\n"
            f"NPC inventory: {npc_items}\n"
            f"Player input: \"{player_input}\"\n\n"
            f"What trade is the player proposing?"
        )
        
        debug_llm_call("InputParser", "Trade proposal extraction", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
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
                'error_message': '',
                'confidence': parsed.get('confidence', 0.0),
                'reasoning': parsed.get('reasoning', '')
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
        
        npc_items = [item.name for item in npc.items]
        
        system_prompt = (
            "You are an item request analyzer. Extract the specific item that the player "
            "is asking for from the NPC.\n\n"
            "GUIDELINES:\n"
            "- Extract the EXACT item name as it appears in the NPC's inventory\n"
            "- Be flexible with partial matches\n"
            "- If multiple items could match, choose the most likely one\n"
            "- If no clear item can be identified, return empty string\n\n"
            "Respond with JSON containing:\n"
            "- 'item_name': exact name from NPC inventory or empty string\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "- 'reasoning': brief explanation"
        )
        
        user_prompt = (
            f"NPC inventory: {npc_items}\n"
            f"Player input: \"{player_input}\"\n\n"
            f"What item is the player asking for?"
        )
        
        debug_llm_call("InputParser", "Request item extraction", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
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
                'error_message': '',
                'confidence': parsed.get('confidence', 0.0),
                'reasoning': parsed.get('reasoning', '')
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
            'error_message': '',
            'confidence': classification.get('confidence', 0.0),
            'reasoning': classification.get('reasoning', '')
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
            'error_message': '',
            'confidence': classification.get('confidence', 0.0),
            'reasoning': classification.get('reasoning', '')
        } 