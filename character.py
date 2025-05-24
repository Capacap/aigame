import collections
import litellm
import json
from player import Player # Assuming player.py is in the same directory

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

console = Console()

class Character:
    def __init__(self, name: str, personality: str, goal: str, relationship_to_player: str, items: list[str]):
        # Validate arguments
        if not isinstance(name, str) or not name:
            raise ValueError("Name must be a non-empty string.")
        if not isinstance(personality, str) or not personality:
            raise ValueError("Personality must be a non-empty string.")
        if not isinstance(goal, str) or not goal:
            raise ValueError("Goal must be a non-empty string.")
        if not isinstance(relationship_to_player, str) or not relationship_to_player:
            raise ValueError("Relationship to player must be a non-empty string.")
        if not isinstance(items, list) or not all(isinstance(item, str) for item in items):
            raise ValueError("Items must be a list of strings.")

        # Assign attributes
        self.name: str = name
        self.personality: str = personality
        self.goal: str = goal
        self.relationship_to_player: str = relationship_to_player
        self.items: list[str] = list(items)
        self.conversation_history: list[dict[str, str]] = []

    def __str__(self) -> str:
        # This format is already quite panel-friendly
        return (
            f"Name: {self.name}\n"
            f"Personality: {self.personality}\n"
            f"Goal: {self.goal}\n"
            f"Relationship to Player: {self.relationship_to_player}\n"
            f"Items: {', '.join(self.items) if self.items else 'None'}"
        )

    def add_item(self, item: str) -> None:
        if not isinstance(item, str) or not item:
            raise ValueError("Item must be a non-empty string.")
        try:
            self.items.append(item)
        except Exception as e:
            rprint(f"[bold red]Error adding item for {self.name}: {e}[/bold red]")

    def remove_item(self, item: str) -> bool:
        if not isinstance(item, str) or not item:
            raise ValueError("Item must be a non-empty string.")
        try:
            if item in self.items:
                self.items.remove(item)
                # Player class handles its own print for remove_item, character's internal remove is silent for AI
                # but when AI *tool* removes item, it rprints. This is fine.
                # For player giving to NPC, the NPC add_item is silent.
                return True
            return False
        except Exception as e:
            rprint(f"[bold red]Error removing item for {self.name}: {e}[/bold red]")
            return False

    def has_item(self, item: str) -> bool:
        if not isinstance(item, str) or not item:
            raise ValueError("Item must be a non-empty string.")
        try:
            return item in self.items
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
        items_str = ", ".join(self.items) if self.items else "nothing"
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
                current_messages.append(response_message.model_dump()) 

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
                            elif self.has_item(item_name_to_give):
                                if self.remove_item(item_name_to_give): # Character removes item
                                    player_object.add_item(item_name_to_give) # Player gets item
                                    tool_result_content = f"Successfully gave '{item_name_to_give}' to {player_object.name}. {self.name} no longer has it."
                                else:
                                    tool_result_content = f"Error: {self.name} tried to give '{item_name_to_give}' but failed to remove it internally."
                            else:
                                tool_result_content = f"{self.name} tried to give '{item_name_to_give}' (Reason: {reason_for_giving}) but does not possess it. Current items: {self.items}"
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

