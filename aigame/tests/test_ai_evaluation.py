#!/usr/bin/env python3
"""
Simple AI Evaluation Test Script

Tests conversation quality using a larger AI model for evaluation.
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aigame.core.game import GameEngine
import json


def evaluate_conversation_with_ai(dialogue_events, character_data, evaluation_model="openai/gpt-4o"):
    """
    Simple AI evaluation of conversation quality
    
    Args:
        dialogue_events: DataFrame with dialogue
        character_data: Dict of character information
        evaluation_model: Model to use for evaluation
        
    Returns:
        Dict with 'scores' (dict of numeric scores) and 'explanation' (string)
    """
    try:
        from aigame.core.ai_inference import generate_json_response
        from aigame.core.config import config
    except ImportError:
        return {"error": "AI inference not available"}
    
    if dialogue_events.empty:
        return {"error": "No dialogue to evaluate"}
    
    # Format conversation transcript
    transcript = []
    for i, (_, event) in enumerate(dialogue_events.iterrows(), 1):
        transcript.append(f"{i}. {event['character']}: \"{event['content']}\"")
    
    # Format character context
    char_context = "CHARACTER PROFILES:\n"
    for char_name in character_data:
        char_info = character_data[char_name]
        char_context += f"\n{char_name}: {char_info.get('disposition', 'unknown')} disposition, goal: {char_info.get('goal', 'unknown')}"
    
    # Create evaluation prompt
    prompt = (
        "Please evaluate this character conversation and respond with valid JSON only.\n"
        "\n"
        f"{char_context}\n"
        "\n"
        "CONVERSATION:\n"
        f"{chr(10).join(transcript)}\n"
        "\n"
        "Rate the conversation in these areas (1-10 scale) and provide your response as JSON:\n"
        "\n"
        "{\n"
        '    "scores": {\n'
        '        "character_consistency": <1-10 integer>,\n'
        '        "dialogue_quality": <1-10 integer>,\n'
        '        "narrative_flow": <1-10 integer>,\n'
        '        "character_interaction": <1-10 integer>,\n'
        '        "overall_score": <1-10 integer>\n'
        '    },\n'
        '    "explanation": "Brief explanation of your assessment, highlighting strengths and areas for improvement"\n'
        "}\n"
        "\n"
        "Evaluation criteria:\n"
        "- Character Consistency: Do characters maintain their unique voices and personalities?\n"
        "- Dialogue Quality: Is the dialogue natural, engaging, and well-written?\n"
        "- Narrative Flow: Does the conversation progress logically and maintain coherence?\n"
        "- Character Interaction: Do characters respond appropriately to each other?\n"
        "- Overall Score: General assessment of conversation quality\n"
        "\n"
        "Respond with valid JSON only."
    )

    try:
        messages = [
            {"role": "system", "content": "You are an expert dialogue analyst. Provide objective, constructive evaluation of character conversations. Respond with valid JSON only."},
            {"role": "user", "content": prompt}
        ]
        
        # Create a temporary config with the evaluation model
        class EvalConfig:
            def __init__(self, base_config, model):
                self.debug_mode = base_config.debug_mode
                self.model = model
                self.api_key = base_config.api_key
                self.api_base = base_config.api_base
                self.api_version = base_config.api_version
                self.request_timeout = base_config.request_timeout
                self.force_ipv4 = base_config.force_ipv4
                self.max_retries = base_config.max_retries
                self.retry_delay = base_config.retry_delay
        
        eval_config = EvalConfig(config, evaluation_model)
        
        response = generate_json_response(
            messages, 
            eval_config,
            temperature=0.3,
            max_tokens=500
        )
        
        # Extract the JSON content
        evaluation_data = response["content"]
        
        # Validate the structure
        if not isinstance(evaluation_data, dict) or "scores" not in evaluation_data:
            return {"error": "Invalid evaluation response format"}
        
        # Add metadata
        evaluation_data["model"] = evaluation_model
        evaluation_data["dialogue_count"] = len(dialogue_events)
        
        return evaluation_data
        
    except Exception as e:
        return {"error": f"Evaluation failed: {str(e)}"}


def check_evaluation_success(evaluation_data, threshold=7):
    """
    Check if evaluation scores meet the success threshold
    
    Args:
        evaluation_data: Dict from evaluate_conversation_with_ai()
        threshold: Minimum score required (default: 7)
        
    Returns:
        tuple: (success: bool, failing_categories: list)
    """
    if "error" in evaluation_data or "scores" not in evaluation_data:
        return False, ["evaluation_error"]
    
    scores = evaluation_data["scores"]
    score_categories = [
        ('character_consistency', 'Character Consistency'),
        ('dialogue_quality', 'Dialogue Quality'),
        ('narrative_flow', 'Narrative Flow'),
        ('character_interaction', 'Character Interaction'),
        ('overall_score', 'Overall Score')
    ]
    
    failing_categories = []
    for key, name in score_categories:
        score = scores.get(key, 0)
        if isinstance(score, (int, float)) and score <= threshold:
            failing_categories.append(f"{name} ({score}/10)")
    
    success = len(failing_categories) == 0
    
    return success, failing_categories


def get_evaluation_scores(dialogue_events, character_data, evaluation_model="openai/gpt-4o"):
    """
    Get evaluation scores as a dictionary for programmatic processing
    
    Args:
        dialogue_events: DataFrame with dialogue
        character_data: Dict of character information  
        evaluation_model: Model to use for evaluation
        
    Returns:
        Dict with scores or None if evaluation failed
        
    Example:
        scores = get_evaluation_scores(dialogue, chars)
        if scores:
            overall = scores['scores']['overall_score']
            consistency = scores['scores']['character_consistency']
    """
    evaluation = evaluate_conversation_with_ai(dialogue_events, character_data, evaluation_model)
    
    if "error" in evaluation:
        print(f"Evaluation error: {evaluation['error']}")
        return None
        
    return evaluation


def run_ai_evaluation_test(num_characters=3, num_turns=5, evaluation_model="openai/gpt-4o"):
    """
    Run a conversation and evaluate it with AI
    
    Args:
        num_characters: Number of characters (max 5)
        num_turns: Number of conversation turns
        evaluation_model: AI model for evaluation
        
    Returns:
        bool: True if all scores > 7, False otherwise
    """
    print(f"🤖 AI Evaluation Test: {num_characters} characters, {num_turns} turns")
    print(f"📊 Evaluation model: {evaluation_model}")
    print("=" * 60)
    
    # Initialize game
    game = GameEngine()
    game.initialize_game()
    
    # Limit characters if requested
    if num_characters < len(game.game_state.turn_order):
        game.game_state.turn_order = game.game_state.turn_order[:num_characters]
        game.game_state.scene_characters = game.game_state.turn_order.copy()
    
    print(f"🎭 Characters: {', '.join(game.game_state.turn_order)}")
    print(f"🔄 Running {num_turns} turns...")
    
    # Run conversation
    game.run_game_loop(max_turns=num_turns)
    
    # Get dialogue and character data
    dialogue_events = game.get_dialogue_history()
    character_data = {}
    for char_name in game.game_state.turn_order:
        char_data = game.get_character_data(char_name)
        if char_data is not None:
            character_data[char_name] = {
                'disposition': char_data['disposition'],
                'goal': char_data['goal'],
                'personality': char_data['personality']
            }
    
    # Show conversation
    print(f"\n📜 CONVERSATION ({len(dialogue_events)} exchanges):")
    print("-" * 50)
    for i, (_, event) in enumerate(dialogue_events.iterrows(), 1):
        print(f"{i:2d}. {event['character']}: \"{event['content']}\"")
    
    # AI Evaluation
    print(f"\n🤖 AI EVALUATION:")
    print("-" * 50)
    
    evaluation = evaluate_conversation_with_ai(dialogue_events, character_data, evaluation_model)
    
    if "error" in evaluation:
        print(f"❌ {evaluation['error']}")
        return False
    
    # Display scores in a structured format
    scores = evaluation.get("scores", {})
    print("📊 SCORES:")
    print(f"   Character Consistency: {scores.get('character_consistency', 'N/A')}/10")
    print(f"   Dialogue Quality: {scores.get('dialogue_quality', 'N/A')}/10")
    print(f"   Narrative Flow: {scores.get('narrative_flow', 'N/A')}/10")
    print(f"   Character Interaction: {scores.get('character_interaction', 'N/A')}/10")
    print(f"   Overall Score: {scores.get('overall_score', 'N/A')}/10")
    
    print(f"\n💭 EXPLANATION:")
    print(f"   {evaluation.get('explanation', 'No explanation provided')}")
    
    print(f"\n📋 Evaluated by: {evaluation.get('model', 'Unknown')}")
    print(f"📈 Dialogue count: {evaluation.get('dialogue_count', 'Unknown')}")
    
    # Check if test passed (all scores > 7)
    success, failing_categories = check_evaluation_success(evaluation)
    
    if success:
        print(f"\n✅ TEST PASSED: All scores > 7")
    else:
        print(f"\n❌ TEST FAILED: Some scores ≤ 7")
        if failing_categories != ["evaluation_error"]:
            print(f"   Failing categories: {', '.join(failing_categories)}")
    
    return success


def run_batch_test():
    """Run multiple tests with different configurations"""
    print("🔬 BATCH AI EVALUATION TEST")
    print("=" * 50)
    
    configs = [
        {"characters": 2, "turns": 4, "name": "Quick 2-char"},
        {"characters": 3, "turns": 6, "name": "Medium 3-char"},
        {"characters": 4, "turns": 8, "name": "Full 4-char"},
    ]
    
    passed_tests = 0
    total_tests = len(configs)
    
    for i, config in enumerate(configs, 1):
        print(f"\n🧪 Test {i}/{total_tests}: {config['name']}")
        print("-" * 30)
        
        success = run_ai_evaluation_test(
            num_characters=config["characters"],
            num_turns=config["turns"]
        )
        
        if success:
            passed_tests += 1
            print(f"✅ Test {i} PASSED")
        else:
            print(f"❌ Test {i} FAILED")
    
    # Final summary
    print(f"\n📊 BATCH TEST SUMMARY:")
    print("=" * 30)
    print(f"Tests passed: {passed_tests}/{total_tests}")
    print(f"Success rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
    elif passed_tests > 0:
        print("⚠️  SOME TESTS FAILED")
    else:
        print("💥 ALL TESTS FAILED")
    
    return passed_tests == total_tests


def main():
    """Main test runner"""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "batch":
            run_batch_test()
        elif test_type == "custom":
            chars = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            turns = int(sys.argv[3]) if len(sys.argv) > 3 else 5
            model = sys.argv[4] if len(sys.argv) > 4 else "openai/gpt-4o"
            run_ai_evaluation_test(chars, turns, model)
        else:
            print("Usage: python test_ai_evaluation.py [batch|custom] [characters] [turns] [model]")
    else:
        # Default test
        run_ai_evaluation_test()


if __name__ == "__main__":
    main() 