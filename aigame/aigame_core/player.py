from __future__ import annotations
from .item import Item # Corrected import
from .character import Character # Corrected import
from rich.text import Text # Corrected
from rich import print as rprint # Corrected

class Player:
    """
    Represents the player in the game.
    """

    def __init__(self, character_data: Character):
        # Validate arguments
        if not isinstance(character_data, Character):
            raise ValueError("Player must be initialized with a Character object.")

        # Assign attributes from Character object
        self.name: str = character_data.name
        # Initialize player's items as a copy of the character's items
        # This ensures the Player has its own list to modify independently
        self.items: list[Item] = list(character_data.items) 

    def __str__(self) -> str:
        """
        Returns a string representation of the player.
        """
        items_str = ", ".join(item.name for item in self.items) if self.items else "nothing" # Use item.name
        return f"Player: {self.name}\nItems: {items_str}"

    def add_item(self, item: Item) -> None: # Changed parameter to Item
        """
        Adds an item to the player's inventory.
        """
        if not isinstance(item, Item): # Validate Item object
            raise ValueError("Item to add must be an Item object.")
        try:
            if item not in self.items: # Comparison works due to Item.__eq__
                self.items.append(item)
                rprint(Text.assemble(Text("EVENT: ", style="dim white"), Text(f"'{item.name}' added to {self.name}'s inventory.", style="white")))
            else:
                rprint(Text.assemble(Text("INFO: ", style="dim yellow"), Text(f"'{item.name}' is already in {self.name}'s inventory.", style="yellow")))
        except Exception as e:
            print(f"Error adding item for {self.name}: {e}")

    def remove_item(self, item_identifier: str | Item) -> bool: # Parameter can be str or Item
        """
        Removes an item from the player's inventory.
        Returns True if the item was removed, False otherwise.
        """
        if not isinstance(item_identifier, (str, Item)) or not item_identifier:
            raise ValueError("Item identifier must be a non-empty string or an Item object.")
        
        item_name_for_message = item_identifier.name if isinstance(item_identifier, Item) else item_identifier

        try:
            if item_identifier in self.items: # Comparison works due to Item.__eq__
                self.items.remove(item_identifier) # remove() will find the matching item
                rprint(Text.assemble(Text("EVENT: ", style="dim white"), Text(f"'{item_name_for_message}' removed from {self.name}'s inventory.", style="white")))
                return True
            else:
                rprint(Text.assemble(Text("INFO: ", style="dim red"), Text(f"'{item_name_for_message}' not found in {self.name}'s inventory.", style="red")))
                return False
        except Exception as e:
            print(f"Error removing item for {self.name}: {e}")
            return False

    def has_item(self, item_identifier: str | Item) -> bool: # Parameter can be str or Item
        """
        Checks if the player has a specific item.
        """
        if not isinstance(item_identifier, (str, Item)) or not item_identifier:
            raise ValueError("Item identifier must be a non-empty string or an Item object.")
        try:
            return item_identifier in self.items # Comparison works due to Item.__eq__
        except Exception as e:
            print(f"Error checking item for {self.name}: {e}")
            return False

if __name__ == '__main__':
    try:
        # Player creation
        # This test code will need adjustment if Character/Item are also moved before Player is tested stand-alone
        # For now, assuming Character and Item are accessible for this test.
        # A more robust test would mock these or use simple versions if run standalone.
        # from .character import Character # Would be needed if running standalone
        # from .item import Item # Would be needed if running standalone
        
        # Minimal Character mock for testing Player constructor if Character is not fully available/moved yet
        class MockCharacter:
            def __init__(self, name, items):
                self.name = name
                self.items = items

        class MockItem:
            def __init__(self, name, description=""):
                self.name = name
                self.description = description
            def __eq__(self, other):
                if isinstance(other, MockItem): return self.name == other.name
                if isinstance(other, str): return self.name == other
                return False
            def __hash__(self):
                return hash(self.name)

        player1 = Player(character_data=MockCharacter(name="Hero", items=[]))
        print(player1)

        hp_potion = MockItem(name="health potion", description="Restores a bit of health.")
        game_map = MockItem(name="map", description="Shows the layout of the current area.")
        player1.add_item(hp_potion)
        player1.add_item(game_map)
        player1.add_item(hp_potion) 
        print(player1)

        print(f"\nPlayer has 'map': {player1.has_item('map')}")
        print(f"Player has 'sword': {player1.has_item('sword')}")
        print(f"Player has health potion object: {player1.has_item(hp_potion)}")

        player1.remove_item("health potion") 
        player1.remove_item(MockItem(name="sword")) 
        print(player1)

    except ValueError as ve:
        print(f"Configuration error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 