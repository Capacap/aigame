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
    # Simplified initial display - just the essentials
    console.line()
    rprint(f"📍 [bold yellow]{location.name}[/bold yellow]")
    rprint(f"   {location.description}")
    console.line()
    
    rprint(f"👤 [bold blue]{player.name}[/bold blue] | Items: [dim]{', '.join(item.name for item in player.items) if player.items else 'None'}[/dim]")
    rprint(f"🤝 [bold green]{npc.name}[/bold green] | Items: [dim]{', '.join(item.name for item in npc.items) if npc.items else 'None'}[/dim]")
    console.line()
    
    rprint(f"[dim]Type '/help' for commands[/dim]")
    console.line()

# Regex to capture optional dialogue and an optional /give command
# It captures: (dialogue_part) (full_command_part including /give) (item_name_for_give)
# COMMAND_REGEX = re.compile(r"^(.*?)(?:\s*(\/give\s+(.+)))?$", re.IGNORECASE) # Old regex, no longer needed

def handle_player_action(player1: Player, npc: Character, player_msg: str, current_location: Location) -> bool:
    """Handles the player's action, which must be a sequence of commands. Returns True if NPC should respond."""
    original_player_msg_stripped = player_msg.strip()

    if not original_player_msg_stripped:
        rprint(Text("Please enter a command or a sequence of commands (e.g., /say Hello, /give ItemName).", style="bold yellow"))
        console.line(1)
        return False

    # Handle backward compatibility for non-slash quit and help
    if original_player_msg_stripped.lower() == "quit":
        return "QUIT"
    
    if original_player_msg_stripped.lower() == "help":
        display_available_commands()
        return "HELP_SHOWN"

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
            rprint(f"💝 [dim]You offer the {item_to_give_obj.name} to {npc.name}[/dim]")

        elif command_verb == "trade":
            # Parse trade command using natural language processing
            if not command_args:
                rprint(Text("Usage: /trade <natural language trade proposal>", style="bold yellow"))
                rprint(Text("Examples: '/trade I offer my bag of coins for your ancient amulet'", style="dim white"))
                rprint(Text("          '/trade my translation cypher for your key'", style="dim white"))
                continue
            
            # Use Game Master to parse the natural language trade proposal
            temp_gm = GameMaster()
            is_valid, player_item_name, npc_item_name, parse_reason = temp_gm.parse_trade_proposal(
                player=player1,
                npc=npc,
                trade_message=command_args
            )
            
            if not is_valid:
                rprint(Text(f"Could not parse trade proposal: {parse_reason}", style="bold red"))
                rprint(Text("Try being more specific about which items you want to trade.", style="dim yellow"))
                rprint(Text("Example: 'I offer my bag of coins for your ancient amulet'", style="dim white"))
                continue
            
            # Get the actual Item objects using the parsed names
            player_item_obj = next((item for item in player1.items if item.name.lower() == player_item_name.lower()), None)
            npc_item_obj = next((item for item in npc.items if item.name.lower() == npc_item_name.lower()), None)
            
            if not player_item_obj or not npc_item_obj:
                rprint(Text(f"Error: Could not find the item objects for the parsed trade.", style="bold red"))
                continue
            
            # Set up the trade proposal on the NPC
            npc.active_trade_proposal = {
                "player_item_name": player_item_obj.name,
                "npc_item_name": npc_item_obj.name,
                "player_item_object": player_item_obj,
                "npc_item_object": npc_item_obj,
                "offered_by_name": player1.name,
                "offered_by_object": player1
            }
            npc_should_respond = True # NPC should react to the trade proposal
            performed_action_descriptions.append(f"*{command_args}*")
            rprint(f"🔄 [dim]You propose trading {player_item_obj.name} for {npc_item_obj.name}[/dim]")

        elif command_verb == "accept":
            # Accept an NPC's counter-proposal
            if not npc.active_trade_proposal:
                rprint(Text("There is no active trade proposal to accept.", style="bold red"))
                continue
            
            # Check if this is an NPC counter-proposal (offered_by_name should be the NPC's name)
            offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
            if offered_by_name != npc.name:
                rprint(Text("There is no NPC counter-proposal to accept. Use /trade to make a new proposal.", style="bold red"))
                continue
            
            # Execute the trade from the counter-proposal
            player_item_name = npc.active_trade_proposal.get("player_item_name", "")
            npc_item_name = npc.active_trade_proposal.get("npc_item_name", "")
            player_item_object = npc.active_trade_proposal.get("player_item_object")
            npc_item_object = npc.active_trade_proposal.get("npc_item_object")
            
            if (player_item_object and npc_item_object and 
                player1.has_item(player_item_object) and npc.has_item(npc_item_object)):
                
                if player1.remove_item(player_item_object) and npc.remove_item(npc_item_object):
                    player1.add_item(npc_item_object)  # Player gets NPC's item
                    npc.add_item(player_item_object)   # NPC gets player's item
                    rprint(f"✅ [bright_green]Trade completed: {player_item_name} ↔ {npc_item_name}[/bright_green]")
                    npc.active_trade_proposal = None
                    
                    # Clear any standing offers to prevent AI confusion
                    npc.active_offer = None
                    
                    # Add system message to inform AI about the completed trade
                    trade_completion_message = f"SYSTEM_ALERT: Trade completed successfully. You just traded your '{npc_item_name}' for the player's '{player_item_name}'. The exchange is done. Respond naturally to this completed transaction."
                    npc.interaction_history.add_entry(role="system", content=trade_completion_message)
                    
                    # Add the player's acceptance message to dialogue history
                    npc.add_dialogue_turn(speaker=player1.name, message=f"*I accept your counter-proposal and trade my {player_item_name} for your {npc_item_name}.*")
                    
                    # Get AI response to the completed trade
                    ai_response = npc.get_ai_response(player_object=player1, current_location=current_location)
                    if ai_response:
                        console.line(1)
                        npc_turn_text = Text()
                        npc_turn_text.append(f"{npc.name}: ", style="bold green")
                        npc_turn_text.append(ai_response)
                        rprint(npc_turn_text)
                    
                    # Return special value to indicate response was handled
                    return "TRADE_ACCEPTED"
                else:
                    rprint(Text("Trade failed due to item transfer error.", style="bold red"))
                    npc.active_trade_proposal = None
            else:
                missing_items = []
                if not player1.has_item(player_item_object):
                    missing_items.append(f"You no longer have '{player_item_name}'")
                if not npc.has_item(npc_item_object):
                    missing_items.append(f"{npc.name} no longer has '{npc_item_name}'")
                rprint(Text(f"Cannot complete trade - {', '.join(missing_items)}.", style="bold red"))
                npc.active_trade_proposal = None

        elif command_verb == "decline":
            # Decline an NPC's counter-proposal
            if not npc.active_trade_proposal:
                rprint(Text("There is no active trade proposal to decline.", style="bold red"))
                continue
            
            # Check if this is an NPC counter-proposal (offered_by_name should be the NPC's name)
            offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
            if offered_by_name != npc.name:
                rprint(Text("There is no NPC counter-proposal to decline. The current proposal is yours.", style="bold red"))
                continue
            
            # Clear the counter-proposal and inform the NPC
            player_item_name = npc.active_trade_proposal.get("player_item_name", "")
            npc_item_name = npc.active_trade_proposal.get("npc_item_name", "")
            npc.active_trade_proposal = None
            
            # Clear any standing offers to prevent AI confusion
            npc.active_offer = None
            
            # Add the player's decline message to dialogue history
            npc.add_dialogue_turn(speaker=player1.name, message=f"*I decline your counter-proposal to trade my {player_item_name} for your {npc_item_name}.*")
            
            # Get AI response to the declined counter-proposal
            ai_response = npc.get_ai_response(player_object=player1, current_location=current_location)
            if ai_response:
                console.line(1)
                npc_turn_text = Text()
                npc_turn_text.append(f"{npc.name}: ", style="bold green")
                npc_turn_text.append(ai_response)
                rprint(npc_turn_text)
            
            rprint(f"❌ [dim]You decline the counter-proposal[/dim]")
            # Return special value to indicate response was handled
            return "TRADE_DECLINED"

        elif command_verb == "quit":
            # Handle /quit command - return a special value to indicate quit
            return "QUIT"
        
        elif command_verb == "help":
            # Handle /help command - display commands and continue
            display_available_commands()
            # Return special value to indicate help was shown but no NPC response needed
            return "HELP_SHOWN"

        else:
            rprint(Text(f"Unknown command: '/{command_verb}'. Valid commands are /say, /give, /trade, /accept, /decline, /quit, and /help.", style="bold red"))
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
             rprint(Text("No action taken. Ensure your commands are valid (e.g., /say, /give, /trade, /accept, /decline) and arguments are correct.", style="yellow"))
        # If it started with /say but message was empty, that error is handled above. 
        # This path is for when input was like "/unknown_cmd" or "/give non_existent_item" with no /say.

    return npc_should_respond

