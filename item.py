# item.py

import json # Make sure json is imported
from rich import print as rprint # For rich printing of errors

class Item:
    def __init__(self, name: str, description: str = ""):
        if not isinstance(name, str) or not name:
            raise ValueError("Item name must be a non-empty string.")
        if not isinstance(description, str):
            raise ValueError("Item description must be a string.")

        self.name: str = name
        self.description: str = description
        # Future attributes like value, weight, type, usable, effect etc. can be added here

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return f"Item(name='{self.name}', description='{self.description}')"

    def __eq__(self, other) -> bool:
        if isinstance(other, Item):
            return self.name == other.name
        elif isinstance(other, str):
            return self.name == other # Allows checking item by name string
        return False

    def __hash__(self) -> int:
        # Necessary for using Item objects in sets or as dict keys if needed
        return hash(self.name)

    @classmethod
    def from_dict(cls, data: dict) -> 'Item':
        if not isinstance(data, dict):
            raise ValueError("Item data must be a dictionary.")
        
        name = data.get("name")
        description = data.get("description", "") # Default to empty string if not provided

        if not name: # Name is mandatory
            raise ValueError("Item data must include 'name'.")
        
        return cls(name=name, description=description)

def load_item_from_file(item_name: str, base_directory_path: str) -> Item:
    """
    Loads a single item definition from a JSON file named after the item.

    Args:
        item_name (str): The name of the item (and the JSON file, e.g., "sword.json").
        base_directory_path (str): The base directory where item JSON files are stored.

    Returns:
        Item: An Item object.
        
    Raises:
        FileNotFoundError: If the JSON file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
        ValueError: If item data is malformed or missing required fields.
    """
    file_path = f"{base_directory_path.rstrip('/')}/{item_name}.json"
    
    try:
        with open(file_path, 'r') as f:
            item_data = json.load(f) # Expecting a single JSON object
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
        # Optional: Check if loaded item's name matches the filename (already handled by from_dict structure)
        if item.name != item_name:
             rprint(f"[bold yellow]Warning: Item name in file '{item.name}' does not match expected name '{item_name}' from filename '{file_path}'. Using name from file.[/bold yellow]")
        return item
    except ValueError as ve:
        rprint(f"[bold red]Error loading item '{item_name}' from '{file_path}': {ve}[/bold red]")
        raise ValueError(f"Failed to load item '{item_name}' from '{file_path}': {ve}") from ve 