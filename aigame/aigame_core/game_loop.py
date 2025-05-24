from __future__ import annotations
import json
# import re # No longer needed for the new command parsing logic

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

# Core game class imports
from .player import Player
from .character import Character, load_character_from_file
# Item is not directly used in this module's functions but load_item_from_file might be if player items were loaded differently
# For now, character loading handles items. If player needs items loaded directly, uncomment Item and its loader.
# from .item import Item, load_item_from_file 
from .location import Location, load_location_from_file
from .scenario import Scenario, load_scenario_from_file
from .game_master import GameMaster

console = Console()

# Game constants
CHARACTERS_BASE_PATH = "aigame/data/characters"
ITEMS_BASE_PATH = "aigame/data/items" # Kept for potential direct item loading in future
LOCATIONS_BASE_PATH = "aigame/data/locations"
SCENARIOS_BASE_PATH = "aigame/data/scenarios"

def load_scenario_and_entities(scenario_name_to_load: str):
    """Loads the specified scenario and all associated game entities (player, NPC, location)."""
    if not isinstance(scenario_name_to_load, str) or not scenario_name_to_load:
        raise ValueError("Scenario name to load must be a non-empty string.")
    try:
        scenario = load_scenario_from_file(scenario_name_to_load, SCENARIOS_BASE_PATH)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load scenario '{scenario_name_to_load}'. Details: {e}[/bold red]")
        raise
    
    rprint(Panel(str(scenario), title="Scenario Loaded", border_style="purple", expand=False))
    console.line()

    try:
        player_char_data = load_character_from_file(scenario.player_character_name, CHARACTERS_BASE_PATH)
        player = Player(character_data=player_char_data)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load player character '{scenario.player_character_name}' for scenario '{scenario.name}'. Details: {e}[/bold red]")
        raise

    try:
        npc_char_data = load_character_from_file(scenario.npc_character_name, CHARACTERS_BASE_PATH)
        npc = npc_char_data # The Character object itself is the NPC
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load NPC character '{scenario.npc_character_name}' for scenario '{scenario.name}'. Details: {e}[/bold red]")
        raise

    try:
        current_location = load_location_from_file(scenario.location_name, LOCATIONS_BASE_PATH)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load location '{scenario.location_name}' for scenario '{scenario.name}'. Details: {e}[/bold red]")
        raise
    
    return player, npc, current_location, scenario.victory_condition, scenario

def display_initial_state(player: Player, npc: Character, location: Location):
    """Displays the initial state of the player, NPC, and current location."""
    rprint(Panel(Text(f"{location.name}\n\n{location.description}"), title="Current Location", border_style="yellow", expand=False))
    console.line()

    player_state_text = Text()
    player_state_text.append(f"Name: {player.name}\n", style="bold")
    player_state_text.append(f"Items: {', '.join(item.name for item in player.items) if player.items else 'Nothing'}")
    rprint(Panel(player_state_text, title="Player Initial State", border_style="blue"))
    console.line()

    rprint(Panel(str(npc), title="Character Initial State", border_style="green"))
    console.line()
    rprint(Panel(f"Starting Interactive Conversation with {npc.name}... (Type 'quit' to end)", title_align="center", border_style="dim white"))

# Regex to capture optional dialogue and an optional /give command
# It captures: (dialogue_part) (full_command_part including /give) (item_name_for_give)
# COMMAND_REGEX = re.compile(r"^(.*?)(?:\s*(\/give\s+(.+)))?$", re.IGNORECASE) # Old regex, no longer needed

