# item.py
from __future__ import annotations # Added for future type hinting if needed within Item itself
import json
from rich import print as rprint

class Item:
    def __init__(self, name: str, description: str = ""):
        if not isinstance(name, str) or not name:
            raise ValueError("Item name must be a non-empty string.")
        if not isinstance(description, str):
            raise ValueError("Item description must be a string.")

        self.name: str = name
        self.description: str = description

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Item(name='{self.name}', description='{self.description}')"

    def __eq__(self, other) -> bool:
        if isinstance(other, Item):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    @classmethod
    def from_dict(cls, data: dict) -> Item:
        if not isinstance(data, dict):
            raise ValueError("Item data must be a dictionary.")
        name = data.get("name")
        description = data.get("description", "")
        if not name:
            raise ValueError("Item data must include 'name'.")
        return cls(name=name, description=description)

def load_item_from_file(item_name: str, base_directory_path: str) -> Item:
    file_path = f"{base_directory_path.rstrip('/')}/{item_name}.json"
    try:
        with open(file_path, 'r') as f:
            item_data = json.load(f)
    except FileNotFoundError:
        rprint(f"[bold red]Error: Item file '{file_path}' not found for item '{item_name}'.[/bold red]")
        raise
    except json.JSONDecodeError as e:
        rprint(f"[bold red]Error: Could not decode JSON from '{file_path}' for item '{item_name}'. Details: {e}[/bold red]")
        raise
    if not isinstance(item_data, dict):
        raise ValueError(f"Item JSON file '{file_path}' should contain a single item object (a dictionary).")
    try:
        item = Item.from_dict(item_data)
        if item.name != item_name:
             rprint(f"[bold yellow]Warning: Item name in file '{item.name}' does not match expected name '{item_name}' from filename '{file_path}'. Using name from file.[/bold yellow]")
        return item
    except ValueError as ve:
        rprint(f"[bold red]Error loading item '{item_name}' from '{file_path}': {ve}[/bold red]")
        raise ValueError(f"Failed to load item '{item_name}' from '{file_path}': {ve}") from ve 