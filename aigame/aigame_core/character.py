from __future__ import annotations
import litellm
import json
from .item import Item, load_item_from_file
from .location import Location
from .interaction_history import InteractionHistory, MessageEntry
from .config import DEFAULT_LLM_MODEL, debug_llm_call
from typing import TYPE_CHECKING, Optional

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

# Import for loading items
ITEMS_BASE_PATH = "aigame/data/items"

console = Console()

if TYPE_CHECKING:
    from .player import Player

class Character:
    def __init__(self, name: str, personality: str, goal: str, disposition: str, items: list[Item]):
        # Validate arguments
        if not isinstance(name, str) or not name:
            raise ValueError("Name must be a non-empty string.")
        if not isinstance(personality, str) or not personality:
            raise ValueError("Personality must be a non-empty string.")
        if not isinstance(goal, str) or not goal:
            raise ValueError("Goal must be a non-empty string.")
        if not isinstance(disposition, str) or not disposition:
            raise ValueError("Disposition must be a non-empty string.")
        if not isinstance(items, list) or not all(isinstance(item, Item) for item in items):
            raise ValueError("Items must be a list of Item objects.")

        # Assign attributes
        self.name: str = name
        self.personality: str = personality
        self.goal: str = goal
        self.disposition: str = disposition
        self.items: list[Item] = list(items) # Now a list of Item objects
        self.interaction_history: InteractionHistory = InteractionHistory()
        self.active_offer: dict | None = None # To store details of an item offered to this character
        self.active_trade_proposal: dict | None = None # To store details of a trade proposal made to this character
        self.active_request: dict | None = None # To store details of an item request made to this character

    def __str__(self) -> str:
        # This format is already quite panel-friendly
        base_info = (
            f"Name: {self.name}\n"
            f"Personality: {self.personality}\n"
            f"Goal: {self.goal}\n"
            f"Disposition: {self.disposition}\n"
            # Use item.name for display
            f"Items: {', '.join(item.name for item in self.items) if self.items else 'None'}"
        )
        
        return base_info

    def add_item(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise ValueError("Item must be an Item object.")
        try:
            self.items.append(item)
            # Removed verbose event message to reduce clutter
        except Exception as e:
            rprint(f"[bold red]Error adding item for {self.name}: {e}[/bold red]")

    def remove_item(self, item_identifier: str | Item) -> bool:
        if not isinstance(item_identifier, (str, Item)) or not item_identifier:
            raise ValueError("Item identifier must be a non-empty string or an Item object.")
        try:
            # The Item.__eq__ method allows us to compare with string (item name) or another Item object
            if item_identifier in self.items:
                self.items.remove(item_identifier)
                return True
            return False
        except Exception as e:
            rprint(f"[bold red]Error removing item for {self.name}: {e}[/bold red]")
            return False

    def has_item(self, item_identifier: str | Item) -> bool:
        if not isinstance(item_identifier, (str, Item)) or not item_identifier:
            raise ValueError("Item identifier must be a non-empty string or an Item object.")
        try:
            # The Item.__eq__ method allows us to compare with string (item name) or another Item object
            return item_identifier in self.items
        except Exception as e:
            rprint(f"[bold red]Error checking for item for {self.name}: {e}[/bold red]")
            return False

    def add_dialogue_turn(self, speaker: str, message: str) -> None:
        if not isinstance(speaker, str) or not speaker:
            raise ValueError("Speaker must be a non-empty string.")
        if not isinstance(message, str) or not message:
            # Allow empty messages if they are from AI (e.g. only tool call)
            # For player, input loop should handle empty string if needed before calling this.
            # For now, let's keep this validation as it's generally good.
            if not message and speaker != self.name : # allow AI to have empty message if it's just a tool call
                 rprint(Text(f"Warning: Empty message from {speaker}", style="dim yellow"))
            # raise ValueError("Message must be a non-empty string.")
        try:
            role: Literal["user", "assistant"] = "user" if speaker != self.name else "assistant"
            self.interaction_history.add_entry(role=role, content=message if message is not None else "")
        except Exception as e:
            rprint(f"[bold red]Error adding to conversation history: {e}[/bold red]")

    def _prepare_llm_messages(self, current_location: Location, scenario: 'Scenario' = None) -> list[MessageEntry]:
        items_str = ", ".join(item.name for item in self.items) if self.items else "nothing"
        location_info = f"You are currently in: {current_location.name}. {current_location.description}"
        
        # Build the system message with strong emphasis on disposition
        system_message_content = (
            f"You are {self.name}.\n"
            f"Your personality: {self.personality}\n"
            f"Your current goal: {self.goal}\n"
            f"🎭 CRITICAL: Your current disposition/state of mind: {self.disposition}\n"
            f"Your disposition '{self.disposition}' should HEAVILY influence your trade decision. "
            f"Consider how your current state of mind affects your willingness to trade, "
            f"your trust in the player, and your evaluation of the offer.\n"
            f"You are currently carrying: {items_str}.\n"
            f"{location_info}\n"
        )
        
        # Add scenario setting context if available
        if scenario and hasattr(scenario, 'setting'):
            system_message_content += (
                f"\n🌍 WORLD CONTEXT: {scenario.setting}\n"
                f"This world context should inform your behavior, dialogue style, and decision-making. "
                f"Consider how the setting influences social norms, power dynamics, and the significance of your actions.\n"
            )
        
        system_message_content += (
            f"\nYou can use these tools when appropriate:\n"
            f"1. 'give_item_to_player': If you decide to give an item to the player, use this tool to transfer it. State your intention to give before using the tool.\n"
            f"2. 'accept_item_offer': If the player has offered you an item (their message will indicate this, e.g., '*I offer you ItemName.*'), use this tool to formally accept and take the item. State your intention to accept before using the tool."
        )
        
        messages: list[MessageEntry] = [{"role": "system", "content": system_message_content}]
        messages.extend(self.interaction_history.get_llm_history())
        return messages

    def handle_standing_trade_offer(self, player_object: 'Player', current_location: 'Location', scenario: 'Scenario' = None) -> str | None:
        """
        Handles a standing trade offer using AI to make the decision.
        Returns the NPC's spoken response or None if no response.
        """
        if not self.active_trade_proposal:
            return None

        # Build context for the AI
        offered_by_name = self.active_trade_proposal.get("offered_by_name", "")
        player_item_name = self.active_trade_proposal.get("player_item_name", "")
        npc_item_name = self.active_trade_proposal.get("npc_item_name", "")

        # Prepare messages for LLM
        messages = self._prepare_llm_messages(current_location, scenario)
        
        # Add trade decision context
        trade_context = (
            f"TRADE_DECISION_REQUIRED: {offered_by_name} has proposed trading their '{player_item_name}' "
            f"for your '{npc_item_name}'. You must decide whether to ACCEPT or REJECT this trade proposal. "
            f"🎭 CRITICAL: Your disposition '{self.disposition}' should heavily influence this decision. "
            f"Consider: Does this trade align with your goals? Do you trust the player? "
            f"Is the trade fair? How does your current disposition affect your willingness to trade? "
            f"Respond with a JSON object containing: "
            f"'decision' (either 'ACCEPT' or 'REJECT'), "
            f"'spoken_response' (what you say to the player), and "
            f"'reasoning' (brief explanation of your decision)."
        )
        
        messages.append({"role": "user", "content": trade_context})
        
        debug_llm_call("Character", f"Trade decision for {self.name}", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            raw_response = response.choices[0].message.content
            if not raw_response:
                # Fallback to rejection if no response
                self.active_trade_proposal = None
                return f"[{self.name} seems confused by the trade proposal and doesn't respond clearly.]"
            
            try:
                decision_data = json.loads(raw_response)
                decision = decision_data.get("decision", "REJECT").upper()
                spoken_response = decision_data.get("spoken_response", "")
                reasoning = decision_data.get("reasoning", "No reasoning provided")
                
                rprint(Text.assemble(Text("TRADE DECISION: ", style="dim yellow"), 
                                   Text(f"{self.name} decided to {decision}. Reasoning: {reasoning}", style="yellow")))
                
                if decision == "ACCEPT":
                    # Execute the trade
                    if (player_item_object and npc_item_object and 
                        player_object.has_item(player_item_object) and self.has_item(npc_item_object)):
                        
                        if player_object.remove_item(player_item_object) and self.remove_item(npc_item_object):
                            self.add_item(player_item_object)  # NPC gets player's item
                            player_object.add_item(npc_item_object)  # Player gets NPC's item
                            rprint(Text.assemble(Text("TRADE COMPLETED: ", style="dim bright_green"), 
                                               Text(f"{self.name} traded '{npc_item_name}' for '{player_item_name}'.", style="bright_green")))
                            self.active_trade_proposal = None
                            
                            # Add system message to inform AI about the completed trade
                            trade_completion_message = f"SYSTEM_ALERT: Trade completed successfully. You just traded your '{npc_item_name}' for the player's '{player_item_name}'. The exchange is done. Respond naturally to this completed transaction."
                            self.interaction_history.add_entry(role="system", content=trade_completion_message)
                            
                            # Add the spoken response to conversation history
                            if spoken_response:
                                self.add_dialogue_turn(speaker=self.name, message=spoken_response)
                            
                            return spoken_response
                        else:
                            self.active_trade_proposal = None
                            return f"[Trade failed due to item transfer error. {spoken_response}]"
                    else:
                        self.active_trade_proposal = None
                        return f"[Trade failed - one party no longer has the required items. {spoken_response}]"
                
                else:  # REJECT or any other value
                    self.active_trade_proposal = None
                    # Add the spoken response to conversation history
                    if spoken_response:
                        self.add_dialogue_turn(speaker=self.name, message=spoken_response)
                    return spoken_response
                    
            except json.JSONDecodeError:
                # Fallback to rejection if JSON parsing fails
                self.active_trade_proposal = None
                return f"[{self.name} seems confused by the trade proposal and declines.]"
                
        except Exception as e:
            rprint(Text(f"Error handling trade offer for {self.name}: {e}", style="bold red"))
            self.active_trade_proposal = None
            return f"[{self.name} seems distracted and doesn't respond to the trade proposal.]"

    def handle_standing_request(self, player_object: 'Player', current_location: 'Location', scenario: 'Scenario' = None) -> str | None:
        """
        Handles a standing item request using AI to make the decision.
        Returns the NPC's spoken response or None if no response.
        """
        if not self.active_request:
            return None

        # Build context for the AI
        requested_by_name = self.active_request.get("requested_by_name", "")
        item_name = self.active_request.get("item_name", "")

        # Prepare messages for LLM
        messages = self._prepare_llm_messages(current_location, scenario)
        
        # Add request decision context
        request_context = (
            f"REQUEST_DECISION_REQUIRED: {requested_by_name} has asked for your '{item_name}'. "
            f"You must decide whether to GIVE or DECLINE this request. "
            f"🎭 CRITICAL: Your disposition '{self.disposition}' should heavily influence this decision. "
            f"Consider: Do you want to help this person? Do you trust them? "
            f"Is this item important to you? How does your current disposition affect your generosity? "
            f"Respond with a JSON object containing: "
            f"'decision' (either 'GIVE' or 'DECLINE'), "
            f"'spoken_response' (what you say to the player), and "
            f"'reasoning' (brief explanation of your decision)."
        )
        
        messages.append({"role": "user", "content": request_context})
        
        debug_llm_call("Character", f"Request decision for {self.name}", DEFAULT_LLM_MODEL)
        
        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            raw_response = response.choices[0].message.content
            if not raw_response:
                # Fallback to decline if no response
                self.active_request = None
                return f"[{self.name} seems confused by the request and doesn't respond clearly.]"
            
            try:
                decision_data = json.loads(raw_response)
                decision = decision_data.get("decision", "DECLINE").upper()
                spoken_response = decision_data.get("spoken_response", "")
                reasoning = decision_data.get("reasoning", "No reasoning provided")
                
                rprint(Text.assemble(Text("REQUEST DECISION: ", style="dim yellow"), 
                                   Text(f"{self.name} decided to {decision}. Reasoning: {reasoning}", style="yellow")))
                
                if decision == "ACCEPT":
                    # Execute the item transfer
                    if requested_item_object and self.has_item(requested_item_object):
                        if self.remove_item(requested_item_object):
                            player_object.add_item(requested_item_object)
                            rprint(Text.assemble(Text("REQUEST GRANTED: ", style="dim bright_green"), 
                                               Text(f"{self.name} gives '{item_name}' to {requested_by_name}.", style="bright_green")))
                            self.active_request = None
                            
                            # Add system message to inform AI about the completed transfer
                            request_completion_message = f"SYSTEM_ALERT: You just gave your '{item_name}' to {requested_by_name} as they requested. The item transfer is complete. Respond naturally to this generous act."
                            self.interaction_history.add_entry(role="system", content=request_completion_message)
                            
                            # Add the spoken response to conversation history
                            if spoken_response:
                                self.add_dialogue_turn(speaker=self.name, message=spoken_response)
                            
                            return spoken_response
                        else:
                            self.active_request = None
                            return f"[Request failed due to item transfer error. {spoken_response}]"
                    else:
                        self.active_request = None
                        return f"[Request failed - {self.name} no longer has the '{item_name}'. {spoken_response}]"
                
                else:  # DECLINE or any other value
                    self.active_request = None
                    # Add the spoken response to conversation history
                    if spoken_response:
                        self.add_dialogue_turn(speaker=self.name, message=spoken_response)
                    return spoken_response
                    
            except json.JSONDecodeError:
                # Fallback to decline if JSON parsing fails
                self.active_request = None
                return f"[{self.name} seems confused by the request and declines.]"
                
        except Exception as e:
            rprint(Text(f"Error handling request for {self.name}: {e}", style="bold red"))
            self.active_request = None
            return f"[{self.name} seems distracted and doesn't respond to the request.]"

    def get_ai_response(self, player_object: 'Player', current_location: Location, scenario: 'Scenario' = None) -> str | None:
        from .player import Player # Corrected import: Import Player here, inside the method

        # Validate arguments
        if not isinstance(player_object, Player):
            raise ValueError("player_object must be a Player instance.")
        if not isinstance(current_location, Location):
            raise ValueError("current_location must be a Location instance.")

        # Handle standing trade offer first
        trade_response = self.handle_standing_trade_offer(player_object, current_location, scenario)
        if trade_response:
            return trade_response

        # Handle standing request second
        request_response = self.handle_standing_request(player_object, current_location, scenario)
        if request_response:
            return request_response

        # Handle standing offer third (commenting out since method doesn't exist)
        # offer_response = self.handle_standing_offer(player_object, current_location, scenario)
        # if offer_response:
        #     return offer_response

        # Regular conversation - prepare messages
        current_messages = self._prepare_llm_messages(current_location, scenario)

        # Define available tools for the NPC
        active_tools = [
            {
                "type": "function",
                "function": {
                    "name": "give_item_to_player",
                    "description": "Give an item from your inventory to the player",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "item_name": {
                                "type": "string",
                                "description": "The exact name of the item to give to the player"
                            }
                        },
                        "required": ["item_name"]
                    }
                }
            }
        ]

        debug_llm_call("Character", f"Dialogue generation for {self.name}", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=current_messages,
                tools=active_tools,
                tool_choice="auto"
            )

            response_message = response.choices[0].message
            # Ensure message content is a string, even if None, for add_dialogue_turn
            ai_message_content = response_message.content if response_message.content is not None else ""
            tool_calls = response_message.tool_calls

            if tool_calls:
                # Add the assistant's initial message (even if empty) that contained the tool_call request to history
                # The actual spoken response will come after tool processing.
                self.interaction_history.add_raw_llm_message(response_message.model_dump(exclude_none=True))

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id
                    tool_result_content = ""
                    try:
                        args = json.loads(function_args_str)
                        if function_name == "give_item_to_player":
                            item_name_to_give = args.get("item_name")
                            # rprint(Text(f"SYSTEM: AI ({self.name}) attempting to give '{item_name_to_give}'. Reason: {reason_for_giving}", style="yellow"))
                            rprint(Text.assemble(Text("AI EVENT: ", style="dim yellow"), Text(f"{self.name} (AI) is attempting to give '{item_name_to_give}'.", style="yellow")))
                            if not item_name_to_give:
                                tool_result_content = f"Error: item_name not provided by {self.name}."
                            elif self.has_item(item_name_to_give): # has_item now works with string name
                                item_object_to_give = next((item for item in self.items if item.name == item_name_to_give), None)
                                if item_object_to_give and self.remove_item(item_object_to_give): 
                                    player_object.add_item(item_object_to_give) # Player gets Item object
                                    tool_result_content = f"Successfully gave '{item_name_to_give}' to {player_object.name}. {self.name} no longer has it."
                                    # Specific success message for AI giving item is handled by player_object.add_item and the tool_result_content itself implies success to AI.
                                    # We can also add a direct rprint here if desired for console visibility of the transfer.
                                    rprint(Text.assemble(Text("AI EVENT: ", style="dim bright_green"), Text(f"{self.name} gives the '{item_object_to_give.name}' to {player_object.name}.", style="bright_green")))
                                else:
                                    tool_result_content = f"Error: {self.name} tried to give '{item_name_to_give}' but failed to remove it internally or find the item object."
                            else:
                                tool_result_content = f"{self.name} tried to give '{item_name_to_give}' but does not possess it. Current items: {', '.join(item.name for item in self.items)}"
                        else:
                            tool_result_content = f"Error: Unknown tool {function_name} called by {self.name}."
                    except json.JSONDecodeError:
                        tool_result_content = f"Error: Invalid JSON arguments for {function_name}. Arguments: {function_args_str}"
                    except Exception as e:
                        tool_result_content = f"Error processing tool {function_name}: {str(e)}"
                    self.interaction_history.add_entry(role="tool", content=tool_result_content, tool_call_id=tool_call_id, name=function_name)
                
                # Get the updated history for the final call
                messages_for_final_call = self._prepare_llm_messages(current_location, scenario)

                debug_llm_call("Character", f"Final response after tools for {self.name}", DEFAULT_LLM_MODEL)
                final_response = litellm.completion(model=DEFAULT_LLM_MODEL, messages=messages_for_final_call)
                ai_spoken_response = final_response.choices[0].message.content

                # Add the AI's final spoken response to history
                if ai_spoken_response:
                    self.interaction_history.add_entry(role="assistant", content=ai_spoken_response)
            else:
                # No tool call, the initial message content is the direct spoken response
                ai_spoken_response = ai_message_content # Use the potentially empty content from the first response
                # Add AI's response to history if it's not just a tool call and has content
                # If ai_message_content is empty and no tool_calls, it's like a silent ponder.
                # If it has content, then it's a spoken response.
                if ai_spoken_response: # Only add if there's actual content
                    self.interaction_history.add_entry(role="assistant", content=ai_spoken_response)

            # The character's spoken response (or lack thereof) is added by add_dialogue_turn by the game loop later.
            # This method should return the *spoken* part.
            # The InteractionHistory is updated internally with all steps (tool req, tool res, final spoken).

            # If ai_spoken_response is empty after tool processing, it means the LLM chose to say nothing.
            # If there were no tool calls and ai_message_content was empty, it also means LLM said nothing.
            # The add_dialogue_turn in the main game loop will receive this and add it to history.

            return ai_spoken_response.strip() if ai_spoken_response else f"[{self.name} seems to ponder for a moment but says nothing further.]"

        except Exception as e:
            rprint(Text(f"Error getting AI response for {self.name}: {e}", style="bold red"))
            return None

    def get_ai_response_with_actions(self, player_object: 'Player', current_location: Location, scenario: 'Scenario' = None) -> tuple[str | None, dict]:
        """
        Enhanced version that generates AI response and parses actions from natural language.
        Returns (spoken_response, action_results_dict)
        """
        from .npc_action_parser import NPCActionParser
        from .player import Player
        
        # Validate arguments
        if not isinstance(player_object, Player):
            raise ValueError("player_object must be a Player instance.")
        if not isinstance(current_location, Location):
            raise ValueError("current_location must be a Location instance.")
        
        # Prepare messages for natural dialogue generation
        messages = self._prepare_llm_messages(current_location, scenario)
        
        debug_llm_call("Character", f"Natural dialogue with actions for {self.name}", DEFAULT_LLM_MODEL)
        
        try:
            # Generate response without tool calls - just natural dialogue
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                temperature=0.7,
                max_tokens=300
            )
            
            ai_response = response.choices[0].message.content
            if not ai_response:
                return None, {'executed_actions': [], 'state_changes': {}, 'errors': ['Empty AI response']}
            
            # Parse the response for actions without debug mode (we handle debug at higher level)
            parser = NPCActionParser(debug_mode=False)
            context = {
                'active_offer': getattr(self, 'active_offer', None),
                'active_trade_proposal': getattr(self, 'active_trade_proposal', None),
                'active_request': getattr(self, 'active_request', None)
            }
            
            parse_result = parser.parse_npc_response(ai_response, self, player_object, context)
            
            if not parse_result['success']:
                rprint(Text(f"Failed to parse NPC actions: {parse_result['error_message']}", style="dim red"))
                return ai_response, {'executed_actions': [], 'state_changes': {}, 'errors': [parse_result['error_message']]}
            
            # Execute the parsed actions
            action_results = parser.execute_actions(parse_result['actions'], self, player_object, context)
            
            # Add classification info to action_results for later display
            if parse_result.get('actions'):
                action_types = parse_result.get('action_types', ['unknown'])
                confidence = parse_result.get('confidence', 0.0)
                action_results['classification'] = {
                    'action_types': action_types,
                    'confidence': confidence
                }
            else:
                # If no actions, it's dialogue only
                action_results['classification'] = {
                    'action_types': ['dialogue_only'],
                    'confidence': parse_result.get('confidence', 1.0)
                }
            
            # Add the response to dialogue history
            self.add_dialogue_turn(speaker=self.name, message=ai_response)
            
            return ai_response, action_results
            
        except Exception as e:
            rprint(Text(f"[bold red]Error during NPC AI response with actions: {e}[/bold red]"))
            return None, {'executed_actions': [], 'state_changes': {}, 'errors': [str(e)]}

    @classmethod
    def from_dict(cls, data: dict) -> 'Character':
        if not isinstance(data, dict):
            raise ValueError("Character data must be a dictionary.")

        name = data.get("name")
        personality = data.get("personality")
        goal = data.get("goal")
        disposition = data.get("disposition")
        item_names_data = data.get("items", []) # Expecting a list of item names (strings)

        if not all([name, personality, goal, disposition]):
            raise ValueError("Missing required character attributes in data: name, personality, goal, disposition.")
        if not isinstance(item_names_data, list):
            raise ValueError("Items data must be a list of item names (strings).")

        # Load Item objects from item_names_data
        parsed_items = []
        for item_name in item_names_data:
            if not isinstance(item_name, str):
                raise ValueError("Each item in items_data must be a string (item name).")
            try:
                item = load_item_from_file(item_name, ITEMS_BASE_PATH)
                parsed_items.append(item)
            except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
                name_for_error = data.get("name", "Unknown") # Get name from data for better error message
                raise ValueError(f"Failed to load item '{item_name}' for character '{name_for_error}': {e}") from e
        
        character = cls(
            name=name,
            personality=personality,
            goal=goal,
            disposition=disposition,
            items=parsed_items
        )
        
        return character

