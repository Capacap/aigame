from __future__ import annotations
import json
from rich import print as rprint

class Scenario:
    def __init__(self, name: str, description: str, 
                 location_name: str, player_character_name: str, 
                 npc_character_name: str, victory_condition: str, 
                 npc_speaks_first: bool = False, setting: str = None):
        
        if not isinstance(name, str) or not name:
            raise ValueError("Scenario name must be a non-empty string.")
        if not isinstance(description, str) or not description:
            raise ValueError("Scenario description must be a non-empty string.")
        if not isinstance(location_name, str) or not location_name:
            raise ValueError("Location name must be a non-empty string.")
        if not isinstance(player_character_name, str) or not player_character_name:
            raise ValueError("Player character name must be a non-empty string.")
        if not isinstance(npc_character_name, str) or not npc_character_name:
            raise ValueError("NPC character name must be a non-empty string.")
        if not isinstance(victory_condition, str) or not victory_condition:
            raise ValueError("Victory condition must be a non-empty string.")
        if not isinstance(npc_speaks_first, bool):
            raise ValueError("NPC speaks first must be a boolean value.")
        if setting is not None and not isinstance(setting, str):
            raise ValueError("Setting must be a string or None.")

        self.name: str = name
        self.description: str = description
        self.location_name: str = location_name
        self.player_character_name: str = player_character_name
        self.npc_character_name: str = npc_character_name
        self.victory_condition: str = victory_condition
        self.npc_speaks_first: bool = npc_speaks_first
        self.setting: str = setting

    def __str__(self) -> str:
        return f"Scenario: {self.name}\nDescription: {self.description}"

    def __repr__(self) -> str:
        return (f"Scenario(name='{self.name}', description='{self.description}', "
                f"location_name='{self.location_name}', player_character_name='{self.player_character_name}', "
                f"npc_character_name='{self.npc_character_name}', victory_condition='{self.victory_condition}', "
                f"npc_speaks_first={self.npc_speaks_first}, setting='{self.setting}')")

    @classmethod
    def from_dict(cls, data: dict) -> Scenario:
        if not isinstance(data, dict):
            raise ValueError("Scenario data must be a dictionary.")
        
        name = data.get("name")
        description = data.get("description")
        location_name = data.get("location_name")
        player_character_name = data.get("player_character_name")
        npc_character_name = data.get("npc_character_name")
        victory_condition = data.get("victory_condition")
        npc_speaks_first = data.get("npc_speaks_first", False)
        setting = data.get("setting")  # Optional field

        if not all([name, description, location_name, player_character_name, npc_character_name, victory_condition]):
            raise ValueError("Scenario data must include 'name', 'description', 'location_name', 'player_character_name', 'npc_character_name', and 'victory_condition'.")
        
        return cls(
            name=name, 
            description=description, 
            location_name=location_name,
            player_character_name=player_character_name,
            npc_character_name=npc_character_name,
            victory_condition=victory_condition,
            npc_speaks_first=npc_speaks_first,
            setting=setting
        )

def load_scenario_from_file(scenario_name: str, base_directory_path: str) -> Scenario:
    file_path = f"{base_directory_path.rstrip('/')}/{scenario_name}.json"
    
    try:
        with open(file_path, 'r') as f:
            scenario_data = json.load(f)
    except FileNotFoundError:
        rprint(f"[bold red]Error: Scenario file '{file_path}' not found for scenario '{scenario_name}'.[/bold red]")
        raise
    except json.JSONDecodeError as e:
        rprint(f"[bold red]Error: Could not decode JSON from '{file_path}' for scenario '{scenario_name}'. Details: {e}[/bold red]")
        raise

    if not isinstance(scenario_data, dict):
        raise ValueError(f"Scenario JSON file '{file_path}' should contain a single scenario object (a dictionary).")

    try:
        scenario = Scenario.from_dict(scenario_data)
        return scenario
    except ValueError as ve:
        rprint(f"[bold red]Error loading scenario '{scenario_name}' from '{file_path}': {ve}[/bold red]")
        raise ValueError(f"Failed to load scenario '{scenario_name}' from '{file_path}': {ve}") from ve 