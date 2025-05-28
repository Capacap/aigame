#!/usr/bin/env python3
"""
AI Game - Main Entry Point

Sets up and runs a conversation game with 3 random characters.
"""

import os
import random
from aigame.core.game import GameEngine

def main():
    print("🎮 AI Game - Character Conversation")
    print("=" * 40)
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  No OPENAI_API_KEY found. Set environment variable to run the game.")
        print("   Example: export OPENAI_API_KEY='your-key-here'")
        return
    
    try:
        # Initialize game engine
        print("🚀 Initializing game...")
        game = GameEngine()
        game.initialize_game()
        
        # Get all available characters
        all_characters = game.game_state.turn_order.copy()
        
        # Select 3 random characters
        if len(all_characters) >= 3:
            selected_characters = random.sample(all_characters, 3)
        else:
            selected_characters = all_characters
        
        # Update game state with selected characters
        game.game_state.turn_order = selected_characters
        game.game_state.scene_characters = selected_characters.copy()
        
        print(f"🎭 Selected characters: {', '.join(selected_characters)}")
        
        # Show character details
        print("\n📋 Character Details:")
        for char_name in selected_characters:
            char_data = game.get_character_data(char_name)
            if char_data is not None:
                print(f"  • {char_name}: {char_data['disposition']} disposition")
                print(f"    Goal: {char_data['goal']}")
        
        print(f"\n🔄 Starting conversation (5 turns)...")
        print("=" * 50)
        
        # Run the game
        game.run_game_loop(max_turns=5)
        
        # Show final conversation
        dialogue_events = game.get_dialogue_history()
        print(f"\n📜 FINAL CONVERSATION ({len(dialogue_events)} exchanges):")
        print("-" * 50)
        
        for i, (_, event) in enumerate(dialogue_events.iterrows(), 1):
            print(f"{i:2d}. {event['character']}: \"{event['content']}\"")
        
        print(f"\n✅ Game completed successfully!")
        print(f"💬 Total exchanges: {len(dialogue_events)}")
        
    except Exception as e:
        print(f"\n❌ Game failed: {e}")
        print("Check your API key and network connection.")

if __name__ == "__main__":
    main()