def handle_npc_response(npc: Character, player_object: Player, current_location: Location) -> str | None:
    """Handles getting and printing the NPC's response. Returns the AI's spoken response string or None."""
    
    # First, handle any standing trade offer before generating dialogue
    trade_response = npc.handle_standing_trade_offer(player_object, current_location)
    
    if trade_response:
        # If there was a trade decision, display it and use it as the complete response
        console.line(1)
        npc_trade_text = Text()
        npc_trade_text.append(f"{npc.name}: ", style="bold green")
        npc_trade_text.append(trade_response)
        rprint(npc_trade_text)
        
        # Add the trade response to dialogue history
        npc.add_dialogue_turn(speaker=npc.name, message=trade_response)
        
        # Return the trade response as the complete NPC response for this turn
        return trade_response
    
    # Only get regular AI response if there was no trade decision
    ai_response = npc.get_ai_response(player_object=player_object, current_location=current_location)
    console.line(1)

    if ai_response:
        npc_turn_text = Text()
        npc_turn_text.append(f"{npc.name}: ", style="bold green")
        npc_turn_text.append(ai_response)
        rprint(npc_turn_text)
        return ai_response
    else:
        # This case might mean an error in get_ai_response or a deliberate empty response.
        rprint(Text(f"[{npc.name} is silent or an error occurred determining a response.]", style="italic red"))
        return None