def handle_player_action(player1: Player, npc: Character, player_msg: str) -> bool:
    """Handles the player's action, which must be a sequence of commands. Returns True if NPC should respond."""
    original_player_msg_stripped = player_msg.strip()

    if not original_player_msg_stripped:
        rprint(Text("Please enter a command or a sequence of commands (e.g., /say Hello, /give ItemName).", style="bold yellow"))
        console.line(1)
        return False

    if not original_player_msg_stripped.startswith("/"):
        rprint(Text("All input must start with a command (e.g., /say Hello). Plain text is not processed.", style="bold red"))
        console.line(1)
        return False

    command_segments = original_player_msg_stripped.split('/')[1:] # Split by '/' and remove the initial empty string
    
    npc_should_respond = False
    performed_action_descriptions: list[str] = [] # For AI context if no /say is used
    say_command_executed_this_turn = False

    if not command_segments:
        rprint(Text("No valid commands found. Ensure commands start with '/'.", style="bold yellow"))
        return False

    for segment in command_segments:
        segment_stripped = segment.strip()
        if not segment_stripped:
            continue # Skip empty segments that might result from multiple slashes e.g. /say hi //give item

        parts = segment_stripped.split(maxsplit=1)
        command_verb = parts[0].lower()
        command_args = parts[1].strip() if len(parts) > 1 else ""

        if command_verb == "say":
            if not command_args:
                rprint(Text("Usage: /say <message> (Message cannot be empty)", style="bold yellow"))
                # If a previous command in the chain made NPC respond, don't override that to False
                # continue # Allow processing other commands in the chain
            else:
                npc.add_dialogue_turn(speaker=player1.name, message=command_args)
                npc_should_respond = True
                say_command_executed_this_turn = True
                performed_action_descriptions = [] # Explicit dialogue provides context, clear previous functional actions
        
        elif command_verb == "give":
            item_name_to_give = command_args
            if not item_name_to_give:
                rprint(Text("Usage: /give <item_name> (Item name cannot be empty)", style="bold yellow"))
                continue # Try next command in chain

            if not player1.has_item(item_name_to_give):
                rprint(Text(f"You don't have '{item_name_to_give}' in your inventory to give.", style="bold red"))
                continue # Try next command in chain
            
            # Attempt to get the exact Item object for case consistency and object reference
            item_to_give_obj = next((item for item in player1.items if item.name.lower() == item_name_to_give.lower()), None)
            
            if not item_to_give_obj: # Should be rare if has_item passed, but good for robustness
                rprint(Text(f"Error: Could not find the precise item object for '{item_name_to_give}' after confirming possession.", style="bold red"))
                continue

            # NEW Offer Logic:
            # Set up the offer on the NPC. The NPC's AI must use the 'accept_item_offer' tool to complete the transfer.
            npc.active_offer = {
                "item_name": item_to_give_obj.name,
                "item_object": item_to_give_obj, # Pass the actual item object
                "offered_by_name": player1.name, # Store who made the offer
                "offered_by_object": player1 # Store the player object for later verification
            }
            npc_should_respond = True # NPC should react to being offered an item
            performed_action_descriptions.append(f"*I hold out the {item_to_give_obj.name} for you. Do you accept?*")
            rprint(Text.assemble(Text("EVENT: ", style="dim white"), Text(f"{player1.name} offers {item_to_give_obj.name} to {npc.name}.", style="white")))

        else:
            rprint(Text(f"Unknown command: '/{command_verb}'. Valid commands are /say and /give.", style="bold red"))
            # If player types "/nonsense", we probably don't want NPC to respond unless a /say was also there.
            # If npc_should_respond is already true from a /say, let it be. If not, this unknown command doesn't trigger it.

    # If actions were performed (like /give) but no /say command provided context in this turn,
    # add the functional descriptions for the AI.
    if performed_action_descriptions and npc_should_respond:
        functional_message_for_ai = " ".join(performed_action_descriptions)
        # If a /say command was executed, this functional message should ideally be a new, distinct entry
        # or appended to the existing user message. For now, let's add it as part of the same user turn if there was dialogue.
        # The current add_dialogue_turn will just add it as if the player said it.
        # This might look a bit odd in history if there was also a /say, e.g.:
        # User: Hello there. *I offer the item to you.*
        # This is acceptable for now to ensure AI gets the info.
        npc.add_dialogue_turn(speaker=player1.name, message=functional_message_for_ai)
        # This ensures the AI is aware of the actions. npc_should_respond is already true.

    # If no command successfully set npc_should_respond to True (e.g. only unknown commands, or failed /give with no /say)
    if not npc_should_respond and original_player_msg_stripped: # original_player_msg_stripped ensures we don't say this for initially empty input
        # Check if any command was attempted. If command_segments was populated but npc_should_respond is false,
        # it means all attempted commands failed or were unrecognized without a successful /say.
        if command_segments and not any(s.strip().lower().startswith("say") for s in command_segments):
             rprint(Text("No action taken. Ensure your commands are valid (e.g., /say or /give) and arguments are correct.", style="yellow"))
        # If it started with /say but message was empty, that error is handled above. 
        # This path is for when input was like "/unknown_cmd" or "/give non_existent_item" with no /say.

    return npc_should_respond

