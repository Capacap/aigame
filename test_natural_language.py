#!/usr/bin/env python3

"""
Test script for the AI-powered natural language game system.
This demonstrates both player input parsing and NPC action parsing through natural dialogue.
"""

import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'aigame'))

from aigame.aigame_core.game_loop import start_game

def main():
    print("Testing AI-powered natural language game system...")
    print("Starting Echo Chamber Quest scenario...")
    print("\nFeatures demonstrated:")
    print("- Natural language player input (no slash commands needed)")
    print("- AI-powered NPC action parsing through dialogue")
    print("- NPCs can give items, accept offers, make trades naturally")
    print("- Dynamic disposition and story direction changes")
    print("\nTry natural interactions like:")
    print("- 'Hello there, how are you?'")
    print("- 'Here, take my translation cypher'") 
    print("- 'I want to trade my cypher for your key'")
    print("- 'help' or 'quit'")
    print()
    
    try:
        start_game("Echo Chamber Quest")
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    main() 