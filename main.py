from player import Player
from character import Character, load_character_from_file
from item import Item, load_item_from_file
from location import Location, load_location_from_file
import json

# Rich imports
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from rich.console import Console

console = Console()

# Game constants
CHARACTERS_BASE_PATH = "aigame/data/characters"
ITEMS_BASE_PATH = "aigame/data/items"
LOCATIONS_BASE_PATH = "aigame/data/locations"
NPC_NAME_TO_LOAD = "Archivist Silas"
PLAYER_CHARACTER_NAME = "Alex the Scholar"
STARTING_LOCATION_NAME = "Archive Study"

def initialize_game_entities():
    """Initializes the player, NPC, and starting location for the game."""
    
    # Load player character data and create Player object
    try:
        player_character_data = load_character_from_file(PLAYER_CHARACTER_NAME, CHARACTERS_BASE_PATH)
        player1 = Player(character_data=player_character_data)
        # Player's starting items are now handled by their character JSON definition.
        # The Player constructor copies these items.
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load player character '{PLAYER_CHARACTER_NAME}' from '{CHARACTERS_BASE_PATH}'. Details: {e}[/bold red]")
        raise SystemExit(f"Error loading player character '{PLAYER_CHARACTER_NAME}': {e}")

    # Load NPC
    try:
        npc = load_character_from_file(NPC_NAME_TO_LOAD, CHARACTERS_BASE_PATH)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e: # Combined error catching for character loading
        rprint(f"[bold red]Critical Error: Failed to load or parse character '{NPC_NAME_TO_LOAD}' from '{CHARACTERS_BASE_PATH}'. Details: {e}[/bold red]")
        raise SystemExit(f"Error loading character '{NPC_NAME_TO_LOAD}': {e}")
    
    # Load starting location
    try:
        current_location = load_location_from_file(STARTING_LOCATION_NAME, LOCATIONS_BASE_PATH)
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[bold red]Critical Error: Failed to load starting location '{STARTING_LOCATION_NAME}' from '{LOCATIONS_BASE_PATH}'. Details: {e}[/bold red]")
        raise SystemExit(f"Error loading location '{STARTING_LOCATION_NAME}': {e}")

    return player1, npc, current_location

def display_initial_state(player, npc, location):
    """Displays the initial state of the player, NPC, and current location."""
    # Display Location first
    rprint(Panel(Text(f"{location.name}\n\n{location.description}"), title="Current Location", border_style="yellow", expand=False))
    console.line()

    # Display Player State (using player1.name which comes from the Character object)
    player_state_text = Text()
    player_state_text.append(f"Name: {player.name}\\n", style="bold")
    player_state_text.append(f"Items: {', '.join(item.name for item in player.items) if player.items else 'Nothing'}")
    rprint(Panel(player_state_text, title="Player Initial State", border_style="blue"))
    console.line()

    rprint(Panel(str(npc), title="Character Initial State", border_style="green"))
    console.line()
    rprint(Panel(f"Starting Interactive Conversation with {npc.name}... (Type 'quit' to end)", title_align="center", border_style="dim white"))

def run_interaction_loop(player1, npc, key_to_obtain, current_location):
    """Handles the main interaction loop between the player and NPC."""
    interaction_count = 0
    while True:
        interaction_count += 1
        console.rule(f"Interaction {interaction_count}", style="bold magenta")
        console.line(1)
        
        old_disposition_for_turn = npc.disposition
        old_npc_items_for_turn = [item.name for item in npc.items]
        old_player_items_for_turn = [item.name for item in player1.items]

        player_prompt_text = Text()
        player_prompt_text.append(f"{player1.name} (type '/give <item>' or 'quit' to end): ", style="bold blue")
        player_msg = console.input(player_prompt_text)

        if player_msg.lower() == "quit":
            rprint(Text("Quitting conversation.", style="bold yellow"))
            break

        npc_should_respond_this_turn = handle_player_action(player1, npc, player_msg)

        if npc_should_respond_this_turn:
            handle_npc_response(npc, player1, current_location) # Pass current_location
        else:
            if not player_msg.lower().startswith("/give ") and not player_msg.strip():
                pass
            elif player_msg.lower().startswith("/give ") and not npc_should_respond_this_turn:
                console.line(1)
            if not npc_should_respond_this_turn and player_msg.lower().startswith("/give "):
                console.line(1)
                continue

        display_interaction_state(player1, npc, old_player_items_for_turn, old_npc_items_for_turn, old_disposition_for_turn)
            
        if not npc.has_item(key_to_obtain) and player1.has_item(key_to_obtain):
            success_text = Text(f"SUCCESS! {player1.name} obtained the '{key_to_obtain}' from {npc.name}!", style="bold bright_green")
            disposition_text = Text(f"{npc.name}'s final disposition: {npc.disposition}", style="green")
            rprint(Panel(Text.assemble(success_text, "\n", disposition_text), title="Outcome", border_style="bright_green"))
            break