def handle_npc_response(npc: Character, player_object: Player, current_location: Location) -> str | None:
    """Handles getting and printing the NPC's response. Returns the AI's spoken response string or None."""
    ai_response = npc.get_ai_response(player_object=player_object, current_location=current_location)
    console.line(1)

    if ai_response:
        npc_turn_text = Text()
        npc_turn_text.append(f"{npc.name}: ", style="bold green")
        npc_turn_text.append(ai_response)
        rprint(npc_turn_text)
        # Add to history only if it's a meaningful spoken response, not just an internal thought prompt
        # This is already handled by character.get_ai_response adding its own spoken part to history.
        # if ai_response.strip() and not ai_response.startswith(f"[{npc.name}]"):
        #     npc.add_dialogue_turn(speaker=npc.name, message=ai_response)
        return ai_response # Return the response for GM assessment
    else:
        # This case might mean an error in get_ai_response or a deliberate empty response.
        # get_ai_response already prints errors.
        # If it's a deliberate empty (None) response and we want a placeholder:
        rprint(Text(f"[{npc.name} is silent or an error occurred determining a response.]", style="italic red"))
        return None # Return None if no response or error

def display_interaction_state(player1: Player, npc: Character, old_player_items: list[str], old_npc_items: list[str], old_disposition: str):
    """Displays the state of player and NPC items and NPC disposition after an interaction."""
    console.line(1) 
    state_panel_content = Text()
    current_player_items_str = ", ".join(item.name for item in player1.items) if player1.items else 'None'
    state_panel_content.append(f"Player ({player1.name}) Items: {current_player_items_str}\n", style="blue")
    
    player_items_changed = old_player_items != [item.name for item in player1.items]
    if player_items_changed:
        state_panel_content.append(f"SYSTEM: Player inventory changed. Old: {old_player_items}, New: {[item.name for item in player1.items]}\n", style="dim bright_blue")
    
    current_npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else 'None'
    state_panel_content.append(f"Character ({npc.name}) Items: {current_npc_items_str}\n", style="green")
    
    npc_items_changed = old_npc_items != [item.name for item in npc.items]
    if npc_items_changed:
            state_panel_content.append(f"SYSTEM: NPC inventory changed. Old: {old_npc_items}, New: {[item.name for item in npc.items]}\n", style="dim bright_green")
    
    state_panel_content.append(f"Character ({npc.name}) Disposition: {npc.disposition}", style="green")
    if old_disposition != npc.disposition:
        state_panel_content.append(f"\nSYSTEM: NPC disposition changed from '{old_disposition}' to '{npc.disposition}'.", style="bright_cyan")
    
    # Only show the panel if something actually changed or it's the first interaction (where old states might be empty)
    # This avoids clutter if an interaction leads to no state changes.
    # However, for debugging or explicit turn-by-turn state, always showing is fine. Let's always show for now.
    rprint(Panel(state_panel_content, title="State After Interaction", expand=False, border_style="yellow"))
    console.line()


