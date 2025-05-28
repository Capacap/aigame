"""
Test suite for package initialization and public API.

Tests package imports, public API availability, and module structure.
"""

import os
import sys
from unittest.mock import patch, MagicMock


def test_package_imports():
    """Test that package imports work correctly."""
    try:
        import aigame
        assert hasattr(aigame, 'generate_text_response')
        assert hasattr(aigame, 'generate_json_response')
        assert hasattr(aigame, 'get_logger')
    except ImportError as e:
        assert False, f"Package import failed: {e}"


def test_public_api_functions():
    """Test that public API functions are callable."""
    try:
        from aigame import generate_text_response, generate_json_response, get_logger
        
        # Test that functions are callable
        assert callable(generate_text_response)
        assert callable(generate_json_response)
        assert callable(get_logger)
        
    except ImportError as e:
        assert False, f"Public API import failed: {e}"


def test_package_metadata():
    """Test package metadata attributes."""
    try:
        import aigame
        
        # Test version
        assert hasattr(aigame, '__version__')
        assert isinstance(aigame.__version__, str)
        assert len(aigame.__version__) > 0
        
        # Test author
        assert hasattr(aigame, '__author__')
        assert isinstance(aigame.__author__, str)
        
        # Test description
        assert hasattr(aigame, '__description__')
        assert isinstance(aigame.__description__, str)
        
        # Test __all__
        assert hasattr(aigame, '__all__')
        assert isinstance(aigame.__all__, list)
        assert len(aigame.__all__) > 0
        
    except ImportError as e:
        assert False, f"Package metadata test failed: {e}"


def test_all_exports():
    """Test that __all__ contains expected exports."""
    try:
        import aigame
        
        expected_exports = [
            'generate_text_response',
            'generate_json_response',
            'get_logger'
        ]
        
        for export in expected_exports:
            assert export in aigame.__all__, f"Missing export: {export}"
            assert hasattr(aigame, export), f"Export not available: {export}"
            
    except ImportError as e:
        assert False, f"__all__ exports test failed: {e}"


def test_core_module_imports():
    """Test that core modules can be imported."""
    try:
        from aigame.core import config, logger, ai_inference
        
        # Test that modules have expected attributes
        assert hasattr(config, 'debug_mode')
        assert hasattr(config, 'model')
        assert hasattr(logger, 'get_logger')
        assert hasattr(ai_inference, 'generate_text_response')
        assert hasattr(ai_inference, 'generate_json_response')
        
    except ImportError as e:
        assert False, f"Core module imports failed: {e}"


def test_direct_core_imports():
    """Test direct imports from core modules."""
    try:
        import aigame.core.config as config
        from aigame.core.logger import get_logger
        from aigame.core.ai_inference import generate_text_response, generate_json_response
        
        # Test that modules/functions are properly imported
        assert config is not None
        assert hasattr(config, 'debug_mode')
        assert get_logger is not None
        assert generate_text_response is not None
        assert generate_json_response is not None
        
    except ImportError as e:
        assert False, f"Direct core imports failed: {e}"


def test_package_structure():
    """Test package directory structure."""
    import aigame
    package_dir = os.path.dirname(aigame.__file__)
    
    # Test that core directory exists
    core_dir = os.path.join(package_dir, 'core')
    assert os.path.isdir(core_dir), "Core directory missing"
    
    # Test that tests directory exists
    tests_dir = os.path.join(package_dir, 'tests')
    assert os.path.isdir(tests_dir), "Tests directory missing"
    
    # Test that core modules exist
    core_files = ['__init__.py', 'config.py', 'logger.py', 'ai_inference.py']
    for file in core_files:
        file_path = os.path.join(core_dir, file)
        assert os.path.isfile(file_path), f"Core file missing: {file}"


def test_import_error_handling():
    """Test graceful handling of import errors."""
    # Test importing non-existent module
    try:
        import importlib
        importlib.import_module('aigame.nonexistent')
        assert False, "Should have raised ImportError"
    except ImportError:
        # Expected behavior
        pass
    except Exception as e:
        assert False, f"Unexpected exception: {e}"


def test_function_signatures():
    """Test that public API functions have expected signatures."""
    try:
        from aigame import generate_text_response, generate_json_response, get_logger
        import inspect
        
        # Test generate_text_response signature
        sig = inspect.signature(generate_text_response)
        params = list(sig.parameters.keys())
        assert 'messages' in params
        assert 'config' in params
        
        # Test generate_json_response signature
        sig = inspect.signature(generate_json_response)
        params = list(sig.parameters.keys())
        assert 'messages' in params
        assert 'config' in params
        
        # Test get_logger signature
        sig = inspect.signature(get_logger)
        params = list(sig.parameters.keys())
        assert 'name' in params
        
    except ImportError as e:
        assert False, f"Function signature test failed: {e}"


def test_module_docstrings():
    """Test that modules have proper docstrings."""
    try:
        import aigame
        from aigame.core import config, logger, ai_inference
        
        # Test package docstring
        assert aigame.__doc__ is not None
        assert len(aigame.__doc__.strip()) > 0
        
        # Test core module docstrings
        modules = [config, logger, ai_inference]
        for module in modules:
            assert module.__doc__ is not None, f"Missing docstring: {module.__name__}"
            assert len(module.__doc__.strip()) > 0, f"Empty docstring: {module.__name__}"
            
    except ImportError as e:
        assert False, f"Module docstring test failed: {e}"


def test_circular_imports():
    """Test that there are no circular import issues."""
    try:
        # Import in different orders to test for circular dependencies
        from aigame import generate_text_response
        from aigame.core.ai_inference import generate_text_response as ai_gen
        import aigame.core.config as config
        from aigame.core.logger import get_logger
        
        # All should work without circular import errors
        assert generate_text_response is not None
        assert ai_gen is not None
        assert config is not None
        assert get_logger is not None
        
    except ImportError as e:
        assert False, f"Circular import detected: {e}"


def run_all_package_tests():
    """Run all package tests and report results."""
    tests = [
        test_package_imports,
        test_public_api_functions,
        test_package_metadata,
        test_all_exports,
        test_core_module_imports,
        test_direct_core_imports,
        test_package_structure,
        test_import_error_handling,
        test_function_signatures,
        test_module_docstrings,
        test_circular_imports
    ]
    
    results = []
    for test in tests:
        try:
            test()
            results.append(f"✅ {test.__name__}")
        except Exception as e:
            results.append(f"❌ {test.__name__}: {e}")
    
    print("Package Structure Test Results:")
    print("=" * 40)
    for result in results:
        print(result)
    
    passed = sum(1 for r in results if r.startswith("✅"))
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_package_tests()
    exit(0 if success else 1) 