def display_interaction_state(player1, npc, old_player_items, old_npc_items, old_disposition):
    """Displays the state of player and NPC items and NPC disposition after an interaction."""
    console.line(1) 
    state_panel_content = Text()
    current_player_items_str = ", ".join(item.name for item in player1.items) if player1.items else 'None'
    state_panel_content.append(f"Player ({player1.name}) Items: {current_player_items_str}\\n", style="blue")
    if old_player_items != [item.name for item in player1.items]:
        state_panel_content.append(f"SYSTEM: Player inventory changed. Old: {old_player_items}, New: {[item.name for item in player1.items]}\\n", style="dim bright_blue")
    
    current_npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else 'None'
    state_panel_content.append(f"Character ({npc.name}) Items: {current_npc_items_str}\\n", style="green")
    if old_npc_items != [item.name for item in npc.items]:
            state_panel_content.append(f"SYSTEM: NPC inventory changed. Old: {old_npc_items}, New: {[item.name for item in npc.items]}\\n", style="dim bright_green")
    
    state_panel_content.append(f"Character ({npc.name}) Disposition: {npc.disposition}", style="green")
    if old_disposition != npc.disposition:
        state_panel_content.append(f"\\nSYSTEM: NPC disposition changed from '{old_disposition}' to '{npc.disposition}'.", style="bright_cyan")
    
    rprint(Panel(state_panel_content, title="State After Interaction", expand=False, border_style="yellow"))
    console.line()

def handle_npc_response(npc, player_object, current_location):
    """Handles getting and printing the NPC's response."""
    ai_response = npc.get_ai_response(player_object=player_object, current_location=current_location) # Pass current_location
    console.line(1)

    if ai_response:
        npc_turn_text = Text()
        npc_turn_text.append(f"{npc.name}: ", style="bold green")
        npc_turn_text.append(ai_response)
        rprint(npc_turn_text)
        if ai_response.strip() and not ai_response.startswith(f"[{npc.name}]"):
            npc.add_dialogue_turn(speaker=npc.name, message=ai_response)
    else:
        rprint(Text(f"[{npc.name} is silent or an error occurred.]", style="italic red"))

def handle_player_action(player1, npc, player_msg):
    """Handles the player's action, whether it's a command or dialogue."""
    if player_msg.lower().startswith("/give "):
        command_parts = player_msg.split(maxsplit=1)
        if len(command_parts) > 1:
            item_name_to_give = command_parts[1].strip()
            if not item_name_to_give:
                rprint(Text("Usage: /give <item_name> (Item name cannot be empty)", style="bold yellow"))
                return False 
            elif player1.has_item(item_name_to_give):
                item_to_give_obj = next((item for item in player1.items if item.name == item_name_to_give), None)
                if item_to_give_obj and player1.remove_item(item_name_to_give):
                    npc.add_item(item_to_give_obj)
                    action_description_for_ai = f"I hand the '{item_name_to_give}' over to you."
                    npc.add_dialogue_turn(speaker=player1.name, message=action_description_for_ai)
                    rprint(Text(f"You give the '{item_name_to_give}' to {npc.name}.", style="italic bright_magenta"))
                    return True 
                else:
                    rprint(Text(f"Error: Could not remove '{item_name_to_give}' from your inventory despite possessing it.", style="bold red"))
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
            console.line(1)
            return False 
        npc.add_dialogue_turn(speaker=player1.name, message=player_msg)
        return True 
    return False 

def main_game_loop():
    try:
        player1, npc, current_location = initialize_game_entities()
        display_initial_state(player1, npc, current_location)

        key_to_obtain = "Echo Chamber Key"
        run_interaction_loop(player1, npc, key_to_obtain, current_location)

        display_final_summary(player1, npc)

    except ValueError as ve:
        rprint(Panel(Text(str(ve), style="bold red"), title="Configuration Error"))
    except ImportError as ie:
        rprint(Panel(Text(str(ie), style="bold red"), title="Import Error"))
    except Exception as e:
        console.print_exception(show_locals=True)

def display_final_summary(player1, npc):
    """Displays the final states of the player and NPC, and the conversation history."""
    console.line(1)
    console.rule("Final States", style="bold white")
    console.line(1)
    player_final_text = Text()
    player_final_text.append(f"Name: {player1.name}\\n", style="bold")
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
            if i < num_turns - 1: 
                history_text.append("\n\n")
    rprint(Panel(history_text, title=f"History with {npc.name}", border_style="dim white"))

if __name__ == '__main__':
    main_game_loop()