def run_interaction_loop(player1: Player, npc: Character, current_location: Location, victory_condition: dict, game_master: GameMaster, scenario: Scenario):
    """Handles the main interaction loop between the player and NPC."""
    interaction_count = 0
    game_ended_by_victory = False # Flag to track if victory occurred
    while True:
        interaction_count += 1
        console.rule(f"Interaction {interaction_count}", style="bold magenta")
        console.line(1) # Adds a blank line after the rule for spacing
        
        # Store state before player/NPC turn for comparison
        old_disposition_for_turn = npc.disposition
        old_npc_items_for_turn = [item.name for item in npc.items] # Store names for simple comparison
        old_player_items_for_turn = [item.name for item in player1.items]

        # Player's turn
        # Display player's current inventory before the prompt
        inventory_text = Text("Your Inventory: ", style="italic dim white")
        if player1.items:
            inventory_text.append(", ".join(item.name for item in player1.items), style="italic white")
        else:
            inventory_text.append("Empty", style="italic dim white")
        rprint(inventory_text)
        console.line(1) # Add a blank line for spacing

        player_prompt_text = Text()
        player_prompt_text.append(f"{player1.name} (type '/give <item>' or 'quit' to end): ", style="bold blue")
        player_msg = console.input(player_prompt_text)

        if player_msg.lower() == "quit":
            rprint(Text("Quitting conversation.", style="bold yellow"))
            # Provide epilogue for quitting
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "PLAYER_QUIT")
            rprint(Panel(Text(epilogue, justify="left"), title="The Story Pauses...", border_style="bold yellow", expand=False))
            # if npc: npc.add_dialogue_turn(speaker="Game Master", message=epilogue) # Epilogue added to history by GM later if needed
            console.line()
            break

        action_processed_successfully = handle_player_action(player1, npc, player_msg)

        if not action_processed_successfully:
            # Player input was invalid or a command that failed without dialogue.
            # handle_player_action already printed the relevant error message.
            # Loop back to get new player input.
            console.line() # Add a little space before re-prompting
            continue
        
        # Get NPC's response *before* GM disposition assessment for this turn's full context
        # The npc_response variable will store the textual response of the NPC for the GM
        npc_actual_response_text = None 

        # NPC's turn (if applicable)
        if action_processed_successfully: # If true, it means player did something that might elicit a response
            npc_actual_response_text = handle_npc_response(npc, player1, current_location) 
        else:
            # This else block might not be strictly necessary anymore if 'continue' is used for failed actions.
            # However, handle_player_action returns false for empty input, or input not starting with /,
            # or for failed commands *without dialogue*. In these cases, we `continue` above.
            # If handle_player_action were to return true but somehow NPC shouldn't respond (which is not current design),
            # this block would be hit. For now, it is defensive.
            pass # No NPC response needed if action_processed_successfully was false and we didn't continue.

        # Game Master assesses disposition change after player action and NPC response (if any)
        # Ensure player_msg for GM is the actual dialogue, not the /give command text itself
        # If player_msg was a /give command, use the action_description_for_ai that was put into history
        # However, handle_player_action already adds the correct user message to history for the GM.
        # The GM can pull from the history, or we pass player_msg and npc_actual_response_text directly.
        # For simplicity, let's ensure player_msg sent to GM is the one AI sees (already handled by add_dialogue_turn)
        # The interaction history will have the player's turn. The npc_actual_response_text is the npc's direct reply.
        
        # Capture the last player message from history for the GM, as handle_player_action might modify it (e.g. for /give)
        # Or, more simply, pass the original player_msg and the npc_actual_response_text directly.
        # Let's pass player_msg (original input) and npc_actual_response_text.
        
        should_change_disp, new_disp, reason_for_change = game_master.assess_disposition_change(
            player=player1, 
            npc=npc, 
            player_message=player_msg, # Original player input for this turn
            npc_response=npc_actual_response_text # NPC's verbal response this turn
        )

        if should_change_disp and new_disp:
            old_disposition_for_gm_change = npc.disposition # Store before GM changes it
            npc.disposition = new_disp
            # Log the GM's decision to interaction_history for full context if needed for future AI reference
            gm_log_message = f"SYSTEM_OBSERVATION (Game Master): NPC disposition changed to '{new_disp}'. Reason: {reason_for_change}"
            npc.interaction_history.add_entry(role="system", content=gm_log_message)
            # The display_interaction_state will show the change, but we can add a specific GM note if desired
            rprint(Text(f"GAME MASTER: {npc.name}'s disposition is now '{new_disp}'. (Reason: {reason_for_change})", style="italic bright_magenta"))
            # We need to update old_disposition_for_turn if GM changed it, so display_interaction_state highlights it correctly.
            # However, display_interaction_state compares with the start-of-turn disposition. 
            # The GM change will be reflected as a change within the turn.
            # The `old_disposition_for_turn` is correctly what it was at the very start of this interaction_count.

        # Display state changes after both player and NPC (if any) have acted, and GM assessment
        display_interaction_state(player1, npc, old_player_items_for_turn, old_npc_items_for_turn, old_disposition_for_turn)
            
        # Check victory condition
        if game_master.evaluate_victory_condition(player1, npc, victory_condition):
            success_text = Text(f"SUCCESS! Victory condition met for the scenario!", style="bold bright_green")
            final_disposition_text = Text(f"{npc.name}'s final disposition: {npc.disposition}", style="green")
            rprint(Panel(Text.assemble(success_text, "\n", final_disposition_text), title="Scenario Outcome", border_style="bright_green"))
            
            # Provide epilogue for victory
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "VICTORY")
            rprint(Panel(Text(epilogue, justify="left"), title="Victory Achieved!", border_style="bold bright_green", expand=False))
            if npc: npc.add_dialogue_turn(speaker="Game Master", message=epilogue)
            console.line()
            game_ended_by_victory = True # Set flag
            break # Exit loop on victory

