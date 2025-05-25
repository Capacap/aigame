from __future__ import annotations
import json
import litellm
from typing import Dict, Any, List, Optional
from rich import print as rprint
from rich.text import Text
from rich.panel import Panel
from .config import DEFAULT_LLM_MODEL

from .player import Player
from .character import Character


class NPCActionParser:
    """
    AI-powered parser that extracts actions from NPC natural language responses.
    This allows NPCs to perform actions through natural dialogue rather than explicit tool calls.
    """
    
    def __init__(self, debug_mode: bool = True):
        self.debug_mode = debug_mode
    
    def _debug_print(self, message: str, style: str = "dim cyan"):
        """Print debug information if debug mode is enabled."""
        if self.debug_mode:
            rprint(Text(f"[NPC PARSER DEBUG] {message}", style=style))
    
    def parse_npc_response(
        self, 
        npc_response: str, 
        npc: Character, 
        player: Player,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Parses an NPC's natural language response to extract implied actions.
        
        Args:
            npc_response: The NPC's spoken response
            npc: The NPC character object
            player: The player object
            context: Additional context (active offers, trades, etc.)
        
        Returns:
            Dictionary with:
            - 'actions': List of action dictionaries
            - 'success': bool indicating if parsing was successful
            - 'error_message': str with error details if parsing failed
        """
        if not isinstance(npc_response, str) or not npc_response.strip():
            return {
                'actions': [],
                'success': True,
                'error_message': ''
            }
        
        context = context or {}
        
        # Extract actions using AI
        extracted_actions = self._extract_actions(npc_response, npc, player, context)
        
        if not extracted_actions['success']:
            if self.debug_mode:
                rprint(Text(f"NPC action parsing failed: {extracted_actions.get('error_message', 'Unknown error')}", style="dim red"))
            return {
                'actions': [],
                'success': False,
                'error_message': extracted_actions.get('error_message', 'Failed to parse NPC actions')
            }
        
        # Validate and filter actions
        valid_actions = []
        for action in extracted_actions['actions']:
            validation_result = self._validate_action(action, npc, player, context)
            if validation_result['valid']:
                valid_actions.append(action)
            else:
                rprint(Text(f"Invalid NPC action filtered out: {validation_result['reason']}", style="dim yellow"))
        
        # Show classification result like player input (always show, regardless of action type)
        if self.debug_mode and valid_actions:
            action_types = [action.get('type', 'unknown') for action in valid_actions]
            confidence = extracted_actions.get('confidence', 0.0)
            # Show all classifications, including dialogue_only
            if action_types[0] == 'dialogue_only':
                rprint(Text(f"NPC response classified as: dialogue_only (confidence: {confidence:.2f})", style="dim magenta"))
            else:
                rprint(Text(f"NPC actions detected: {action_types} (confidence: {confidence:.2f})", style="dim magenta"))
        
        return {
            'actions': valid_actions,
            'success': True,
            'error_message': '',
            'confidence': extracted_actions.get('confidence', 0.0),
            'action_types': [action.get('type', 'unknown') for action in valid_actions] if valid_actions else ['dialogue_only']
        }
    
    def _extract_actions(
        self, 
        npc_response: str, 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use AI to extract actions from NPC's natural language response.
        """
        # Prepare context information
        npc_items = [item.name for item in npc.items]
        player_items = [item.name for item in player.items]
        active_offer = context.get('active_offer')
        active_trade = context.get('active_trade_proposal')
        active_request = context.get('active_request')
        
        system_prompt = (
            "You are an AI that extracts actions from NPC dialogue in a text adventure game. "
            "Analyze the NPC's spoken response and identify any actions they are implying or performing. "
            "Focus on concrete actions that affect the game state, not just emotional expressions. "
            "Return a JSON object with 'actions' (list) and 'confidence' (0.0-1.0). "
            "Each action should have 'type' and 'parameters'. "
            "Action types: give_item, accept_offer, decline_offer, trade_accept, trade_decline, trade_counter, accept_request, decline_request, dialogue_only. "
            "For give_item: include 'item_name'. "
            "For trade_counter: include 'player_item' and 'npc_item'. "
            "For accept_request: include 'item_name' (item being given to fulfill request). "
            "For decline_request: no additional parameters needed. "
            "If no concrete actions are detected, return dialogue_only. "
            "Examples: "
            "'Here, take this ring' -> give_item with item_name='ring' "
            "'I accept your offer' -> accept_offer "
            "'I decline' -> decline_offer "
            "'How about my sword for your shield?' -> trade_counter "
            "'Sure, you can have it' -> accept_request "
            "'No, I need that myself' -> decline_request "
            "'Hello there' -> dialogue_only"
        )
        
        # Build context description
        context_desc = f"NPC ({npc.name}) inventory: {npc_items if npc_items else ['None']}\n"
        context_desc += f"Player ({player.name}) inventory: {player_items if player_items else ['None']}\n"
        
        if active_offer:
            offered_item = active_offer.get('item_name', 'unknown item')
            context_desc += f"Active offer: Player offered '{offered_item}' to NPC\n"
        else:
            context_desc += "Active offer: None\n"
        
        if active_trade:
            player_item = active_trade.get('player_item_name', 'unknown')
            npc_item = active_trade.get('npc_item_name', 'unknown')
            context_desc += f"Active trade proposal: Player's '{player_item}' for NPC's '{npc_item}'\n"
        else:
            context_desc += "Active trade proposal: None\n"
        
        if active_request:
            requested_item = active_request.get('item_name', 'unknown item')
            context_desc += f"Active request: Player asked for '{requested_item}' from NPC\n"
        else:
            context_desc += "Active request: None\n"
        
        user_prompt = (
            f"Game Context:\n{context_desc}\n"
            f"NPC's response: \"{npc_response}\"\n\n"
            "What actions is the NPC performing through this dialogue?"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                temperature=0.1,  # Low temperature for precise action extraction
                response_format={"type": "json_object"}
            )
            
            raw_response = response.choices[0].message.content
            if not raw_response:
                return {'success': False, 'error_message': 'Empty response from action extractor'}
            
            parsed = json.loads(raw_response)
            actions = parsed.get('actions', [])
            confidence = parsed.get('confidence', 0.0)
            reasoning = parsed.get('reasoning', '')
            
            # Log extraction for debugging (only for non-dialogue actions)
            if actions and actions[0].get('type') != 'dialogue_only':
                action_types = [action.get('type', 'unknown') for action in actions]
                rprint(Text(f"NPC actions extracted: {action_types} (confidence: {confidence:.2f})", style="dim magenta"))
            
            return {
                'success': True,
                'actions': actions,
                'confidence': confidence,
                'reasoning': reasoning
            }
            
        except json.JSONDecodeError as e:
            return {'success': False, 'error_message': f'JSON decode error: {e}'}
        except Exception as e:
            return {'success': False, 'error_message': f'Action extraction error: {e}'}
    
    def _validate_action(
        self, 
        action: Dict[str, Any], 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate that an extracted action is actually possible given the current game state.
        """
        action_type = action.get('type', '')
        parameters = action.get('parameters', {})
        
        if action_type == 'give_item':
            item_name = parameters.get('item_name', '')
            if not item_name:
                return {'valid': False, 'reason': 'give_item action missing item_name'}
            if not npc.has_item(item_name):
                return {'valid': False, 'reason': f"NPC doesn't have '{item_name}' to give"}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'accept_offer':
            active_offer = context.get('active_offer')
            if not active_offer:
                return {'valid': False, 'reason': 'No active offer to accept'}
            offered_item = active_offer.get('item_name', '')
            if not player.has_item(offered_item):
                return {'valid': False, 'reason': f"Player no longer has '{offered_item}' to offer"}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'decline_offer':
            active_offer = context.get('active_offer')
            if not active_offer:
                return {'valid': False, 'reason': 'No active offer to decline'}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'trade_accept':
            active_trade = context.get('active_trade_proposal')
            if not active_trade:
                return {'valid': False, 'reason': 'No active trade to accept'}
            # Verify both parties still have the items
            player_item = active_trade.get('player_item_object')
            npc_item = active_trade.get('npc_item_object')
            if not player.has_item(player_item):
                return {'valid': False, 'reason': 'Player no longer has trade item'}
            if not npc.has_item(npc_item):
                return {'valid': False, 'reason': 'NPC no longer has trade item'}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'trade_decline':
            active_trade = context.get('active_trade_proposal')
            if not active_trade:
                return {'valid': False, 'reason': 'No active trade to decline'}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'trade_counter':
            player_item = parameters.get('player_item', '')
            npc_item = parameters.get('npc_item', '')
            if not player_item or not npc_item:
                return {'valid': False, 'reason': 'trade_counter missing item names'}
            if not player.has_item(player_item):
                return {'valid': False, 'reason': f"Player doesn't have '{player_item}' for counter-trade"}
            if not npc.has_item(npc_item):
                return {'valid': False, 'reason': f"NPC doesn't have '{npc_item}' for counter-trade"}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'accept_request':
            item_name = parameters.get('item_name', '')
            if not item_name:
                return {'valid': False, 'reason': 'accept_request action missing item_name'}
            if not npc.has_item(item_name):
                return {'valid': False, 'reason': f"NPC doesn't have '{item_name}' to give"}
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'decline_request':
            return {'valid': True, 'reason': ''}
        
        elif action_type == 'dialogue_only':
            return {'valid': True, 'reason': ''}
        
        else:
            return {'valid': False, 'reason': f'Unknown action type: {action_type}'}
    
    def execute_actions(
        self, 
        actions: List[Dict[str, Any]], 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a list of validated NPC actions.
        
        Returns:
            Dictionary with execution results and any state changes.
        """
        results = {
            'executed_actions': [],
            'state_changes': {},
            'errors': []
        }
        
        for action in actions:
            try:
                result = self._execute_single_action(action, npc, player, context)
                if result['success']:
                    results['executed_actions'].append(action)
                    # Merge state changes
                    for key, value in result.get('state_changes', {}).items():
                        results['state_changes'][key] = value
                else:
                    results['errors'].append(result.get('error', 'Unknown execution error'))
            except Exception as e:
                results['errors'].append(f"Error executing {action.get('type', 'unknown')}: {e}")
        
        return results
    
    def _execute_single_action(
        self, 
        action: Dict[str, Any], 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single NPC action.
        """
        action_type = action.get('type', '')
        parameters = action.get('parameters', {})
        
        if action_type == 'give_item':
            item_name = parameters.get('item_name', '')
            # Find the actual item object
            item_obj = next((item for item in npc.items if item.name.lower() == item_name.lower()), None)
            if item_obj and npc.remove_item(item_obj):
                player.add_item(item_obj)
                return {
                    'success': True,
                    'state_changes': {'item_transferred': item_name}
                }
            return {'success': False, 'error': f"Failed to transfer '{item_name}'"}
        
        elif action_type == 'accept_offer':
            active_offer = context.get('active_offer', {})
            offered_item = active_offer.get('item_object')
            if offered_item and player.remove_item(offered_item):
                npc.add_item(offered_item)
                # Clear the offer
                npc.active_offer = None
                return {
                    'success': True,
                    'state_changes': {'offer_accepted': offered_item.name}
                }
            return {'success': False, 'error': 'Failed to accept offer'}
        
        elif action_type == 'decline_offer':
            # Clear the offer
            npc.active_offer = None
            return {
                'success': True,
                'state_changes': {'offer_declined': True}
            }
        
        elif action_type == 'trade_accept':
            active_trade = context.get('active_trade_proposal', {})
            player_item = active_trade.get('player_item_object')
            npc_item = active_trade.get('npc_item_object')
            
            if (player_item and npc_item and 
                player.remove_item(player_item) and npc.remove_item(npc_item)):
                player.add_item(npc_item)
                npc.add_item(player_item)
                # Clear the trade proposal
                npc.active_trade_proposal = None
                return {
                    'success': True,
                    'state_changes': {
                        'trade_completed': True,
                        'player_received': npc_item.name,
                        'npc_received': player_item.name
                    }
                }
            return {'success': False, 'error': 'Failed to execute trade'}
        
        elif action_type == 'trade_decline':
            # Clear the trade proposal
            npc.active_trade_proposal = None
            return {
                'success': True,
                'state_changes': {'trade_declined': True}
            }
        
        elif action_type == 'trade_counter':
            player_item_name = parameters.get('player_item', '')
            npc_item_name = parameters.get('npc_item', '')
            
            # Find the actual item objects
            player_item_obj = next((item for item in player.items if item.name.lower() == player_item_name.lower()), None)
            npc_item_obj = next((item for item in npc.items if item.name.lower() == npc_item_name.lower()), None)
            
            if player_item_obj and npc_item_obj:
                # Set up the counter-proposal
                npc.active_trade_proposal = {
                    "player_item_name": player_item_obj.name,
                    "npc_item_name": npc_item_obj.name,
                    "player_item_object": player_item_obj,
                    "npc_item_object": npc_item_obj,
                    "offered_by_name": npc.name,
                    "offered_by_object": npc
                }
                return {
                    'success': True,
                    'state_changes': {
                        'counter_proposal_made': True,
                        'counter_player_item': player_item_name,
                        'counter_npc_item': npc_item_name
                    }
                }
            return {'success': False, 'error': 'Failed to create counter-proposal'}
        
        elif action_type == 'accept_request':
            item_name = parameters.get('item_name', '')
            if not item_name:
                return {'success': False, 'error': 'accept_request action missing item_name'}
            
            # Find the actual item object
            item_obj = next((item for item in npc.items if item.name.lower() == item_name.lower()), None)
            if item_obj and npc.remove_item(item_obj):
                player.add_item(item_obj)
                # Clear the active request
                npc.active_request = None
                return {
                    'success': True,
                    'state_changes': {'request_accepted': item_name}
                }
            return {'success': False, 'error': f"Failed to transfer '{item_name}' for request"}
        
        elif action_type == 'decline_request':
            # Clear the active request
            npc.active_request = None
            return {
                'success': True,
                'state_changes': {'request_declined': True}
            }
        
        elif action_type == 'dialogue_only':
            return {'success': True, 'state_changes': {}}
        
        else:
            return {'success': False, 'error': f'Unknown action type: {action_type}'} 