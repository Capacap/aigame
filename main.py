import os
from aigame.aigame_core.game_loop import start_game
from rich.console import Console
from rich.text import Text

console = Console()

SCENARIOS_DIR_PATH = "aigame/data/scenarios/" # Path to the scenarios directory

def list_and_select_scenario() -> str | None:
    """Lists available scenarios and prompts the user to select one."""
    try:
        all_files = os.listdir(SCENARIOS_DIR_PATH)
        scenario_files = sorted([f for f in all_files if f.endswith(".json")])
    except FileNotFoundError:
        console.print(f"[bold red]Error: Scenarios directory not found at '{SCENARIOS_DIR_PATH}'.[/bold red]")
        return None
    except Exception as e:
        console.print(f"[bold red]Error accessing scenarios directory: {e}[/bold red]")
        return None

    if not scenario_files:
        console.print(f"[bold yellow]No scenarios found in '{SCENARIOS_DIR_PATH}'.[/bold yellow]")
        return None

    console.print("[bold cyan]Available Scenarios:[/bold cyan]")
    scenario_names = []
    for i, filename in enumerate(scenario_files):
        scenario_name = filename[:-5] # Remove .json extension
        scenario_names.append(scenario_name)
        console.print(f"  {i + 1}. {scenario_name}")
    
    console.line()

    while True:
        try:
            choice_text = Text("Enter the number of the scenario you want to play: ", style="bold bright_blue")
            selection = console.input(choice_text)
            choice_index = int(selection) - 1
            if 0 <= choice_index < len(scenario_names):
                selected_scenario = scenario_names[choice_index]
                return selected_scenario
            else:
                console.print("[yellow]Invalid selection. Please enter a number from the list.[/yellow]")
        except ValueError:
            console.print("[yellow]Invalid input. Please enter a number.[/yellow]")
        except Exception as e:
            console.print(f"[red]An error occurred with your selection: {e}[/red]")
            # Potentially offer to exit or retry after a more generic error

if __name__ == '__main__':
    selected_scenario_name = list_and_select_scenario()

    if selected_scenario_name:
        console.print(f"[dim white]Attempting to start scenario: '{selected_scenario_name}'...[/dim white]")
        try:
            start_game(scenario_name_to_load=selected_scenario_name)
        except Exception as e:
            console.print_exception(show_locals=False)
            console.input("[bold red]An unexpected critical error occurred during gameplay. Press Enter to exit.[/bold red]")
    else:
        console.print("[dim white]No scenario selected. Exiting game.[/dim white]")

    console.line()
    console.print("[bold bright_magenta]Thank you for playing![/bold bright_magenta]")