def display_interaction_state(player1: Player, npc: Character, old_player_items: list[str], old_npc_items: list[str], old_disposition: str, old_direction: str = ""):
    """Displays the state of player and NPC items, disposition, and direction after an interaction."""
    
    # Check for important changes that need highlighting
    player_items_changed = old_player_items != [item.name for item in player1.items]
    npc_items_changed = old_npc_items != [item.name for item in npc.items]
    disposition_changed = old_disposition != npc.disposition
    direction_changed = old_direction != npc.direction
    
    # Show active counter-proposal prominently if it exists
    if npc.active_trade_proposal:
        offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
        if offered_by_name == npc.name:  # This is an NPC counter-proposal
            player_item_name = npc.active_trade_proposal.get("player_item_name", "")
            npc_item_name = npc.active_trade_proposal.get("npc_item_name", "")
            console.line()
            rprint(f"🔄 [bold bright_cyan]COUNTER-PROPOSAL: {npc.name} wants your {player_item_name} for their {npc_item_name}[/bold bright_cyan]")
            rprint(f"   [dim cyan]Use /accept or /decline to respond[/dim cyan]")
    
    # Only show changes if something actually changed
    changes_to_show = []
    
    if player_items_changed:
        current_items = ', '.join(item.name for item in player1.items) if player1.items else 'None'
        changes_to_show.append(f"👤 [blue]{player1.name}[/blue]: {current_items}")
    
    if npc_items_changed:
        current_items = ', '.join(item.name for item in npc.items) if npc.items else 'None'
        changes_to_show.append(f"🤝 [green]{npc.name}[/green]: {current_items}")
    
    if disposition_changed:
        changes_to_show.append(f"💭 [cyan]{npc.name} feels: {npc.disposition}[/cyan]")
    
    if direction_changed and npc.direction:
        changes_to_show.append(f"🎯 [yellow]Story direction: {npc.direction}[/yellow]")
    
    # Only display if there are changes to show
    if changes_to_show:
        console.line()
        for change in changes_to_show:
            rprint(change)
    
    console.line()


