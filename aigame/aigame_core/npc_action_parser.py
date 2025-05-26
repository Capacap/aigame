from __future__ import annotations
import json
import litellm
from typing import Dict, Any, List, Optional
from rich import print as rprint
from rich.text import Text
from rich.panel import Panel
from .config import DEFAULT_LLM_MODEL, debug_llm_call

from .player import Player
from .character import Character


class NPCActionParser:
    """
    AI-powered parser that extracts actions from NPC natural language responses.
    This allows NPCs to perform actions through natural dialogue rather than explicit tool calls.
    """
    
    def __init__(self, debug_mode: bool = False):
        # Keep the parameter for backward compatibility but don't use it
        pass
    
    def parse_npc_response(
        self, 
        npc_response: str, 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parses an NPC's natural language response to extract any actions they want to perform.
        
        Returns a dictionary with:
        - 'success': bool indicating if parsing was successful
        - 'actions': list of action dictionaries
        - 'error_message': str with error details if parsing failed
        """
        if not isinstance(npc_response, str) or not npc_response.strip():
            return {
                'success': False,
                'actions': [],
                'error_message': 'NPC response cannot be empty'
            }
        
        # Extract actions from the response
        extraction_result = self._extract_actions(npc_response, npc, player, context)
        
        if not extraction_result['success']:
            return {
                'success': False,
                'actions': [],
                'error_message': extraction_result['error_message']
            }
        
        actions = extraction_result['actions']
        confidence = extraction_result.get('confidence', 0.0)
        
        # Validate actions
        validated_actions = []
        for action in actions:
            if self._validate_action(action, npc, player, context):
                validated_actions.append(action)
        
        return {
            'success': True,
            'actions': validated_actions,
            'confidence': confidence,
            'error_message': ''
        }
    
    def _extract_actions(
        self, 
        npc_response: str, 
        npc: Character, 
        player: Player, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Uses AI to extract actions from the NPC's natural language response.
        """
        
        # Build context for action extraction
        npc_items = [item.name for item in npc.items]
        player_items = [item.name for item in player.items]
        
        # Check for active proposals
        active_offer = context.get('active_offer')
        active_trade_proposal = context.get('active_trade_proposal')
        active_request = context.get('active_request')
        
        system_prompt = (
            "You are an expert action extractor for NPCs in a text adventure game. "
            "Analyze the NPC's natural language response and identify any actions they want to perform.\n\n"
            "AVAILABLE ACTION TYPES:\n"
            "- 'give_item': NPC wants to give an item to the player\n"
            "- 'accept_offer': NPC accepts an item offer from the player\n"
            "- 'decline_offer': NPC declines an item offer from the player\n"
            "- 'accept_trade': NPC accepts a trade proposal\n"
            "- 'decline_trade': NPC declines a trade proposal\n"
            "- 'counter_trade': NPC proposes a different trade\n"
            "- 'dialogue_only': NPC is only speaking, no actions\n\n"
            "EXTRACTION GUIDELINES:\n"
            "- Look for explicit action words and intentions\n"
            "- Consider the context of active offers/trades\n"
            "- Be conservative - only extract clear actions\n"
            "- Most responses will be 'dialogue_only'\n"
            "- Multiple actions are possible but rare\n\n"
            "For each action, extract relevant parameters:\n"
            "- give_item: {'item_name': 'exact item name'}\n"
            "- accept_offer: {'item_name': 'item being accepted'}\n"
            "- accept_trade: {'player_item': 'item from player', 'npc_item': 'item from npc'}\n"
            "- counter_trade: {'player_item': 'what npc wants', 'npc_item': 'what npc offers'}\n\n"
            "Respond with JSON containing:\n"
            "- 'actions': list of action objects with 'type' and 'parameters'\n"
            "- 'confidence': float between 0.0 and 1.0\n"
            "- 'reasoning': brief explanation of extracted actions"
        )
        
        user_prompt = (
            f"GAME CONTEXT:\n"
            f"NPC: {npc.name}\n"
            f"NPC items: {npc_items}\n"
            f"Player items: {player_items}\n"
            f"Active offer: {active_offer is not None}\n"
            f"Active trade proposal: {active_trade_proposal is not None}\n"
            f"Active request: {active_request is not None}\n\n"
            f"NPC RESPONSE TO ANALYZE:\n"
            f'"{npc_response}"\n\n'
            f"What actions (if any) does the NPC want to perform?"
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        debug_llm_call("NPCActionParser", f"Action extraction for {npc.name}", DEFAULT_LLM_MODEL)
        
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
            
            # Validate that actions is a list of dictionaries, not strings
            validated_actions = []
            for action in actions:
                if isinstance(action, dict):
                    validated_actions.append(action)
                elif isinstance(action, str):
                    # Convert string action to proper dictionary format
                    validated_actions.append({'type': action, 'parameters': {}})
                else:
                    # Skip invalid action types
                    continue
            
            actions = validated_actions
            
            # Log extraction for debugging (only for non-dialogue actions)
            if actions and len(actions) > 0:
                first_action = actions[0]
                if isinstance(first_action, dict) and first_action.get('type') != 'dialogue_only':
                    action_types = [action.get('type', 'unknown') if isinstance(action, dict) else str(action) for action in actions]
                    # Remove duplicate logging - it's handled in game_loop.py
                    # rprint(Text(f"NPC actions extracted: {action_types} (confidence: {confidence:.2f})", style="dim magenta"))
            
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
    ) -> bool:
        """
        Validate that an extracted action is actually possible given the current game state.
        """
        action_type = action.get('type', '')
        parameters = action.get('parameters', {})
        
        if action_type == 'give_item':
            item_name = parameters.get('item_name', '')
            if not item_name:
                return False
            if not npc.has_item(item_name):
                return False
            return True
        
        elif action_type == 'accept_offer':
            active_offer = context.get('active_offer')
            if not active_offer:
                return False
            offered_item = active_offer.get('item_name', '')
            if not player.has_item(offered_item):
                return False
            return True
        
        elif action_type == 'decline_offer':
            active_offer = context.get('active_offer')
            if not active_offer:
                return False
            return True
        
        elif action_type == 'trade_accept':
            active_trade = context.get('active_trade_proposal')
            if not active_trade:
                return False
            # Verify both parties still have the items
            player_item = active_trade.get('player_item_object')
            npc_item = active_trade.get('npc_item_object')
            if not player.has_item(player_item):
                return False
            if not npc.has_item(npc_item):
                return False
            return True
        
        elif action_type == 'trade_decline':
            active_trade = context.get('active_trade_proposal')
            if not active_trade:
                return False
            return True
        
        elif action_type == 'trade_counter':
            player_item = parameters.get('player_item', '')
            npc_item = parameters.get('npc_item', '')
            if not player_item or not npc_item:
                return False
            if not player.has_item(player_item):
                return False
            if not npc.has_item(npc_item):
                return False
            return True
        
        elif action_type == 'accept_request':
            item_name = parameters.get('item_name', '')
            if not item_name:
                return False
            if not npc.has_item(item_name):
                return False
            return True
        
        elif action_type == 'decline_request':
            return True
        
        elif action_type == 'dialogue_only':
            return True
        
        else:
            return False
    
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