def load_character_from_file(character_name: str, base_directory_path: str) -> Character:
    """
    Loads a single character definition from a JSON file named after the character.

    Args:
        character_name (str): The name of the character (and the JSON file, e.g., "Archivist Silas.json").
        base_directory_path (str): The base directory where character JSON files are stored.

    Returns:
        Character: A Character object.
        
    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If character data is malformed or missing required fields.
    """
    file_path = f"{base_directory_path.rstrip('/')}/{character_name}.json"
    
    try:
        with open(file_path, 'r') as f:
            char_data = json.load(f) # Expecting a single JSON object, not a list
    except FileNotFoundError:
        rprint(f"[bold red]Error: Character file '{file_path}' not found for character '{character_name}'.[/bold red]")
        raise
    except json.JSONDecodeError as e:
        rprint(f"[bold red]Error: Could not decode JSON from '{file_path}' for character '{character_name}'. Details: {e}[/bold red]")
        raise

    if not isinstance(char_data, dict):
        raise ValueError(f"Character JSON file '{file_path}' should contain a single character object (a dictionary), not a list or other type.")

    try:
        character = Character.from_dict(char_data)
        # Ensure the loaded character's name matches the expected name (optional, but good for consistency)
        if character.name != character_name:
            rprint(f"[bold yellow]Warning: Character name in file '{character.name}' does not match expected name '{character_name}' from filename '{file_path}'. Using name from file.[/bold yellow]")
        return character
    except ValueError as ve:
        char_name = char_data.get('name', 'Unknown Character')
        rprint(f"[bold red]Error loading character '{char_name}': {ve}[/bold red]")
        raise ValueError(f"Failed to load character '{char_name}': {ve}") from ve