if __name__ == '__main__':
    try:
        player1 = Player(name="Alex the Scholar")
        player1.add_item("translation cypher") # Player starts with the cypher
        # Player class __str__ could also be made rich-friendly or we format it here
        player_state_text = Text()
        player_state_text.append(f"Name: {player1.name}\n", style="bold")
        player_state_text.append(f"Items: {', '.join(player1.items) if player1.items else 'Nothing'}")
        rprint(Panel(player_state_text, title="Player Initial State", border_style="blue"))
        console.line()

        npc = Character(
            name="Archivist Silas",
            personality=("A kind and knowledgeable archivist, passionate about history and discovery. "
                           "Initially a bit preoccupied and formal, but genuinely appreciates those who share his love for knowledge "
                           "or offer assistance with his research. He is willing to share resources with those he deems trustworthy and helpful."),
            goal=("To access and study the newly unsealed 'Chamber of Echoes' within the archives. He possesses the 'Echo Chamber Key' "
                  "but is also trying to find a 'translation cypher' for some ancient tablets he found, which he believes are crucial for understanding the Chamber's contents."),
            relationship_to_player="Neutral but polite; open to scholarly individuals.",
            items=["Echo Chamber Key", "reading spectacles", "dusty tome"]
        )
        rprint(Panel(str(npc), title="Character Initial State", border_style="green"))
        console.line()
        rprint(Panel("Starting Interactive Conversation with Silas... (Type 'quit' to end)", title_align="center", border_style="dim white"))

        key_to_obtain = "Echo Chamber Key"
        interaction_count = 0

        while True:
            interaction_count += 1
            console.rule(f"Interaction {interaction_count}", style="bold magenta")
            console.line(1)
            
            # Capture state before player action for this turn's comparison
            old_disposition_for_turn = npc.relationship_to_player
            old_npc_items_for_turn = list(npc.items)
            old_player_items_for_turn = list(player1.items)

            player_prompt_text = Text()
            player_prompt_text.append(f"{player1.name} (type '/give <item>' or 'quit' to end): ", style="bold blue")
            player_msg = console.input(player_prompt_text)

            if player_msg.lower() == "quit":
                rprint(Text("Quitting conversation.", style="bold yellow"))
                break

            npc_should_respond_this_turn = False

            if player_msg.lower().startswith("/give "):
                command_parts = player_msg.split(maxsplit=1)
                if len(command_parts) > 1:
                    item_name_to_give = command_parts[1].strip()
                    if not item_name_to_give:
                        rprint(Text("Usage: /give <item_name> (Item name cannot be empty)", style="bold yellow"))
                    elif player1.has_item(item_name_to_give):
                        if player1.remove_item(item_name_to_give): # Player's console output happens here
                            npc.add_item(item_name_to_give)      # NPC gets item silently for now
                            
                            action_description_for_ai = f"I hand the '{item_name_to_give}' over to you."
                            npc.add_dialogue_turn(speaker=player1.name, message=action_description_for_ai)
                            
                            rprint(Text(f"You give the '{item_name_to_give}' to {npc.name}.", style="italic bright_magenta"))
                            npc_should_respond_this_turn = True 
                        else:
                            # This case (remove_item returning False after has_item was True) is unlikely
                            rprint(Text(f"Error: Could not remove '{item_name_to_give}' from your inventory despite possessing it.", style="bold red"))
                    else:
                        rprint(Text(f"You don't have '{item_name_to_give}' in your inventory.", style="bold red"))
                else:
                    rprint(Text("Usage: /give <item_name>", style="bold yellow"))
                
                if not npc_should_respond_this_turn:
                    console.line(1) # Maintain spacing before next player prompt if turn is skipped for NPC
                    continue 
            else: # Regular dialogue
                if not player_msg.strip():
                    rprint(Text("Please type a message or a command.", style="yellow"))
                    console.line(1)
                    continue # Skip NPC response if player sent empty message
                npc.add_dialogue_turn(speaker=player1.name, message=player_msg)
                npc_should_respond_this_turn = True

            if npc_should_respond_this_turn:
                ai_response = npc.get_ai_response(player_object=player1)
                console.line(1)

                if ai_response:
                    npc_turn_text = Text()
                    npc_turn_text.append(f"{npc.name}: ", style="bold green")
                    npc_turn_text.append(ai_response)
                    rprint(npc_turn_text)
                    # Add AI's spoken response to history (if it wasn't just a tool call with no text)
                    # The get_ai_response now returns the final spoken part, so it's safe to add.
                    if ai_response.strip() and not ai_response.startswith(f"[{npc.name}]"): # Avoid adding placeholder messages
                        npc.add_dialogue_turn(speaker=npc.name, message=ai_response)
                else:
                    rprint(Text(f"[{npc.name} is silent or an error occurred.]", style="italic red"))
            
            console.line(1) 
            state_panel_content = Text()
            current_player_items_str = ", ".join(player1.items) if player1.items else 'None'
            state_panel_content.append(f"Player ({player1.name}) Items: {current_player_items_str}\n", style="blue")
            if old_player_items_for_turn != player1.items:
                state_panel_content.append(f"SYSTEM: Player inventory changed. Old: {old_player_items_for_turn}, New: {player1.items}\n", style="dim bright_blue")
            
            current_npc_items_str = ", ".join(npc.items) if npc.items else 'None'
            state_panel_content.append(f"Character ({npc.name}) Items: {current_npc_items_str}\n", style="green")
            if old_npc_items_for_turn != npc.items:
                 state_panel_content.append(f"SYSTEM: NPC inventory changed. Old: {old_npc_items_for_turn}, New: {npc.items}\n", style="dim bright_green")
            
            state_panel_content.append(f"Character ({npc.name}) Disposition: {npc.relationship_to_player}", style="green")
            if old_disposition_for_turn != npc.relationship_to_player:
                state_panel_content.append(f"\nSYSTEM: NPC disposition changed from '{old_disposition_for_turn}' to '{npc.relationship_to_player}'.", style="bright_cyan")
            
            rprint(Panel(state_panel_content, title="State After Interaction", expand=False, border_style="yellow"))
            console.line()
            
            if not npc.has_item(key_to_obtain) and player1.has_item(key_to_obtain):
                success_text = Text(f"SUCCESS! {player1.name} obtained the '{key_to_obtain}' from {npc.name}!", style="bold bright_green")
                disposition_text = Text(f"{npc.name}'s final disposition: {npc.relationship_to_player}", style="green")
                rprint(Panel(Text.assemble(success_text, "\n", disposition_text), title="Outcome", border_style="bright_green"))
                break

        console.line(1)
        console.rule("Final States", style="bold white")
        console.line(1)
        player_final_text = Text()
        player_final_text.append(f"Name: {player1.name}\n", style="bold")
        player_final_text.append(f"Items: {', '.join(player1.items) if player1.items else 'Nothing'}")
        rprint(Panel(player_final_text, title="Final Player State", border_style="blue"))
        console.line(1)
        
        rprint(Panel(str(npc), title="Final Character State", border_style="green"))

        console.line(1)
        console.rule("Full Conversation History", style="bold white")
        console.line(1)
        history_text = Text()
        if not npc.conversation_history:
             history_text.append("(No conversation took place)", style="italic dim white")
        else:
            for turn in npc.conversation_history:
                speaker_style = "bold blue" if turn['speaker'] == player1.name else "bold green"
                history_text.append(f"{turn['speaker']}: ", style=speaker_style)
                history_text.append(f"{turn['message']}\n\n")
        rprint(Panel(history_text, title=f"History with {npc.name}", border_style="dim white"))

    except ValueError as ve:
        rprint(Panel(Text(str(ve), style="bold red"), title="Configuration Error"))
    except ImportError as ie:
        rprint(Panel(Text(str(ie), style="bold red"), title="Import Error"))
    except Exception as e:
        console.print_exception(show_locals=True)

