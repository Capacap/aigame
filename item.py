# item.py

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