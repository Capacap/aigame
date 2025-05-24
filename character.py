import litellm
import json
from player import Player # Assuming player.py is in the same directory
from item import Item # Import the new Item class

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

console = Console()

class Character:
    def __init__(self, name: str, personality: str, goal: str, relationship_to_player: str, items: list[Item]):
        # Validate arguments
        if not isinstance(name, str) or not name:
            raise ValueError("Name must be a non-empty string.")
        if not isinstance(personality, str) or not personality:
            raise ValueError("Personality must be a non-empty string.")
        if not isinstance(goal, str) or not goal:
            raise ValueError("Goal must be a non-empty string.")
        if not isinstance(relationship_to_player, str) or not relationship_to_player:
            raise ValueError("Relationship to player must be a non-empty string.")
        if not isinstance(items, list) or not all(isinstance(item, Item) for item in items):
            raise ValueError("Items must be a list of Item objects.")

        # Assign attributes
        self.name: str = name
        self.personality: str = personality
        self.goal: str = goal
        self.relationship_to_player: str = relationship_to_player
        self.items: list[Item] = list(items) # Now a list of Item objects
        self.conversation_history: list[dict[str, str]] = []

    def __str__(self) -> str:
        # This format is already quite panel-friendly
        return (
            f"Name: {self.name}\n"
            f"Personality: {self.personality}\n"
            f"Goal: {self.goal}\n"
            f"Relationship to Player: {self.relationship_to_player}\n"
            # Use item.name for display
            f"Items: {', '.join(item.name for item in self.items) if self.items else 'None'}"
        )

    def add_item(self, item: Item) -> None:
        if not isinstance(item, Item):
            raise ValueError("Item must be an Item object.")
        try:
            self.items.append(item)
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
            self.conversation_history.append({"speaker": speaker, "message": message if message is not None else ""})
        except Exception as e:
            rprint(f"[bold red]Error adding to conversation history: {e}[/bold red]")

    def _prepare_llm_messages(self) -> list[dict[str, str]]:
        items_str = ", ".join(item.name for item in self.items) if self.items else "nothing"
        system_message_content = (
            f"You are {self.name}.\n"
            f"Your personality: {self.personality}\n"
            f"Your current goal: {self.goal}\n"
            f"Your current feelings towards the player: {self.relationship_to_player}\n"
            f"You are currently carrying: {items_str}.\n\n"
            f"You will act and speak as {self.name} based on this information. Do not break character. "
            f"Only provide {self.name}'s next line of dialogue in response to the user. "
            f"The user may perform actions like giving you items. These will be described in their message (e.g., 'I hand the item_name over to you.'). React naturally to such actions."
            f"You have tools available to interact with the game world. These include: "
            f"1. 'give_item_to_player': Use this if you willingly decide to give an item you possess to the player. Only use this if the reason is compelling (e.g. player helped you significantly, player offers a fair trade you accept, it directly achieves your goal). "
            f"2. 'change_disposition': Use this to update your internal feelings/relationship towards the player if the conversation significantly warrants it (e.g., they help you, betray you, impress you with knowledge, show great kindness). "
            f"Clearly state your intention or the context that leads you to use a tool before using it. For example, if giving an item, say something like 'Since you helped me, I can give you this.'"
        )
        messages = [{"role": "system", "content": system_message_content}]
        for turn in self.conversation_history:
            role = "assistant" if turn["speaker"] == self.name else "user"
            messages.append({"role": role, "content": turn["message"]})
        return messages

    def get_ai_response(self, player_object: Player) -> str | None:
        current_messages = self._prepare_llm_messages()
        give_item_tool = {
            "type": "function",
            "function": {
                "name": "give_item_to_player",
                "description": "Gives an item from the character's inventory to the player. Only use this if the character willingly and logically decides to give the item based on the conversation (e.g., as a reward, for significant help, a fair trade). The item must be one the character currently possesses.",
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
                "description": "Updates the character's internal disposition or relationship towards the player based on the interaction. Use after significant positive or negative events, or if the player's actions align or conflict with your goals/personality.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_disposition": {
                            "type": "string",
                            "description": "The new way the character feels about or relates to the player (e.g., 'more trusting and friendly', 'highly suspicious and wary', 'grateful and indebted', 'impressed and respectful')."
                        },
                        "reason": {
                            "type": "string",
                            "description": "A brief explanation for why the character's disposition is changing, reflecting the conversation."
                        }
                    },
                    "required": ["new_disposition", "reason"]
                }
            }
        }
        active_tools = [give_item_tool, change_disposition_tool]

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
                # Storing response_message.model_dump() which includes the tool_call itself.
                # current_messages.append(response_message.model_dump()) # This causes an error with the API if tool calls exist.
                # LiteLLM expects the assistant message with tool_calls to be added to the messages list for the *next* call,
                # not the one that *produced* the tool_call. Let's add it to the *character's* history, and the next _prepare_llm_messages will include it.

                # We need to ensure the message that *requested* the tool call (even if empty text) is in history.
                # If ai_message_content is empty AND there are tool_calls, the LLM might just be thinking.
                # We'll add it to conversation_history. It will then be part of 'current_messages' for the *next* call *if* it was added.

                # The original code structure for message appending needs review for tool calls.
                # The `response_message.model_dump()` is the correct thing to add if it has tool_calls.
                # Let's ensure `current_messages` is the list we pass to the *next* LLM call when tools are involved.
                # The first LLM call provides `response_message`. If it has `tool_calls`, we append `response_message.model_dump()` to `current_messages`.
                # Then, we process tools, append their results, and make *another* call with the updated `current_messages`.

                current_messages.append(response_message.model_dump(exclude_none=True))

                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args_str = tool_call.function.arguments
                    tool_call_id = tool_call.id
                    tool_result_content = ""
                    try:
                        args = json.loads(function_args_str)
                        if function_name == "give_item_to_player":
                            item_name_to_give = args.get("item_name")
                            reason_for_giving = args.get("reason", "No specific reason stated by AI.")
                            rprint(Text(f"SYSTEM: AI ({self.name}) attempting to give '{item_name_to_give}'. Reason: {reason_for_giving}", style="yellow"))
                            if not item_name_to_give:
                                tool_result_content = f"Error: item_name not provided by {self.name}."
                            elif self.has_item(item_name_to_give): # has_item now works with string name
                                # Find the actual Item object to give, as player.add_item will expect an Item object
                                item_object_to_give = next((item for item in self.items if item.name == item_name_to_give), None)
                                if item_object_to_give and self.remove_item(item_object_to_give): # remove_item also works with string or Item
                                    player_object.add_item(item_object_to_give) # Player gets Item object
                                    tool_result_content = f"Successfully gave '{item_name_to_give}' to {player_object.name}. {self.name} no longer has it."
                                else:
                                    tool_result_content = f"Error: {self.name} tried to give '{item_name_to_give}' but failed to remove it internally or find the item object."
                            else:
                                tool_result_content = f"{self.name} tried to give '{item_name_to_give}' (Reason: {reason_for_giving}) but does not possess it. Current items: {', '.join(item.name for item in self.items)}"
                        elif function_name == "change_disposition":
                            new_disposition = args.get("new_disposition")
                            reason_for_change = args.get("reason", "No specific reason stated by AI.")
                            rprint(Text(f"SYSTEM: AI ({self.name}) attempting to change disposition to '{new_disposition}'. Reason: {reason_for_change}", style="yellow"))
                            if not new_disposition or not isinstance(new_disposition, str):
                                tool_result_content = "Error: new_disposition not provided or invalid."
                            else:
                                self.relationship_to_player = new_disposition
                                tool_result_content = f"{self.name}'s disposition towards player changed to: '{new_disposition}'."
                                rprint(Text(f"SYSTEM: {self.name}'s disposition towards player is now '{self.relationship_to_player}'.", style="bright_cyan"))
                        else:
                            tool_result_content = f"Error: Unknown tool {function_name} called by {self.name}."
                    except json.JSONDecodeError:
                        tool_result_content = f"Error: Invalid JSON arguments for {function_name}. Arguments: {function_args_str}"
                    except Exception as e:
                        tool_result_content = f"Error processing tool {function_name}: {str(e)}"
                    current_messages.append({"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": tool_result_content})
                
                final_response = litellm.completion(model="openai/gpt-4.1-mini", messages=current_messages)
                ai_spoken_response = final_response.choices[0].message.content
            else:
                # No tool call, the initial message content is the direct spoken response
                ai_spoken_response = ai_message_content # Use the potentially empty content from the first response

            return ai_spoken_response.strip() if ai_spoken_response else f"[{self.name} seems to ponder for a moment but says nothing further.]"

        except Exception as e:
            rprint(Text(f"Error getting AI response for {self.name}: {e}", style="bold red"))
            return None


