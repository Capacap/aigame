from __future__ import annotations
import json

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

def handle_player_action(player1: Player, npc: Character, player_msg: str) -> bool:
    """Handles the player's action, whether it's a command or dialogue. Returns True if NPC should respond."""
    if player_msg.lower().startswith("/give "):
        command_parts = player_msg.split(maxsplit=1)
        if len(command_parts) > 1:
            item_name_to_give = command_parts[1].strip()
            if not item_name_to_give:
                rprint(Text("Usage: /give <item_name> (Item name cannot be empty)", style="bold yellow"))
                return False 
            elif player1.has_item(item_name_to_give):
                item_to_give_obj = next((item for item in player1.items if item.name == item_name_to_give), None)
                if item_to_give_obj and player1.remove_item(item_name_to_give): # remove_item itself prints messages
                    npc.add_item(item_to_give_obj) # add_item in Character also prints messages
                    action_description_for_ai = f"I hand the '{item_name_to_give}' over to you."
                    npc.add_dialogue_turn(speaker=player1.name, message=action_description_for_ai)
                    # Message about successful give is now handled by Player.remove_item and Character.add_item
                    # rprint(Text(f"You give the '{item_name_to_give}' to {npc.name}.", style="italic bright_magenta"))
                    return True 
                else:
                    rprint(Text(f"Error: Could not transfer '{item_name_to_give}'. Check inventory or item status.", style="bold red"))
                    return False 
            else:
                rprint(Text(f"You don't have '{item_name_to_give}' in your inventory.", style="bold red"))
                return False 
        else:
            rprint(Text("Usage: /give <item_name>", style="bold yellow"))
            return False 
    else: 
        if not player_msg.strip():
            rprint(Text("Please type a message or a command.", style="yellow"))
            console.line(1) # Add a bit of space after the prompt
            return False 
        npc.add_dialogue_turn(speaker=player1.name, message=player_msg)
        return True 
    # Fallback, should ideally be covered by branches above
    return False 

def handle_npc_response(npc: Character, player_object: Player, current_location: Location):
    """Handles getting and printing the NPC's response."""
    ai_response = npc.get_ai_response(player_object=player_object, current_location=current_location)
    console.line(1)

    if ai_response:
        npc_turn_text = Text()
        npc_turn_text.append(f"{npc.name}: ", style="bold green")
        npc_turn_text.append(ai_response)
        rprint(npc_turn_text)
        # Add to history only if it's a meaningful spoken response, not just an internal thought prompt
        if ai_response.strip() and not ai_response.startswith(f"[{npc.name}]"):
            npc.add_dialogue_turn(speaker=npc.name, message=ai_response)
    else:
        # This case might mean an error in get_ai_response or a deliberate empty response.
        # get_ai_response already prints errors.
        # If it's a deliberate empty (None) response and we want a placeholder:
        rprint(Text(f"[{npc.name} is silent or an error occurred determining a response.]", style="italic red"))

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
            if npc: npc.add_dialogue_turn(speaker="Game Master", message=epilogue)
            console.line()
            break

        npc_should_respond_this_turn = handle_player_action(player1, npc, player_msg)

        # NPC's turn (if applicable)
        if npc_should_respond_this_turn:
            handle_npc_response(npc, player1, current_location)
        else:
            # Specific handling for spacing if NPC doesn't respond due to failed command, etc.
            # handle_player_action takes care of its own spacing for empty messages.
            # If /give command failed, handle_player_action prints a message. Add a line for visual separation.
            if player_msg.lower().startswith("/give "): # and not npc_should_respond_this_turn is implied
                 console.line(1) # Add a bit of space after failed /give command output
                 # We might want to skip display_interaction_state if the command itself failed and no game state changed significantly
                 # For now, let it display to show the (unchanged) state.
                 # continue # Option to skip display_interaction_state for failed commands

        # Display state changes after both player and NPC (if any) have acted
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
    if not npc.conversation_history:
            history_text.append("(No conversation took place)", style="italic dim white")
    else:
        num_turns = len(npc.conversation_history)
        for i, turn in enumerate(npc.conversation_history):
            speaker_style = "bold blue" if turn['speaker'] == player1.name else "bold green"
            history_text.append(f"{turn['speaker']}: ", style=speaker_style)
            history_text.append(f"{turn['message']}")
            # Add double newline for better readability between turns, except for the last message
            if i < num_turns - 1: 
                history_text.append("\n\n") # Using escaped newline for Text object
    rprint(Panel(history_text, title=f"History with {npc.name}", border_style="dim white"))

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
            npc.add_dialogue_turn(speaker="Game Master", message=scenario_introduction)

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