def run_interaction_loop(player1: Player, npc: Character, current_location: Location, victory_condition: dict, game_master: GameMaster, scenario: Scenario):
    """Handles the main interaction loop between the player and NPC."""
    interaction_count = 0
    game_ended_by_victory = False # Flag to track if victory occurred
    
    # Display available commands at the start
    display_available_commands()
    
    while True:
        interaction_count += 1
        
        # Store state before player/NPC turn for comparison
        old_disposition_for_turn = npc.disposition
        old_direction_for_turn = npc.direction
        old_npc_items_for_turn = [item.name for item in npc.items] # Store names for simple comparison
        old_player_items_for_turn = [item.name for item in player1.items]

        # Player's turn - simplified display
        current_items = ', '.join(item.name for item in player1.items) if player1.items else 'None'
        rprint(f"💼 [dim]Your items: {current_items}[/dim]")
        
        player_prompt_text = Text()
        player_prompt_text.append(f"{player1.name}: ", style="bold blue")
        player_msg = console.input(player_prompt_text)

        action_processed_successfully = handle_player_action(player1, npc, player_msg, current_location)

        if action_processed_successfully == "QUIT":
            rprint(Text("Quitting conversation.", style="bold yellow"))
            # Provide epilogue for quitting
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "PLAYER_QUIT")
            rprint(Panel(Text(epilogue, justify="left"), title="The Story Pauses...", border_style="bold yellow", expand=False))
            console.line()
            break

        if action_processed_successfully == "HELP_SHOWN":
            # Help was displayed, continue to next interaction without NPC response
            continue

        if action_processed_successfully == "TRADE_ACCEPTED" or action_processed_successfully == "TRADE_DECLINED":
            # Trade response was already handled in the command, skip to GM assessment
            npc_actual_response_text = "Trade response handled"
        elif not action_processed_successfully:
            # Player input was invalid or a command that failed without dialogue.
            # handle_player_action already printed the relevant error message.
            # Loop back to get new player input.
            console.line() # Add a little space before re-prompting
            continue
        
        # Get NPC's response *before* GM disposition assessment for this turn's full context
        # The npc_response variable will store the textual response of the NPC for the GM
        npc_actual_response_text = None 

        # NPC's turn (if applicable)
        if action_processed_successfully and action_processed_successfully not in ["TRADE_ACCEPTED", "TRADE_DECLINED"]: # If true, it means player did something that might elicit a response
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
            # Removed verbose GM message - the change will be shown in display_interaction_state
            # We need to update old_disposition_for_turn if GM changed it, so display_interaction_state highlights it correctly.
            # However, display_interaction_state compares with the start-of-turn disposition. 
            # The GM change will be reflected as a change within the turn.
            # The `old_disposition_for_turn` is correctly what it was at the very start of this interaction_count.

        # Game Master assesses narrative direction after disposition assessment
        should_provide_direction, new_direction, direction_reason = game_master.assess_narrative_direction(
            player=player1,
            npc=npc,
            scenario=scenario,
            player_message=player_msg,
            npc_response=npc_actual_response_text,
            victory_condition=victory_condition
        )

        if should_provide_direction and new_direction:
            old_direction = npc.direction
            npc.direction = new_direction
            # Log the GM's direction decision to interaction_history
            gm_direction_message = f"NARRATIVE_DIRECTION (Game Master): {new_direction}. Reason: {direction_reason}"
            npc.interaction_history.add_entry(role="system", content=gm_direction_message)
            # Removed verbose GM direction message - the change will be shown in display_interaction_state

        # Display state changes after both player and NPC (if any) have acted, and GM assessment
        display_interaction_state(player1, npc, old_player_items_for_turn, old_npc_items_for_turn, old_disposition_for_turn, old_direction_for_turn)
            
        # Check victory condition
        if game_master.evaluate_victory_condition(player1, npc, victory_condition):
            console.line()
            rprint(f"🎉 [bold bright_green]SUCCESS! Victory condition achieved![/bold bright_green]")
            rprint(f"💭 [green]{npc.name}'s final disposition: {npc.disposition}[/green]")
            
            # Provide epilogue for victory
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "VICTORY")
            console.line()
            rprint(Panel(Text(epilogue, justify="left"), title="Victory Achieved!", border_style="bold bright_green", expand=False))
            if npc: npc.add_dialogue_turn(speaker="Game Master", message=epilogue)
            console.line()
            game_ended_by_victory = True # Set flag
            break # Exit loop on victory

