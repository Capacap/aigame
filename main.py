import os
import sys
import json
from aigame.aigame_core.game_loop import start_game
from aigame.aigame_core.config import LLM_DEBUG_MODE
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich.columns import Columns
from rich.table import Table

console = Console()

SCENARIOS_DIR_PATH = "aigame/data/scenarios/"
CHARACTERS_DIR_PATH = "aigame/data/characters/"
LOCATIONS_DIR_PATH = "aigame/data/locations/"

def check_debug_mode():
    """Check if debug mode should be enabled via command line or environment variable."""
    # Check command line arguments
    if '--debug' in sys.argv or '-d' in sys.argv:
        return True
    
    # Check environment variable
    if os.getenv('AIGAME_DEBUG', '').lower() in ['true', '1', 'yes', 'on']:
        return True
    
    return False

def enable_debug_mode():
    """Enable LLM debug mode."""
    import aigame.aigame_core.config as config
    config.LLM_DEBUG_MODE = True
    console.print(Panel(
        Text("🐛 Debug Mode Enabled - LLM calls will be tracked", style="bright_yellow"),
        border_style="yellow"
    ))

def load_json_file(file_path: str) -> dict | None:
    """Safely loads a JSON file and returns its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, PermissionError):
        return None

def get_scenario_details(scenario_file: str) -> dict | None:
    """Loads detailed information about a scenario including character and location data."""
    scenario_path = os.path.join(SCENARIOS_DIR_PATH, scenario_file)
    scenario_data = load_json_file(scenario_path)
    
    if not scenario_data:
        return None
    
    # Load character information
    player_char_path = os.path.join(CHARACTERS_DIR_PATH, f"{scenario_data['player_character_name']}.json")
    npc_char_path = os.path.join(CHARACTERS_DIR_PATH, f"{scenario_data['npc_character_name']}.json")
    location_path = os.path.join(LOCATIONS_DIR_PATH, f"{scenario_data['location_name']}.json")
    
    player_data = load_json_file(player_char_path)
    npc_data = load_json_file(npc_char_path)
    location_data = load_json_file(location_path)
    
    return {
        'scenario': scenario_data,
        'player': player_data,
        'npc': npc_data,
        'location': location_data
    }

def estimate_difficulty(scenario_details: dict) -> tuple[str, str]:
    """Estimates scenario difficulty based on victory condition complexity and character traits."""
    if not scenario_details or not scenario_details['scenario']:
        return "Unknown", "gray"
    
    victory_condition = scenario_details['scenario'].get('victory_condition', '').lower()
    npc_data = scenario_details.get('npc', {})
    npc_personality = npc_data.get('personality', '').lower() if npc_data else ''
    
    # Analyze complexity factors
    complexity_score = 0
    
    # Victory condition complexity
    if 'and' in victory_condition:
        complexity_score += 2
    if 'positive disposition' in victory_condition or 'not stern' in victory_condition:
        complexity_score += 2
    if 'charm' in victory_condition or 'understanding' in victory_condition:
        complexity_score += 1
    
    # Character personality complexity
    if any(trait in npc_personality for trait in ['stubborn', 'stern', 'rule-obsessed', 'protective']):
        complexity_score += 2
    if any(trait in npc_personality for trait in ['secret', 'hidden', 'mysterious']):
        complexity_score += 1
    if 'shady' in npc_personality or 'merchant' in npc_personality:
        complexity_score += 1
    
    # Determine difficulty
    if complexity_score <= 2:
        return "Easy", "bright_green"
    elif complexity_score <= 4:
        return "Medium", "bright_yellow"
    else:
        return "Hard", "bright_red"

def create_scenario_panel(scenario_name: str, details: dict, index: int) -> Panel:
    """Creates a rich panel displaying detailed scenario information."""
    if not details:
        return Panel(
            Text("❌ Failed to load scenario details", style="red"),
            title=f"{index}. {scenario_name}",
            border_style="red"
        )
    
    scenario = details['scenario']
    player = details['player']
    npc = details['npc']
    location = details['location']
    
    # Create content sections
    content = Text()
    
    # Description
    content.append("📖 ", style="bright_blue")
    content.append("Story: ", style="bold bright_blue")
    content.append(f"{scenario.get('description', 'No description available')}\n\n", style="white")
    
    # Characters
    content.append("👥 ", style="bright_green")
    content.append("Characters:\n", style="bold bright_green")
    
    if player:
        content.append(f"  • You play as: ", style="dim")
        content.append(f"{player['name']}", style="bold blue")
        if 'goal' in player:
            content.append(f" - {player['goal']}\n", style="dim")
        else:
            content.append("\n")
    
    if npc:
        content.append(f"  • You'll meet: ", style="dim")
        content.append(f"{npc['name']}", style="bold green")
        if 'goal' in npc:
            content.append(f" - {npc['goal']}\n", style="dim")
        else:
            content.append("\n")
    
    content.append("\n")
    
    # Location
    if location:
        content.append("📍 ", style="bright_yellow")
        content.append("Setting: ", style="bold bright_yellow")
        content.append(f"{location['name']}\n", style="bright_yellow")
        content.append(f"   {location.get('description', 'No description available')}\n\n", style="dim")
    
    # Victory condition
    content.append("🎯 ", style="bright_magenta")
    content.append("Goal: ", style="bold bright_magenta")
    victory = scenario.get('victory_condition', 'No victory condition specified')
    # Simplify victory condition for display
    if 'player' in victory.lower() and 'must possess' in victory.lower():
        # Extract key items/conditions
        simplified = victory.replace('The player', 'You must').replace('AND', 'and')
        content.append(f"{simplified}\n\n", style="white")
    else:
        content.append(f"{victory}\n\n", style="white")
    
    # Difficulty and special features
    difficulty, diff_color = estimate_difficulty(details)
    content.append("⚡ ", style="bright_cyan")
    content.append("Difficulty: ", style="bold bright_cyan")
    content.append(f"{difficulty}", style=diff_color)
    
    # Special features
    special_features = []
    if scenario.get('npc_speaks_first'):
        special_features.append("NPC starts conversation")
    if npc and 'secret' in npc.get('personality', '').lower():
        special_features.append("Hidden character traits")
    if 'trade' in victory.lower() or 'haggle' in scenario.get('name', '').lower():
        special_features.append("Trading focus")
    
    if special_features:
        content.append(" | Features: ", style="dim")
        content.append(", ".join(special_features), style="dim cyan")
    
    # Determine border color based on difficulty
    border_colors = {"Easy": "bright_green", "Medium": "bright_yellow", "Hard": "bright_red"}
    border_color = border_colors.get(difficulty, "white")
    
    return Panel(
        content,
        title=f"{index}. {scenario_name}",
        border_style=border_color,
        expand=False
    )

def display_scenarios_detailed() -> list[str]:
    """Displays detailed information about all available scenarios."""
    try:
        all_files = os.listdir(SCENARIOS_DIR_PATH)
        scenario_files = sorted([f for f in all_files if f.endswith(".json")])
    except FileNotFoundError:
        console.print(f"[bold red]Error: Scenarios directory not found at '{SCENARIOS_DIR_PATH}'.[/bold red]")
        return []
    except Exception as e:
        console.print(f"[bold red]Error accessing scenarios directory: {e}[/bold red]")
        return []

    if not scenario_files:
        console.print(f"[bold yellow]No scenarios found in '{SCENARIOS_DIR_PATH}'.[/bold yellow]")
        return []

    # Create header
    console.print(Panel(
        Text("Choose your adventure! Each scenario offers a unique challenge with different characters, settings, and objectives.", 
             justify="center", style="bright_white"),
        title="🎮 Available Adventures",
        border_style="bold bright_blue",
        expand=False
    ))
    console.line()

    # Load and display scenario details
    scenario_names = []
    panels = []
    
    for i, filename in enumerate(scenario_files):
        scenario_name = filename[:-5]  # Remove .json extension
        scenario_names.append(scenario_name)
        
        details = get_scenario_details(filename)
        panel = create_scenario_panel(scenario_name, details, i + 1)
        panels.append(panel)
    
    # Display panels in a grid layout
    for panel in panels:
        console.print(panel)
        console.line()
    
    return scenario_names

def get_user_selection(scenario_names: list[str]) -> str | None:
    """Gets the user's scenario selection with enhanced input handling."""
    if not scenario_names:
        return None
    
    # Create selection prompt
    console.print(Panel(
        Text("Enter the number of your chosen adventure, 'debug' to toggle debug mode, or 'quit' to exit", 
             justify="center", style="bright_white"),
        border_style="bright_blue"
    ))
    
    while True:
        try:
            choice_text = Text("Your choice: ", style="bold bright_blue")
            selection = console.input(choice_text).strip()
            
            # Handle quit
            if selection.lower() in ['quit', 'exit', 'q']:
                return None
            
            # Handle debug toggle
            if selection.lower() == 'debug':
                import aigame.aigame_core.config as config
                config.LLM_DEBUG_MODE = not config.LLM_DEBUG_MODE
                
                if config.LLM_DEBUG_MODE:
                    console.print(Panel(
                        Text("🐛 Debug Mode Enabled - LLM calls will be tracked", style="bright_yellow"),
                        border_style="yellow"
                    ))
                else:
                    console.print(Panel(
                        Text("🔇 Debug Mode Disabled - LLM calls will not be shown", style="bright_blue"),
                        border_style="blue"
                    ))
                console.line()
                continue  # Go back to selection prompt
            
            # Handle numeric selection
            choice_index = int(selection) - 1
            if 0 <= choice_index < len(scenario_names):
                selected_scenario = scenario_names[choice_index]
                
                # Confirmation with scenario name
                console.line()
                console.print(f"[bright_green]✓[/bright_green] You selected: [bold bright_yellow]{selected_scenario}[/bold bright_yellow]")
                return selected_scenario
            else:
                console.print(f"[yellow]Please enter a number between 1 and {len(scenario_names)}, 'debug' to toggle debug mode, or 'quit' to exit.[/yellow]")
                
        except ValueError:
            console.print("[yellow]Please enter a valid number, 'debug' to toggle debug mode, or 'quit' to exit.[/yellow]")
        except KeyboardInterrupt:
            console.print("\n[dim]Goodbye![/dim]")
            return None
        except Exception as e:
            console.print(f"[red]An error occurred: {e}[/red]")

