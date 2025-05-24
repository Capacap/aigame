class Player:
    """
    Represents the player in the game.
    """

    def __init__(self, name: str):
        # Validate arguments
        if not isinstance(name, str) or not name:
            raise ValueError("Player name must be a non-empty string.")

        # Assign attributes
        self.name: str = name
        self.items: list[str] = []

    def __str__(self) -> str:
        """
        Returns a string representation of the player.
        """
        items_str = ", ".join(self.items) if self.items else "nothing"
        return f"Player: {self.name}\nItems: {items_str}"

    def add_item(self, item: str) -> None:
        """
        Adds an item to the player's inventory.
        """
        if not isinstance(item, str) or not item:
            raise ValueError("Item to add must be a non-empty string.")
        try:
            if item not in self.items:
                self.items.append(item)
                print(f"Added '{item}' to {self.name}'s inventory.")
            else:
                print(f"'{item}' is already in {self.name}'s inventory.")
        except Exception as e:
            print(f"Error adding item for {self.name}: {e}")

    def remove_item(self, item: str) -> bool:
        """
        Removes an item from the player's inventory.
        Returns True if the item was removed, False otherwise.
        """
        if not isinstance(item, str) or not item:
            raise ValueError("Item to remove must be a non-empty string.")
        try:
            if item in self.items:
                self.items.remove(item)
                print(f"Removed '{item}' from {self.name}'s inventory.")
                return True
            else:
                print(f"'{item}' not found in {self.name}'s inventory.")
                return False
        except Exception as e:
            print(f"Error removing item for {self.name}: {e}")
            return False

    def has_item(self, item: str) -> bool:
        """
        Checks if the player has a specific item.
        """
        if not isinstance(item, str) or not item:
            raise ValueError("Item to check must be a non-empty string.")
        try:
            return item in self.items
        except Exception as e:
            print(f"Error checking item for {self.name}: {e}")
            return False

if __name__ == '__main__':
    try:
        # Player creation
        player1 = Player(name="Hero")
        print(player1)

        # Add items
        player1.add_item("health potion")
        player1.add_item("map")
        player1.add_item("health potion") # Try adding a duplicate
        print(player1)

        # Check for items
        print(f"\nPlayer has 'map': {player1.has_item('map')}")
        print(f"Player has 'sword': {player1.has_item('sword')}")

        # Remove items
        player1.remove_item("health potion")
        player1.remove_item("sword") # Try removing an item not present
        print(player1)

        # Test invalid instantiation
        # invalid_player = Player("")

    except ValueError as ve:
        print(f"Configuration error: {ve}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}") 