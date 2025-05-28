"""
Test suite for configuration module.

Tests configuration loading, validation, and default values.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

try:
    import aigame.core.config as config_module
except ImportError:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import core.config as config_module


def test_config_defaults():
    """Test that config module has sensible default values."""
    # Test basic defaults
    assert hasattr(config_module, 'debug_mode')
    assert hasattr(config_module, 'model')
    assert hasattr(config_module, 'api_key')
    assert hasattr(config_module, 'request_timeout')
    assert hasattr(config_module, 'max_retries')
    assert hasattr(config_module, 'retry_delay')
    
    # Test console output defaults
    assert hasattr(config_module, 'console_minimal_mode')
    assert hasattr(config_module, 'show_ai_debug_panels')
    assert hasattr(config_module, 'show_litellm_console_logs')
    assert hasattr(config_module, 'show_performance_timers')
    assert hasattr(config_module, 'console_debug_level')


def test_config_values():
    """Test configuration values are reasonable."""
    # Test that timeout is reasonable
    assert config_module.request_timeout > 0
    assert config_module.request_timeout <= 3600  # Not more than 1 hour
    
    # Test retry settings
    assert config_module.max_retries >= 0
    assert config_module.retry_delay >= 0
    
    # Test model name
    assert isinstance(config_module.model, str)
    assert len(config_module.model) > 0


def test_config_boolean_fields():
    """Test boolean configuration fields."""
    boolean_fields = [
        'debug_mode',
        'log_to_file',
        'log_file_rotation',
        'console_rich_output',
        'show_performance_timers',
        'show_ai_debug_panels',
        'show_litellm_console_logs',
        'console_minimal_mode',
        'force_ipv4'
    ]
    
    for field in boolean_fields:
        if hasattr(config_module, field):
            value = getattr(config_module, field)
            assert isinstance(value, bool), f"{field} should be boolean, got {type(value)}"


def test_config_string_fields():
    """Test string configuration fields."""
    string_fields = [
        'log_level',
        'log_directory',
        'console_debug_level',
        'model'
    ]
    
    for field in string_fields:
        if hasattr(config_module, field):
            value = getattr(config_module, field)
            assert isinstance(value, str), f"{field} should be string, got {type(value)}"


def test_config_numeric_fields():
    """Test numeric configuration fields."""
    numeric_fields = [
        'request_timeout',
        'max_retries',
        'retry_delay'
    ]
    
    for field in numeric_fields:
        if hasattr(config_module, field):
            value = getattr(config_module, field)
            assert isinstance(value, (int, float)), f"{field} should be numeric, got {type(value)}"
            assert value >= 0, f"{field} should be non-negative"


def test_config_optional_fields():
    """Test optional configuration fields that can be None."""
    optional_fields = [
        'api_base',
        'api_version',
        'api_key'
    ]
    
    for field in optional_fields:
        if hasattr(config_module, field):
            value = getattr(config_module, field)
            # These can be None or strings
            assert value is None or isinstance(value, str), f"{field} should be None or string"


def test_litellm_settings():
    """Test LiteLLM settings structure."""
    if hasattr(config_module, 'litellm_settings'):
        settings = config_module.litellm_settings
        assert isinstance(settings, dict)
        
        # Check expected keys
        expected_keys = ['set_verbose', 'json_logs', 'request_timeout', 'force_ipv4']
        for key in expected_keys:
            if key in settings:
                assert isinstance(settings[key], (bool, int, float))


def test_provider_settings():
    """Test provider-specific settings structure."""
    if hasattr(config_module, 'provider_settings'):
        settings = config_module.provider_settings
        assert isinstance(settings, dict)
        
        # Check that provider sections are dictionaries
        for provider, provider_config in settings.items():
            assert isinstance(provider_config, dict), f"Provider {provider} config should be dict"


def test_config_modification():
    """Test that config values can be modified."""
    original_debug = config_module.debug_mode
    
    # Modify value
    config_module.debug_mode = not original_debug
    assert config_module.debug_mode != original_debug
    
    # Restore original value
    config_module.debug_mode = original_debug
    assert config_module.debug_mode == original_debug


def test_config_import_structure():
    """Test that config module imports correctly."""
    # Test direct attribute access
    assert hasattr(config_module, 'debug_mode')
    assert hasattr(config_module, 'model')
    
    # Test that we can get all attributes
    config_attrs = dir(config_module)
    assert 'debug_mode' in config_attrs
    assert 'model' in config_attrs


def test_config_environment_integration():
    """Test config behavior with environment variables."""
    # This tests that the config module doesn't break with env vars
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}):
        # Should be able to access config without issues
        assert hasattr(config_module, 'api_key')
        
        # The config module itself doesn't read env vars, but this tests compatibility
        env_key = os.getenv('OPENAI_API_KEY')
        assert env_key == 'test-key'


def run_all_config_tests():
    """Run all configuration tests and report results."""
    tests = [
        test_config_defaults,
        test_config_values,
        test_config_boolean_fields,
        test_config_string_fields,
        test_config_numeric_fields,
        test_config_optional_fields,
        test_litellm_settings,
        test_provider_settings,
        test_config_modification,
        test_config_import_structure,
        test_config_environment_integration
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(f"✅ {test.__name__}")
        except Exception as e:
            results.append(f"❌ {test.__name__}: {e}")
    
    print("Config Module Test Results:")
    print("=" * 40)
    for result in results:
        print(result)
    
    passed = sum(1 for r in results if r.startswith("✅"))
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_config_tests()
    exit(0 if success else 1) 