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
from .location import Location, load_location_from_file
from .scenario import Scenario, load_scenario_from_file
from .game_master import GameMaster
from .input_parser import InputParser

console = Console()

# Game constants
CHARACTERS_BASE_PATH = "aigame/data/characters"
ITEMS_BASE_PATH = "aigame/data/items"
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
    
    rprint(f"[dim]Type naturally - just say what you want to do![/dim]")
    console.line()

# Regex to capture optional dialogue and an optional /give command
# It captures: (dialogue_part) (full_command_part including /give) (item_name_for_give)
# COMMAND_REGEX = re.compile(r"^(.*?)(?:\s*(\/give\s+(.+)))?$", re.IGNORECASE) # Old regex, no longer needed

def handle_player_action(player1: Player, npc: Character, player_msg: str, current_location: Location) -> bool:
    """
    AI-powered version of handle_player_action that uses natural language parsing.
    Returns True if NPC should respond, or special strings for quit/help.
    """
    parser = InputParser()
    
    # Parse the player input using AI
    parsed_result = parser.parse_player_input(player_msg, player1, npc, current_location)
    
    if not parsed_result['success']:
        rprint(Text(parsed_result['error_message'], style="bold red"))
        console.line(1)
        return False
    
    action_type = parsed_result['action_type']
    parameters = parsed_result['parameters']
    
    # Display input classification with spacing
    console.line()
    rprint(Text(f"Input classified as: {action_type} (confidence: {parsed_result.get('confidence', 0.0):.2f})", style="dim magenta"))
    
    # Handle each action type
    if action_type == 'dialogue':
        message = parameters['message']
        npc.add_dialogue_turn(speaker=player1.name, message=message)
        return True
    
    elif action_type == 'give_item':
        item_name = parameters['item_name']
        original_message = parameters.get('original_message', '')
        
        # Get the exact Item object
        item_to_give_obj = next((item for item in player1.items if item.name.lower() == item_name.lower()), None)
        
        if not item_to_give_obj:
            rprint(Text(f"Error: Could not find the item object for '{item_name}'.", style="bold red"))
            return False
        
        # Set up the offer on the NPC
        npc.active_offer = {
            "item_name": item_to_give_obj.name,
            "item_object": item_to_give_obj,
            "offered_by_name": player1.name,
            "offered_by_object": player1
        }
        
        # Add contextual message to dialogue history
        offer_message = f"*{original_message}*" if original_message else f"*I offer you the {item_to_give_obj.name}.*"
        npc.add_dialogue_turn(speaker=player1.name, message=offer_message)
        
        rprint(f"💝 [dim]You offer the {item_to_give_obj.name} to {npc.name}[/dim]")
        return True
    
    elif action_type == 'trade_proposal':
        player_item_name = parameters['player_item']
        npc_item_name = parameters['npc_item']
        original_message = parameters.get('original_message', '')
        
        # Get the actual Item objects
        player_item_obj = next((item for item in player1.items if item.name.lower() == player_item_name.lower()), None)
        npc_item_obj = next((item for item in npc.items if item.name.lower() == npc_item_name.lower()), None)
        
        if not player_item_obj or not npc_item_obj:
            rprint(Text("Error: Could not find the item objects for the trade.", style="bold red"))
            return False
        
        # Set up the trade proposal on the NPC
        npc.active_trade_proposal = {
            "player_item_name": player_item_obj.name,
            "npc_item_name": npc_item_obj.name,
            "player_item_object": player_item_obj,
            "npc_item_object": npc_item_obj,
            "offered_by_name": player1.name,
            "offered_by_object": player1
        }
        
        # Add contextual message to dialogue history
        trade_message = f"*{original_message}*" if original_message else f"*I propose trading my {player_item_obj.name} for your {npc_item_obj.name}.*"
        npc.add_dialogue_turn(speaker=player1.name, message=trade_message)
        
        rprint(f"🔄 [dim]You propose trading {player_item_obj.name} for {npc_item_obj.name}[/dim]")
        return True
    
    elif action_type == 'request_item':
        item_name = parameters['item_name']
        original_message = parameters.get('original_message', '')
        
        # Get the exact Item object from NPC's inventory
        item_to_request_obj = next((item for item in npc.items if item.name.lower() == item_name.lower()), None)
        
        if not item_to_request_obj:
            rprint(Text(f"Error: Could not find the item object for '{item_name}'.", style="bold red"))
            return False
        
        # Set up the request on the NPC
        npc.active_request = {
            "item_name": item_to_request_obj.name,
            "item_object": item_to_request_obj,
            "requested_by_name": player1.name,
            "requested_by_object": player1
        }
        
        # Add contextual message to dialogue history
        request_message = f"*{original_message}*" if original_message else f"*I would like to have your {item_to_request_obj.name}.*"
        npc.add_dialogue_turn(speaker=player1.name, message=request_message)
        
        rprint(f"🙏 [dim]You ask for the {item_to_request_obj.name}[/dim]")
        return True
    
    elif action_type == 'accept_trade':
        custom_message = parameters.get('custom_message')
        
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
                if custom_message:
                    acceptance_message = f"{custom_message} *I accept your counter-proposal and trade my {player_item_name} for your {npc_item_name}.*"
                else:
                    acceptance_message = f"*I accept your counter-proposal and trade my {player_item_name} for your {npc_item_name}.*"
                
                npc.add_dialogue_turn(speaker=player1.name, message=acceptance_message)
                
                # Get AI response to the completed trade
                ai_response = npc.get_ai_response(player_object=player1, current_location=current_location)
                if ai_response:
                    console.line(1)
                    npc_turn_text = Text()
                    npc_turn_text.append(f"{npc.name}: ", style="bold green")
                    npc_turn_text.append(ai_response)
                    rprint(npc_turn_text)
                
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
        
        return False
    
    elif action_type == 'decline_trade':
        custom_message = parameters.get('custom_message')
        
        # Clear the counter-proposal and inform the NPC
        player_item_name = npc.active_trade_proposal.get("player_item_name", "")
        npc_item_name = npc.active_trade_proposal.get("npc_item_name", "")
        npc.active_trade_proposal = None
        
        # Clear any standing offers to prevent AI confusion
        npc.active_offer = None
        
        # Add the player's decline message to dialogue history
        if custom_message:
            decline_message = f"{custom_message} *I decline your counter-proposal to trade my {player_item_name} for your {npc_item_name}.*"
        else:
            decline_message = f"*I decline your counter-proposal to trade my {player_item_name} for your {npc_item_name}.*"
        
        npc.add_dialogue_turn(speaker=player1.name, message=decline_message)
        
        # Get AI response to the declined counter-proposal
        ai_response = npc.get_ai_response(player_object=player1, current_location=current_location)
        if ai_response:
            console.line(1)
            npc_turn_text = Text()
            npc_turn_text.append(f"{npc.name}: ", style="bold green")
            npc_turn_text.append(ai_response)
            rprint(npc_turn_text)
        
        rprint(f"❌ [dim]You decline the counter-proposal[/dim]")
        return "TRADE_DECLINED"
    
    else:
        rprint(Text(f"Something went wrong processing your input. Please try again.", style="bold yellow"))
        rprint(Text("You can talk to the character, offer items, propose trades, or type 'help' for guidance.", style="dim white"))
        return False

