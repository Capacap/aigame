from __future__ import annotations
import litellm
import json
from .item import Item, load_item_from_file
from .location import Location
from .interaction_history import InteractionHistory, MessageEntry

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

# Import for loading items
ITEMS_BASE_PATH = "aigame/data/items"

console = Console()

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

    def __str__(self) -> str:
        # This format is already quite panel-friendly
        return (
            f"Name: {self.name}\n"
            f"Personality: {self.personality}\n"
            f"Goal: {self.goal}\n"
            f"Disposition: {self.disposition}\n"
            # Use item.name for display
            f"Items: {', '.join(item.name for item in self.items) if self.items else 'None'}"
        )

    def add_item(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise ValueError("Item must be an Item object.")
        try:
            self.items.append(item)
            # Message when character receives an item
            rprint(Text.assemble(Text("EVENT: ", style="dim white"), Text(f"{self.name} received '{item.name}'.", style="white")))
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

    def _prepare_llm_messages(self, current_location: Location) -> list[MessageEntry]:
        items_str = ", ".join(item.name for item in self.items) if self.items else "nothing"
        location_info = f"You are currently in: {current_location.name}. {current_location.description}"
        system_message_content = (
            f"You are {self.name}.\n"
            f"Your personality: {self.personality}\n"
            f"Your current goal: {self.goal}\n"
            f"Your current disposition/state of mind: {self.disposition}\n"
            f"You are currently carrying: {items_str}.\n"
            f"{location_info}\n\n"
            f"You will act and speak as {self.name} based on this information. Do not break character. "
            f"Your dialogue should reflect your thoughts and speech. "
            f"Only provide {self.name}'s next line of dialogue in response to the user. "
            f"The user may perform actions (like giving you items, complimenting you, or insulting you). These will be described in their message (e.g., \"I hand the item_name over to you.\", \"You seem very wise.\", or \"Your wares are terrible!\"). React naturally to such actions, both in your dialogue and by considering changes to your disposition."
            f"When the player uses a command like '/give ItemName', they are OFFERING you the item. It is not yet in your possession. Their message might look like '*I offer you the ItemName. Do you accept?*'. To accept the offered item, you MUST use the 'accept_item_offer' tool. If you do not want the item, simply state that in your dialogue."
            f"Pay close attention to any 'SYSTEM_ALERT' or 'SYSTEM_OBSERVATION' messages in the history. These provide direct prompts or context for you to consider significant changes or facts."
            f"You have tools available to interact with the game world. These include: "
            f"1. 'give_item_to_user': Use this tool if you willingly decide to give an item YOU possess to the user. You MUST use this tool to transfer an item. Clearly state your intention first." 
            f"2. 'change_disposition': Use this to update your internal disposition/state of mind in response to significant events or interactions (positive or negative). Clearly state your intention or reasoning first."
            f"3. 'accept_item_offer': If the player has offered you an item (their message will indicate this, e.g., '*I offer you ItemName.*'), use this tool to formally accept and take the item. State your intention to accept before using the tool."
        )
        messages: list[MessageEntry] = [{"role": "system", "content": system_message_content}]
        messages.extend(self.interaction_history.get_llm_history())
        return messages

    def get_ai_response(self, player_object: 'Player', current_location: Location) -> str | None:
        from .player import Player # Corrected import: Import Player here, inside the method
        current_messages = self._prepare_llm_messages(current_location)
        give_item_tool = {
            "type": "function",
            "function": {
                "name": "give_item_to_user",
                "description": "Gives an item from the character's inventory to the user. Only use this if the character willingly and logically decides to give the item based on the conversation (e.g., as a reward, for significant help, a fair trade). The item must be one the character currently possesses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {
                            "type": "string",
                            "description": "The exact name of the item to give. Must be an item the character possesses."
                        },
                        "reason": {
                            "type": "string",
                            "description": "A brief reason or thought process for why the character is giving this item now. This should reflect the conversation."
                        }
                    },
                    "required": ["item_name", "reason"]
                }
            }
        }
        change_disposition_tool = {
            "type": "function",
            "function": {
                "name": "change_disposition",
                "description": "Updates the character's internal disposition or state of mind based on the interaction. Use after significant positive or negative events, or if the user's actions align or conflict with your goals/personality.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_disposition_state": {
                            "type": "string",
                            "description": "The new disposition or state of mind (e.g., 'more trusting and friendly', 'highly suspicious and wary', 'grateful and indebted', 'annoyed', 'pleased')."
                        },
                        "reason": {
                            "type": "string",
                            "description": "A brief explanation for why the character's disposition is changing, reflecting the conversation."
                        }
                    },
                    "required": ["new_disposition_state", "reason"]
                }
            }
        }
        accept_item_offer_tool = {
            "type": "function",
            "function": {
                "name": "accept_item_offer",
                "description": "Accepts an item currently being offered by the player. Only use if the player's message clearly indicates they are offering you a specific item. Upon successful use, the item is transferred to your inventory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "item_name": {
                            "type": "string",
                            "description": "The exact name of the item you are accepting from the player's offer."
                        },
                        "reason": {
                            "type": "string",
                            "description": "A brief reason or acknowledgement for why you are accepting this item now."
                        }
                    },
                    "required": ["item_name", "reason"]
                }
            }
        }
        active_tools = [give_item_tool, change_disposition_tool, accept_item_offer_tool]

        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
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
                        if function_name == "give_item_to_user":
                            item_name_to_give = args.get("item_name")
                            reason_for_giving = args.get("reason", "No specific reason stated by AI.")
                            # rprint(Text(f"SYSTEM: AI ({self.name}) attempting to give '{item_name_to_give}'. Reason: {reason_for_giving}", style="yellow"))
                            rprint(Text.assemble(Text("AI EVENT: ", style="dim yellow"), Text(f"{self.name} (AI) is attempting to give '{item_name_to_give}'. Reason: {reason_for_giving}", style="yellow")))
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
                                tool_result_content = f"{self.name} tried to give '{item_name_to_give}' (Reason: {reason_for_giving}) but does not possess it. Current items: {', '.join(item.name for item in self.items)}"
                        elif function_name == "change_disposition":
                            new_disposition_value = args.get("new_disposition_state")
                            reason_for_change = args.get("reason", "No specific reason stated by AI.")
                            # rprint(Text(f"SYSTEM: AI ({self.name}) attempting to change disposition to '{new_disposition_value}'. Reason: {reason_for_change}", style="yellow"))
                            rprint(Text.assemble(Text("AI EVENT: ", style="dim yellow"), Text(f"{self.name} (AI) is considering a disposition change to '{new_disposition_value}'. Reason: {reason_for_change}", style="yellow")))
                            if not new_disposition_value or not isinstance(new_disposition_value, str):
                                tool_result_content = "Error: new_disposition_state not provided or invalid."
                            else:
                                self.disposition = new_disposition_value
                                tool_result_content = f"{self.name}'s disposition changed to: '{self.disposition}'."
                                # rprint(Text(f"SYSTEM: {self.name}'s disposition is now '{self.disposition}'.", style="bright_cyan"))
                                rprint(Text.assemble(Text("AI EVENT: ", style="dim bright_cyan"), Text(f"{self.name}'s disposition (self-initiated) is now '{self.disposition}'.", style="bright_cyan")))
                        elif function_name == "accept_item_offer":
                            item_name_to_accept = args.get("item_name")
                            reason_for_accepting = args.get("reason", "No specific reason stated by AI.")
                            rprint(Text.assemble(Text("AI EVENT: ", style="dim yellow"), Text(f"{self.name} (AI) is attempting to accept offer for '{item_name_to_accept}'. Reason: {reason_for_accepting}", style="yellow")))

                            if not self.active_offer:
                                tool_result_content = f"Error: There is no active item offer from the player to accept."
                            elif self.active_offer.get("item_name", "").lower() != item_name_to_accept.lower():
                                tool_result_content = f"Error: The item you tried to accept ('{item_name_to_accept}') does not match the currently offered item ('{self.active_offer.get('item_name')}')."
                            else:
                                offered_item_object = self.active_offer.get("item_object")
                                offered_by_name = self.active_offer.get("offered_by_name", "Player") # Default to Player if name not stored
                                
                                # Ensure player_object (the one who made the offer) still has the item
                                # Note: player_object here is the game's player object, not just a name.
                                if offered_item_object and player_object.has_item(offered_item_object):
                                    if player_object.remove_item(offered_item_object): # This prints its own success message
                                        self.add_item(offered_item_object) # This prints its own success message
                                        tool_result_content = f"Successfully accepted and received '{item_name_to_accept}' from {offered_by_name}. You now possess it."
                                        rprint(Text.assemble(Text("AI EVENT: ", style="dim bright_green"), Text(f"{self.name} accepted and received '{item_name_to_accept}' from {offered_by_name}.", style="bright_green")))
                                        self.active_offer = None # Clear the active offer
                                    else:
                                        tool_result_content = f"Error: Failed to remove '{item_name_to_accept}' from {offered_by_name}'s inventory, even though they appeared to have it."
                                else:
                                    tool_result_content = f"Error: {offered_by_name} no longer seems to possess the offered item '{item_name_to_accept}'. Offer may be void."
                        else:
                            tool_result_content = f"Error: Unknown tool {function_name} called by {self.name}."
                    except json.JSONDecodeError:
                        tool_result_content = f"Error: Invalid JSON arguments for {function_name}. Arguments: {function_args_str}"
                    except Exception as e:
                        tool_result_content = f"Error processing tool {function_name}: {str(e)}"
                    self.interaction_history.add_entry(role="tool", content=tool_result_content, tool_call_id=tool_call_id, name=function_name)
                
                # Get the updated history for the final call
                messages_for_final_call = self._prepare_llm_messages(current_location)

                final_response = litellm.completion(model="openai/gpt-4.1-mini", messages=messages_for_final_call)
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
        
        return cls(
            name=name,
            personality=personality,
            goal=goal,
            disposition=disposition,
            items=parsed_items
        )

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