#!/usr/bin/env python3
"""
Test module for game conversation functionality.

This module contains unit tests and integration tests for the conversation
system in the AI game engine.
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aigame.core.game import GameEngine, EventCategory, DialogueEventType


class TestGameConversation(unittest.TestCase):
    """Test cases for game conversation functionality"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.game = GameEngine()
        self.game.initialize_game()
    
    def test_game_initialization(self):
        """Test that the game initializes correctly"""
        self.assertIsNotNone(self.game.game_state.characters_df)
        self.assertGreater(len(self.game.game_state.characters_df), 0)
        self.assertGreater(len(self.game.game_state.turn_order), 0)
    
    def test_character_loading(self):
        """Test that characters are loaded with required attributes"""
        for _, char in self.game.game_state.characters_df.iterrows():
            self.assertIn('name', char)
            self.assertIn('personality', char)
            self.assertIn('disposition', char)
            self.assertIn('goal', char)
    
    def test_single_turn_execution(self):
        """Test that a single turn executes without errors"""
        initial_events = len(self.game.game_state.events_df)
        turn_result = self.game.execute_turn()
        
        self.assertIn('character', turn_result)
        self.assertIn('new_action', turn_result)
        self.assertGreater(len(self.game.game_state.events_df), initial_events)
    
    def test_dialogue_generation(self):
        """Test that dialogue is generated for characters"""
        character_name = self.game.game_state.turn_order[0]
        action = self.game.take_character_action(character_name)
        
        self.assertEqual(action['type'], 'dialogue')
        self.assertEqual(action['character'], character_name)
        self.assertIsInstance(action['content'], str)
        self.assertGreater(len(action['content']), 0)
    
    def test_event_tracking(self):
        """Test that events are properly tracked"""
        initial_events = len(self.game.game_state.events_df)
        self.game.execute_turn()
        
        # Should have at least turn start, dialogue, action taken, and turn end events
        self.assertGreaterEqual(len(self.game.game_state.events_df), initial_events + 4)
    
    def test_dialogue_history_retrieval(self):
        """Test that dialogue history can be retrieved"""
        # Run a few turns to generate dialogue
        for _ in range(3):
            self.game.execute_turn()
        
        dialogue_history = self.game.get_dialogue_history()
        self.assertGreaterEqual(len(dialogue_history), 3)
        
        # Check that all entries are dialogue events
        for _, event in dialogue_history.iterrows():
            self.assertEqual(event['category'], EventCategory.DIALOGUE.value)
            self.assertEqual(event['event_type'], DialogueEventType.DIALOGUE_SPEAK.value)
    
    def test_conversation_analysis(self):
        """Test that conversation analysis works"""
        # Run several turns
        for _ in range(5):
            self.game.execute_turn()
        
        analysis = self.game.analyze_conversation()
        
        self.assertIn('total_exchanges', analysis)
        self.assertIn('characters', analysis)
        self.assertIn('conversation_flow', analysis)
        self.assertGreater(analysis['total_exchanges'], 0)
    
    def test_decision_queuing(self):
        """Test that decisions can be queued and processed"""
        character_name = self.game.game_state.turn_order[0]
        test_decision = {'type': 'test_decision', 'data': 'test'}
        
        self.game.queue_decision(character_name, test_decision)
        decisions = self.game.process_queued_decisions(character_name)
        
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]['type'], 'test_decision')


class TestGameConversationIntegration(unittest.TestCase):
    """Integration tests for full conversation flows"""
    
    def test_full_conversation_flow(self):
        """Test a complete conversation flow"""
        game = GameEngine()
        game.initialize_game()
        
        # Run a full conversation
        game.run_game_loop(max_turns=8)
        
        # Verify we have dialogue from multiple characters
        dialogue_history = game.get_dialogue_history()
        characters_who_spoke = set(dialogue_history['character'].unique())
        
        self.assertGreaterEqual(len(characters_who_spoke), 3)
        self.assertGreaterEqual(len(dialogue_history), 8)
    
    def test_character_consistency(self):
        """Test that characters maintain consistency in their dialogue"""
        game = GameEngine()
        game.initialize_game()
        
        # Run conversation
        game.run_game_loop(max_turns=10)
        
        # Check that each character's dialogue reflects their disposition
        dialogue_history = game.get_dialogue_history()
        
        for character_name in game.game_state.turn_order:
            char_data = game.get_character_data(character_name)
            char_dialogue = dialogue_history[dialogue_history['character'] == character_name]
            
            # Each character should have spoken at least once
            self.assertGreater(len(char_dialogue), 0)
            
            # Dialogue should be non-empty strings
            for _, event in char_dialogue.iterrows():
                self.assertIsInstance(event['content'], str)
                self.assertGreater(len(event['content'].strip()), 0)


def run_conversation_tests():
    """Run all conversation tests"""
    print("🧪 Running AI Game Conversation Tests")
    print("=" * 40)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestGameConversation))
    suite.addTests(loader.loadTestsFromTestCase(TestGameConversationIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 40)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    run_conversation_tests() 