def handle_npc_response(npc: Character, player_object: Player, current_location: Location) -> str | None:
    """
    Enhanced version of handle_npc_response that uses AI action parsing.
    Returns the AI's spoken response string or None.
    """
    
    # Use the new AI action parsing method
    ai_response, action_results = npc.get_ai_response_with_actions(player_object, current_location)
    
    if ai_response:
        # NPC Response Section
        console.line()
        npc_turn_text = Text()
        npc_turn_text.append(f"{npc.name}: ", style="bold green")
        npc_turn_text.append(ai_response)
        rprint(npc_turn_text)
        
        # Action Results Section (if any actions occurred)
        action_feedback = []
        state_changes = action_results.get('state_changes', {})
        
        # Collect item transfer feedback
        if 'item_transferred' in state_changes:
            item_name = state_changes['item_transferred']
            action_feedback.append(f"🎁 [dim]{npc.name} gives you the {item_name}[/dim]")
        
        # Collect offer feedback
        if 'offer_accepted' in state_changes:
            item_name = state_changes['offer_accepted']
            action_feedback.append(f"✅ [dim]{npc.name} accepts your {item_name}[/dim]")
        elif 'offer_declined' in state_changes:
            action_feedback.append(f"❌ [dim]{npc.name} declines your offer[/dim]")
        
        # Collect trade feedback
        if 'trade_completed' in state_changes:
            player_received = state_changes.get('player_received', 'item')
            npc_received = state_changes.get('npc_received', 'item')
            action_feedback.append(f"✅ [bright_green]Trade completed: {npc_received} ↔ {player_received}[/bright_green]")
        elif 'trade_declined' in state_changes:
            action_feedback.append(f"❌ [dim]{npc.name} declines the trade[/dim]")
        
        # Collect counter-proposal feedback
        if 'counter_proposal_made' in state_changes:
            counter_player_item = state_changes.get('counter_player_item', 'item')
            counter_npc_item = state_changes.get('counter_npc_item', 'item')
            action_feedback.append(f"🔄 [bright_cyan]Counter-proposal: {npc.name} wants your {counter_player_item} for their {counter_npc_item}[/bright_cyan]")
        
        # Display action feedback with spacing if any exists
        if action_feedback:
            for feedback in action_feedback:
                rprint(feedback)
        
        # Debug Information Section (separated and minimal)
        classification = action_results.get('classification', {})
        if classification:
            action_types = classification.get('action_types', ['unknown'])
            confidence = classification.get('confidence', 0.0)
            if action_types[0] != 'dialogue_only':  # Only show non-dialogue classifications
                rprint(Text(f"NPC actions detected: {action_types} (confidence: {confidence:.2f})", style="dim magenta"))
        
        # Error Section (if any errors occurred)
        errors = action_results.get('errors', [])
        if errors:
            for error in errors:
                rprint(Text(f"Action error: {error}", style="dim red"))
        
        return ai_response
    else:
        # Error case
        console.line()
        rprint(Text(f"[{npc.name} is silent or an error occurred determining a response.]", style="italic red"))
        return None