def display_final_summary(player1: Player, npc: Character):
    """Displays the final states of the player and NPC, and the conversation history."""
    console.line(1)
    console.rule("Final States", style="bold white")
    console.line(1)
    player_final_text = Text()
    player_final_text.append(f"Name: {player1.name}\n", style="bold")
    player_final_text.append(f"Items: {', '.join(item.name for item in player1.items) if player1.items else 'Nothing'}")
    rprint(Panel(player_final_text, title="Final Player State", border_style="blue"))
    console.line(1)
    
    rprint(Panel(str(npc), title="Final Character State", border_style="green"))

    console.line(1)
    console.rule("Full Conversation History", style="bold white")
    console.line(1)
    history_text = Text()
    full_history = npc.interaction_history.get_llm_history()
    if not full_history:
            history_text.append("(No conversation took place)", style="italic dim white")
    else:
        dialogue_turns = []
        for entry in full_history:
            if entry["role"] == "user":
                dialogue_turns.append({"speaker": player1.name, "message": entry["content"], "style": "bold blue"})
            elif entry["role"] == "assistant" and entry["content"]:
                # Only include assistant messages that have actual content (spoken responses)
                # Exclude tool call requests or purely functional messages without text for the player.
                if not entry.get("tool_calls"): # If it has tool_calls, it's a request, not spoken dialogue yet.
                    dialogue_turns.append({"speaker": npc.name, "message": entry["content"], "style": "bold green"})
            # We are not displaying system messages or tool results in the final summary for brevity,
            # but they are in npc.interaction_history if needed for debugging.

        if not dialogue_turns:
            history_text.append("(No actual dialogue was exchanged)", style="italic dim white")
        else:
            num_dialogue_turns = len(dialogue_turns)
            for i, turn in enumerate(dialogue_turns):
                history_text.append(f"{turn['speaker']}: ", style=turn['style'])
                history_text.append(f"{turn['message']}")
                if i < num_dialogue_turns - 1:
                    history_text.append("\n\n")

    rprint(Panel(history_text, title=f"History with {npc.name}", border_style="dim white"))

    # Raw Interaction Log Dump for Debugging
    console.line(1)
    console.rule("Raw Interaction Log (Debug)", style="bold yellow")
    raw_history = npc.interaction_history.get_llm_history()
    if not raw_history:
        rprint(Text("(Interaction log is empty)", style="dim"))
    else:
        for i, entry in enumerate(raw_history):
            rprint(f"[yellow]Log Entry {i}:[/yellow] {entry}")
    console.line(1)

def start_game(scenario_name_to_load: str):
    """Initializes and runs the main game loop for the specified scenario."""
    if not isinstance(scenario_name_to_load, str) or not scenario_name_to_load:
        rprint(Panel(Text("Fatal Game Error: No scenario name provided to start_game.", style="bold red"), title="Configuration Error"))
        return # Early exit if no scenario name is provided
    try:
        player1, npc, current_location, victory_condition, scenario_obj = load_scenario_and_entities(scenario_name_to_load)
        game_master = GameMaster()

        # Introduce the scenario using the GameMaster
        scenario_introduction = game_master.introduce_scenario(scenario_obj)
        rprint(Panel(Text(scenario_introduction, justify="left"), title="A New Adventure Begins...", border_style="bold bright_yellow", expand=False))
        console.line()
        
        # Add GM's introduction to NPC's conversation history for context
        # This is important so the NPC is aware of how the game started.
        if npc: # Ensure NPC exists before trying to add to its history
            # npc.add_dialogue_turn(speaker="Game Master", message=scenario_introduction) # OLD way
            npc.interaction_history.add_entry(role="system", content=f"GAME_MASTER_NARRATION: {scenario_introduction}")

        display_initial_state(player1, npc, current_location)
        run_interaction_loop(player1, npc, current_location, victory_condition, game_master, scenario_obj)
        display_final_summary(player1, npc)

    except (FileNotFoundError, json.JSONDecodeError, ValueError) as fe_jv_ve: # Catch specific loading errors
        # These are already printed with context by the loading functions.
        # Re-print a summary error or log it.
        rprint(Panel(Text(f"Game initialization failed: {fe_jv_ve}", style="bold red"), title="Fatal Game Error"))
        # Optionally, could exit here: raise SystemExit("Exiting due to game initialization failure.")
    except ImportError as ie: # Should be less common now with structured project
        rprint(Panel(Text(str(ie), style="bold red"), title="Import Error"))
    except Exception as e: # Catch-all for other unexpected errors during game play
        rprint(Panel(Text(f"An unexpected error occurred during the game: {e}",style="bold red"), title="Unexpected Game Error"))
        console.print_exception(show_locals=False) # show_locals=True can be very verbose

# This allows game_loop.py to be run directly for testing if needed, though main.py is the intended entry point.
if __name__ == '__main__':
    # Example of how to run directly, assuming a default scenario for testing
    start_game(scenario_name_to_load="Echo Chamber Quest") 