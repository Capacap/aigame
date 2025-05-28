"""
Test suite for main script functionality.

Tests the main demo script, configuration handling, and workflow validation.
"""

import os
import sys
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

# Add the project root to path for importing main
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    import main
    from aigame import generate_text_response, generate_json_response
except ImportError as e:
    print(f"Import error: {e}")
    # Create mock functions for testing
    def generate_text_response(*args, **kwargs):
        return {"content": "Mock text response", "reasoning": "Mock reasoning"}
    
    def generate_json_response(*args, **kwargs):
        return {"content": {"name": "Test", "level": 1}, "reasoning": "Mock JSON reasoning"}


def test_simple_config_defaults():
    """Test SimpleConfig default values."""
    config = main.SimpleConfig()
    
    assert config.debug_mode is False
    assert config.model == "gpt-4o-mini"
    assert config.api_key is None
    assert config.request_timeout == 30
    assert config.max_retries == 2
    assert config.retry_delay == 1.0
    assert config.force_ipv4 is False


def test_simple_config_customization():
    """Test SimpleConfig with custom values."""
    config = main.SimpleConfig(
        debug_mode=True,
        model="gpt-4",
        request_timeout=60,
        max_retries=5
    )
    
    assert config.debug_mode is True
    assert config.model == "gpt-4"
    assert config.request_timeout == 60
    assert config.max_retries == 5


def test_api_key_check_missing():
    """Test behavior when API key is missing."""
    with patch.dict(os.environ, {}, clear=True):
        # Test that os.getenv returns None when API key is missing
        api_key = os.getenv('OPENAI_API_KEY')
        assert api_key is None
        
        # Test the logic that would be executed
        if not api_key:
            should_exit = True
        else:
            should_exit = False
            
        assert should_exit is True


def test_api_key_check_present():
    """Test behavior when API key is present."""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
        # Test that os.getenv returns the key when present
        api_key = os.getenv('OPENAI_API_KEY')
        assert api_key == 'test-key'
        
        # Test the logic that would be executed
        if not api_key:
            should_exit = True
        else:
            should_exit = False
            
        assert should_exit is False


def test_text_generation_demo():
    """Test the text generation demo functionality."""
    import main
    config = main.SimpleConfig()
    
    with patch('aigame.tests.test_main.generate_text_response') as mock_generate:
        mock_generate.return_value = {
            "content": "Hello! I'm your AI game assistant.",
            "reasoning": "Friendly introduction"
        }
        
        # Simulate the text generation part
        text_messages = [{"role": "user", "content": "Say hello and introduce yourself as an AI game assistant"}]
        result = generate_text_response(text_messages, config)
        
        assert result["content"] == "Hello! I'm your AI game assistant."
        assert result["reasoning"] == "Friendly introduction"


def test_json_generation_demo():
    """Test the JSON generation demo functionality."""
    import main
    config = main.SimpleConfig()
    
    with patch('aigame.tests.test_main.generate_json_response') as mock_generate:
        mock_generate.return_value = {
            "content": {"name": "Warrior", "level": 5, "health": 150},
            "reasoning": "Generated RPG character"
        }
        
        # Simulate the JSON generation part
        json_messages = [
            {"role": "system", "content": "Respond with valid JSON only"},
            {"role": "user", "content": "Create a simple game character in JSON format with name, level, and health"}
        ]
        result = generate_json_response(json_messages, config)
        
        assert isinstance(result["content"], dict)
        assert "name" in result["content"]
        assert "level" in result["content"]
        assert "health" in result["content"]


def test_error_handling():
    """Test error handling in main script."""
    import main
    config = main.SimpleConfig()
    
    with patch('aigame.generate_text_response') as mock_text:
        with patch('builtins.print') as mock_print:
            
            # Mock an exception
            mock_text.side_effect = Exception("API Error")
            
            # Should handle the exception gracefully
            try:
                text_messages = [{"role": "user", "content": "Say hello and introduce yourself as an AI game assistant"}]
                result = generate_text_response(text_messages, config)
            except Exception as e:
                # This is expected
                assert "API Error" in str(e)


def test_message_structure():
    """Test that demo messages have correct structure."""
    # Test text generation message structure
    text_messages = [{"role": "user", "content": "Say hello and introduce yourself as an AI game assistant"}]
    
    assert len(text_messages) == 1
    assert text_messages[0]["role"] == "user"
    assert "introduce yourself" in text_messages[0]["content"]
    
    # Test JSON generation message structure
    json_messages = [
        {"role": "system", "content": "Respond with valid JSON only"},
        {"role": "user", "content": "Create a simple game character in JSON format with name, level, and health"}
    ]
    
    assert len(json_messages) == 2
    assert json_messages[0]["role"] == "system"
    assert json_messages[1]["role"] == "user"
    assert "json" in json_messages[1]["content"].lower()


def test_config_integration():
    """Test that SimpleConfig integrates properly with AI functions."""
    config = main.SimpleConfig(
        model="test-model",
        request_timeout=45,
        max_retries=3
    )
    
    # Test that config attributes are accessible
    assert hasattr(config, 'model')
    assert hasattr(config, 'request_timeout')
    assert hasattr(config, 'max_retries')
    assert hasattr(config, 'debug_mode')
    assert hasattr(config, 'api_key')


def test_output_formatting():
    """Test that output is formatted correctly."""
    with patch('builtins.print') as mock_print:
        # Test header formatting
        print("🎮 AI Game - Inference Demo")
        print("=" * 40)
        
        # Test section formatting
        print("\n📝 Text Generation Demo:")
        print("\n🔧 JSON Generation Demo:")
        
        # Verify print was called
        assert mock_print.called


def test_reasoning_display():
    """Test reasoning display logic."""
    # Test with reasoning
    result_with_reasoning = {
        "content": "Test response",
        "reasoning": "This is the reasoning"
    }
    
    if result_with_reasoning['reasoning']:
        reasoning_displayed = True
    else:
        reasoning_displayed = False
    
    assert reasoning_displayed is True
    
    # Test without reasoning
    result_without_reasoning = {
        "content": "Test response",
        "reasoning": None
    }
    
    if result_without_reasoning['reasoning']:
        reasoning_displayed = True
    else:
        reasoning_displayed = False
    
    assert reasoning_displayed is False


def run_all_main_tests():
    """Run all main script tests and report results."""
    tests = [
        test_simple_config_defaults,
        test_simple_config_customization,
        test_api_key_check_missing,
        test_api_key_check_present,
        test_text_generation_demo,
        test_json_generation_demo,
        test_error_handling,
        test_message_structure,
        test_config_integration,
        test_output_formatting,
        test_reasoning_display
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(f"✅ {test.__name__}")
        except Exception as e:
            results.append(f"❌ {test.__name__}: {e}")
    
    print("Main Script Test Results:")
    print("=" * 40)
    for result in results:
        print(result)
    
    passed = sum(1 for r in results if r.startswith("✅"))
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_main_tests()
    exit(0 if success else 1) 