def display_interaction_state(player1: Player, npc: Character, old_player_items: list[str], old_npc_items: list[str], old_disposition: str):
    """Displays the state of player and NPC items and disposition after an interaction."""
    
    # Check for important changes that need highlighting
    player_items_changed = old_player_items != [item.name for item in player1.items]
    npc_items_changed = old_npc_items != [item.name for item in npc.items]
    disposition_changed = old_disposition != npc.disposition
    
    # === ACTIVE PROPOSALS SECTION ===
    # Show active counter-proposal prominently if it exists
    if npc.active_trade_proposal:
        offered_by_name = npc.active_trade_proposal.get("offered_by_name", "")
        if offered_by_name == npc.name:  # This is an NPC counter-proposal
            player_item_name = npc.active_trade_proposal.get("player_item_name", "")
            npc_item_name = npc.active_trade_proposal.get("npc_item_name", "")
            console.line()
            rprint(f"🔄 [bold bright_cyan]COUNTER-PROPOSAL: {npc.name} wants your {player_item_name} for their {npc_item_name}[/bold bright_cyan]")
            rprint(f"   [dim cyan]You can accept or decline this offer[/dim cyan]")
            console.line()
    
    # === INVENTORY CHANGES SECTION ===
    # Collect inventory changes
    inventory_changes = []
    if player_items_changed:
        current_items = ', '.join(item.name for item in player1.items) if player1.items else 'None'
        inventory_changes.append(f"👤 [blue]{player1.name}[/blue]: {current_items}")
    
    if npc_items_changed:
        current_items = ', '.join(item.name for item in npc.items) if npc.items else 'None'
        inventory_changes.append(f"🤝 [green]{npc.name}[/green]: {current_items}")
    
    # Display inventory changes with proper spacing
    if inventory_changes:
        console.line()
        for change in inventory_changes:
            rprint(change)
        console.line()
    
    # Note: Removed the redundant "character feels" message since disposition changes 
    # are already shown by the Game Master analysis

