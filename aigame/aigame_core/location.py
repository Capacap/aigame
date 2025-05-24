from __future__ import annotations
import json
from rich import print as rprint

class Location:
    def __init__(self, name: str, description: str):
        if not isinstance(name, str) or not name:
            raise ValueError("Location name must be a non-empty string.")
        if not isinstance(description, str) or not description:
            raise ValueError("Location description must be a non-empty string.")

        self.name: str = name
        self.description: str = description

    def __str__(self) -> str:
        return f"{self.name}\n{self.description}"

    def __repr__(self) -> str:
        return f"Location(name='{self.name}', description='{self.description}')"

    @classmethod
    def from_dict(cls, data: dict) -> Location:
        if not isinstance(data, dict):
            raise ValueError("Location data must be a dictionary.")
        
        name = data.get("name")
        description = data.get("description")

        if not name or not description:
            raise ValueError("Location data must include 'name' and 'description'.")
        
        return cls(name=name, description=description)

def load_location_from_file(location_name: str, base_directory_path: str) -> Location:
    file_path = f"{base_directory_path.rstrip('/')}/{location_name}.json"
    
    try:
        with open(file_path, 'r') as f:
            location_data = json.load(f)
    except FileNotFoundError:
        rprint(f"[bold red]Error: Location file '{file_path}' not found for location '{location_name}'.[/bold red]")
        raise
    except json.JSONDecodeError as e:
        rprint(f"[bold red]Error: Could not decode JSON from '{file_path}' for location '{location_name}'. Details: {e}[/bold red]")
        raise

    if not isinstance(location_data, dict):
        raise ValueError(f"Location JSON file '{file_path}' should contain a single location object (a dictionary).")

    try:
        location = Location.from_dict(location_data)
        if location.name != location_name:
             rprint(f"[bold yellow]Warning: Location name in file '{location.name}' does not match expected name '{location_name}' from filename '{file_path}'. Using name from file.[/bold yellow]")
        return location
    except ValueError as ve:
        rprint(f"[bold red]Error loading location '{location_name}' from '{file_path}': {ve}[/bold red]")
        raise ValueError(f"Failed to load location '{location_name}' from '{file_path}': {ve}") from ve 