def list_and_select_scenario() -> str | None:
    """Enhanced scenario selection with detailed information display."""
    scenario_names = display_scenarios_detailed()
    
    if not scenario_names:
        return None
    
    return get_user_selection(scenario_names)

if __name__ == '__main__':
    # Check for debug mode
    if check_debug_mode():
        enable_debug_mode()
    
    console.print(Panel(
        Text("Welcome to the AI Adventure Game!", justify="center", style="bold bright_magenta"),
        subtitle="Where every conversation shapes your destiny",
        border_style="bold bright_magenta"
    ))
    
    # Show debug status if enabled
    if LLM_DEBUG_MODE:
        console.print(Text("Debug mode is active - LLM invocations will be displayed", style="dim yellow"))
    
    console.line()
    
    selected_scenario_name = list_and_select_scenario()

    if selected_scenario_name:
        console.line()
        console.print(f"[dim white]Preparing your adventure: '{selected_scenario_name}'...[/dim white]")
        console.line()
        
        try:
            start_game(scenario_name_to_load=selected_scenario_name)
        except Exception as e:
            console.print_exception(show_locals=False)
            console.input("[bold red]An unexpected critical error occurred during gameplay. Press Enter to exit.[/bold red]")
    else:
        console.print("[dim white]No adventure selected. Perhaps another time...[/dim white]")

    console.line()
    console.print(Panel(
        Text("Thank you for playing the AI Adventure Game!", justify="center", style="bold bright_magenta"),
        subtitle="May your next adventure be even greater!",
        border_style="bold bright_magenta"
    ))