def run_interaction_loop(player1: Player, npc: Character, current_location: Location, victory_condition: str, game_master: GameMaster, scenario: Scenario):
    """Handles the main interaction loop between the player and NPC."""
    interaction_count = 0
    game_ended_by_victory = False # Flag to track if victory occurred
    
    # Display available commands at the start
    display_available_commands()
    
    # Handle NPC speaking first if specified in scenario
    if scenario.npc_speaks_first:
        console.line()
        rprint("[dim]The conversation begins...[/dim]")
        console.line()
        
        # Store initial state for comparison
        old_disposition_initial = npc.disposition
        old_npc_items_initial = [item.name for item in npc.items]
        old_player_items_initial = [item.name for item in player1.items]
        
        # NPC speaks first
        npc_opening_response = handle_npc_response(npc, player1, current_location)
        
        # Analyze NPC's opening and update disposition if needed
        if npc_opening_response:
            opening_events = f"Game started; {npc.name} spoke first: {npc_opening_response}"
            game_master.analyze_and_update_disposition(npc, player1, opening_events, scenario)
        
        # Display any state changes from NPC's opening
        display_interaction_state(player1, npc, old_player_items_initial, old_npc_items_initial, old_disposition_initial)
        
        # Check victory condition after NPC's opening (unlikely but possible)
        victory_met, gm_reasoning = game_master.evaluate_victory_condition(player1, npc, victory_condition)
        if victory_met:
            console.line()
            rprint(f"🎯 [dim cyan]Game Master: {gm_reasoning}[/dim cyan]")
            rprint(f"🎉 [bold bright_green]SUCCESS! Victory condition achieved![/bold bright_green]")
            rprint(f"💭 [green]{npc.name}'s final disposition: {npc.disposition}[/green]")
            
            # Provide epilogue for victory
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "VICTORY")
            console.line()
            rprint(Panel(Text(epilogue, justify="left"), title="Victory Achieved!", border_style="bold bright_green", expand=False))
            if npc: npc.add_dialogue_turn(speaker="Game Master", message=epilogue)
            console.line()
            game_ended_by_victory = True
            return
        else:
            # Subtly show progress feedback after NPC opening
            rprint(f"🎯 [dim]Game Master: {gm_reasoning}[/dim]")
    
    while True:
        interaction_count += 1
        
        # Store state before player/NPC turn for comparison
        old_disposition_for_turn = npc.disposition
        old_npc_items_for_turn = [item.name for item in npc.items] # Store names for simple comparison
        old_player_items_for_turn = [item.name for item in player1.items]

        # === PLAYER TURN SECTION ===
        console.line()
        current_items = ', '.join(item.name for item in player1.items) if player1.items else 'None'
        rprint(f"💼 [dim]Your items: {current_items}[/dim]")
        
        player_prompt_text = Text()
        player_prompt_text.append(f"{player1.name}: ", style="bold blue")
        player_msg = console.input(player_prompt_text)

        # Check for quit command directly before AI parsing
        player_msg_stripped = player_msg.strip().lower()
        if player_msg_stripped == 'quit' or player_msg_stripped == '/quit':
            rprint(Text("Quitting conversation.", style="bold yellow"))
            # Provide epilogue for quitting
            epilogue = game_master.provide_epilogue(scenario, player1, npc, "PLAYER_QUIT")
            rprint(Panel(Text(epilogue, justify="left"), title="The Story Pauses...", border_style="bold yellow", expand=False))
            console.line()
            break

        # Check for help command directly before AI parsing
        if player_msg_stripped == 'help' or player_msg_stripped == '/help':
            display_available_commands()
            continue

        action_processed_successfully = handle_player_action(player1, npc, player_msg, current_location)

        if action_processed_successfully == "TRADE_ACCEPTED" or action_processed_successfully == "TRADE_DECLINED":
            # Trade response was already handled in the command, skip to GM assessment
            npc_actual_response_text = "Trade response handled"
        elif not action_processed_successfully:
            # Player input was invalid or a command that failed without dialogue.
            # handle_player_action already printed the relevant error message.
            # Loop back to get new player input.
            console.line() # Add a little space before re-prompting
            continue
        
        # === NPC RESPONSE SECTION ===
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

        # === GAME MASTER ANALYSIS SECTION ===
        # Analyze recent events and update NPC disposition
        if action_processed_successfully:
            # Build a summary of recent events for disposition analysis
            recent_events = []
            
            # Add player action description
            if player_msg.strip():
                recent_events.append(f"Player said/did: {player_msg}")
            
            # Add item changes if any occurred
            current_player_items = [item.name for item in player1.items]
            current_npc_items = [item.name for item in npc.items]
            
            if current_player_items != old_player_items_for_turn:
                items_gained = [item for item in current_player_items if item not in old_player_items_for_turn]
                items_lost = [item for item in old_player_items_for_turn if item not in current_player_items]
                if items_gained:
                    recent_events.append(f"Player gained items: {', '.join(items_gained)}")
                if items_lost:
                    recent_events.append(f"Player lost items: {', '.join(items_lost)}")
            
            if current_npc_items != old_npc_items_for_turn:
                items_gained = [item for item in current_npc_items if item not in old_npc_items_for_turn]
                items_lost = [item for item in old_npc_items_for_turn if item not in current_npc_items]
                if items_gained:
                    recent_events.append(f"{npc.name} gained items: {', '.join(items_gained)}")
                if items_lost:
                    recent_events.append(f"{npc.name} lost items: {', '.join(items_lost)}")
            
            # Add NPC response if there was one
            if npc_actual_response_text:
                recent_events.append(f"{npc.name} responded: {npc_actual_response_text}")
            
            # Only analyze if there were meaningful events
            if recent_events:
                events_summary = "; ".join(recent_events)
                game_master.analyze_and_update_disposition(npc, player1, events_summary, scenario)

        # === STATE CHANGES SECTION ===
        # Display state changes after both player and NPC (if any) have acted, and GM assessment
        display_interaction_state(player1, npc, old_player_items_for_turn, old_npc_items_for_turn, old_disposition_for_turn)
            
        # === VICTORY CONDITION CHECK SECTION ===
        # Check victory condition
        victory_met, gm_reasoning = game_master.evaluate_victory_condition(player1, npc, victory_condition)
        if victory_met:
            console.line()
            rprint(f"🎯 [dim cyan]Game Master: {gm_reasoning}[/dim cyan]")
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
        else:
            # Subtly show progress feedback with spacing
            rprint(f"🎯 [dim]Game Master: {gm_reasoning}[/dim]")
            console.line()  # Add extra space before next turn

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
                    # Include all assistant messages with content, even if they have tool calls
                    # The content represents the NPC's spoken dialogue
                    dialogue_turns.append({"speaker": npc.name, "message": content, "style": "green"})

        if not dialogue_turns:
            rprint("[dim]No actual dialogue was exchanged[/dim]")
        else:
            for turn in dialogue_turns:
                rprint(f"[{turn['style']}]{turn['speaker']}:[/{turn['style']}] {turn['message']}")
    
    console.line()

def display_available_commands():
    """Displays natural language examples for the AI-powered input system."""
    console.line()
    rprint("[bold cyan]You can interact naturally! Here are some examples:[/bold cyan]")
    rprint("  [bright_white]Talk:[/bright_white] 'Hello there!' or 'How are you today?'")
    rprint("  [bright_white]Give items:[/bright_white] 'Here, take my sword' or 'I offer you this potion'")
    rprint("  [bright_white]Request items:[/bright_white] 'Can I have your map?' or 'I really need that key'")
    rprint("  [bright_white]Propose trades:[/bright_white] 'I'll trade my coins for your key' or 'Want to swap items?'")
    rprint("  [bright_white]Accept trades:[/bright_white] 'That sounds good, I accept' or 'Deal!'")
    rprint("  [bright_white]Decline trades:[/bright_white] 'No thanks' or 'I decline your offer'")
    rprint("  [bright_white]Get help:[/bright_white] '/help' or 'help'")
    rprint("  [bright_white]Quit:[/bright_white] '/quit' or 'quit'")
    console.line()
    rprint("[dim]Just type naturally - the AI will understand what you want to do![/dim]")
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