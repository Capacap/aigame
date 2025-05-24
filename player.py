from item import Item # Import the Item class
from character import Character # Import Character class

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
                print(f"Added '{item.name}' to {self.name}'s inventory.") # Use item.name
            else:
                print(f"'{item.name}' is already in {self.name}'s inventory.") # Use item.name
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
                print(f"Removed '{item_name_for_message}' from {self.name}'s inventory.")
                return True
            else:
                print(f"'{item_name_for_message}' not found in {self.name}'s inventory.")
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
        player1 = Player(character_data=Character(name="Hero", items=[]))
        print(player1)

        # Add items - now creating Item objects
        hp_potion = Item(name="health potion", description="Restores a bit of health.")
        game_map = Item(name="map", description="Shows the layout of the current area.")
        player1.add_item(hp_potion)
        player1.add_item(game_map)
        player1.add_item(hp_potion) # Try adding a duplicate
        print(player1)

        # Check for items
        print(f"\nPlayer has 'map': {player1.has_item('map')}") # Check by name string
        print(f"Player has 'sword': {player1.has_item('sword')}")
        print(f"Player has health potion object: {player1.has_item(hp_potion)}") # Check by Item object

        # Remove items
        player1.remove_item("health potion") # Remove by name string
        player1.remove_item(Item(name="sword")) # Try removing an item not present, by Item object
        print(player1)

        # Test invalid instantiation
        # invalid_player = Player("")

    except ValueError as ve:
        print(f"Configuration error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 