def display_final_summary(player1: Player, npc: Character):
    """Displays the final states of the player and NPC, and the conversation history."""
    console.line()
    rprint("[bold white]═══ Final Summary ═══[/bold white]")
    console.line()
    
    # Final states in simple format
    player_items = ', '.join(item.name for item in player1.items) if player1.items else 'None'
    npc_items = ', '.join(item.name for item in npc.items) if npc.items else 'None'
    
    rprint(f"👤 [bold blue]{player1.name}[/bold blue] | Items: {player_items}")
    rprint(f"🤝 [bold green]{npc.name}[/bold green] | Items: {npc_items} | Disposition: {npc.disposition}")
    
    # Conversation history in simple format
    console.line()
    rprint("[bold white]Conversation:[/bold white]")
    
    full_history = npc.interaction_history.get_llm_history()
    if not full_history:
        rprint("[dim]No conversation took place[/dim]")
    else:
        dialogue_turns = []
        for entry in full_history:
            if entry["role"] == "user":
                content = entry.get("content", "")
                if content:  # Only add if there's actual content
                    dialogue_turns.append({"speaker": player1.name, "message": content, "style": "blue"})
            elif entry["role"] == "assistant":
                content = entry.get("content", "")
                if content:  # Only include assistant messages that have actual content (spoken responses)
                    # Exclude tool call requests or purely functional messages without text for the player.
                    if not entry.get("tool_calls"): # If it has tool_calls, it's a request, not spoken dialogue yet.
                        dialogue_turns.append({"speaker": npc.name, "message": content, "style": "green"})

        if not dialogue_turns:
            rprint("[dim]No actual dialogue was exchanged[/dim]")
        else:
            for turn in dialogue_turns:
                rprint(f"[{turn['style']}]{turn['speaker']}:[/{turn['style']}] {turn['message']}")
    
    console.line()

def display_available_commands():
    """Displays all available commands to the user."""
    console.line()
    rprint("[bold cyan]Commands:[/bold cyan]")
    rprint("  [bright_white]/say[/bright_white] <message> - Talk to the character")
    rprint("  [bright_white]/give[/bright_white] <item> - Offer an item")
    rprint("  [bright_white]/trade[/bright_white] <proposal> - Propose a trade")
    rprint("  [bright_white]/accept[/bright_white] - Accept counter-proposal")
    rprint("  [bright_white]/decline[/bright_white] - Decline counter-proposal")
    rprint("  [bright_white]/quit[/bright_white] - End conversation")
    rprint("  [bright_white]/help[/bright_white] - Show commands")
    console.line()

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