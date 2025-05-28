"""
Comprehensive test runner for the AI Game project.

Runs all test modules and provides detailed reporting of test results.
"""

import os
import sys
import time
import traceback
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import test modules with graceful error handling
test_functions = {}

try:
    from aigame.tests.test_config import run_all_config_tests
    test_functions['config'] = run_all_config_tests
except ImportError as e:
    print(f"Warning: Could not import config tests: {e}")

try:
    from aigame.tests.test_logger import run_all_logger_tests
    test_functions['logger'] = run_all_logger_tests
except ImportError as e:
    print(f"Warning: Could not import logger tests: {e}")

try:
    from aigame.tests.test_main import run_all_main_tests
    test_functions['main'] = run_all_main_tests
except ImportError as e:
    print(f"Warning: Could not import main tests: {e}")

try:
    from aigame.tests.test_package import run_all_package_tests
    test_functions['package'] = run_all_package_tests
except ImportError as e:
    print(f"Warning: Could not import package tests: {e}")

try:
    from aigame.tests.test_ai_inference import run_all_tests as run_ai_inference_tests
    test_functions['ai_inference'] = run_ai_inference_tests
except ImportError as e:
    print(f"Warning: Could not import AI inference tests: {e}")


class TestRunner:
    """Comprehensive test runner with reporting capabilities."""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def run_test_module(self, module_name, test_function):
        """Run a test module and capture results."""
        print(f"\n{'='*60}")
        print(f"Running {module_name} Tests")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            success = test_function()
            end_time = time.time()
            duration = end_time - start_time
            
            self.results[module_name] = {
                'success': success,
                'duration': duration,
                'error': None
            }
            
            status = "✅ PASSED" if success else "❌ FAILED"
            print(f"\n{module_name}: {status} ({duration:.2f}s)")
            
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            
            self.results[module_name] = {
                'success': False,
                'duration': duration,
                'error': str(e)
            }
            
            print(f"\n❌ {module_name}: ERROR ({duration:.2f}s)")
            print(f"Error: {e}")
            if hasattr(e, '__traceback__'):
                traceback.print_exc()
    
    def run_all_tests(self):
        """Run all available test modules."""
        self.start_time = time.time()
        
        print("🎮 AI Game - Comprehensive Test Suite")
        print("=" * 60)
        print(f"Starting test run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Define test modules to run
        test_modules = [
            ("Package Structure", test_functions.get('package')),
            ("Configuration", test_functions.get('config')),
            ("Logger", test_functions.get('logger')),
            ("AI Inference", test_functions.get('ai_inference')),
            ("Main Script", test_functions.get('main')),
        ]
        
        # Run each test module
        for module_name, test_function in test_modules:
            if test_function:
                self.run_test_module(module_name, test_function)
            else:
                print(f"\n⚠️  Skipping {module_name}: Test function not available")
                self.results[module_name] = {
                    'success': False,
                    'duration': 0,
                    'error': 'Test function not available'
                }
        
        self.end_time = time.time()
        return self.print_summary()
    
    def print_summary(self):
        """Print comprehensive test summary."""
        total_duration = self.end_time - self.start_time
        
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results.values() if r['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Test Modules: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Total Duration: {total_duration:.2f}s")
        print()
        
        # Detailed results
        print("Detailed Results:")
        print("-" * 40)
        for module_name, result in self.results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = result['duration']
            print(f"{module_name:<20} {status} ({duration:.2f}s)")
            
            if result['error']:
                print(f"  Error: {result['error']}")
        
        print()
        
        # Overall result
        if failed_tests == 0:
            print("🎉 ALL TESTS PASSED!")
            return True
        else:
            print(f"💥 {failed_tests} TEST MODULE(S) FAILED")
            return False
    
    def run_quick_tests(self):
        """Run a subset of quick tests for rapid feedback."""
        print("🚀 AI Game - Quick Test Suite")
        print("=" * 40)
        
        self.start_time = time.time()
        
        # Run only essential tests
        quick_tests = [
            ("Package Structure", test_functions.get('package')),
            ("Configuration", test_functions.get('config')),
        ]
        
        for module_name, test_function in quick_tests:
            if test_function:
                self.run_test_module(module_name, test_function)
            else:
                print(f"⚠️  Skipping {module_name}: Not available")
                self.results[module_name] = {
                    'success': False,
                    'duration': 0,
                    'error': 'Test function not available'
                }
        
        self.end_time = time.time()
        return self.print_summary()


def run_unit_tests():
    """Run unit tests only (no integration tests)."""
    print("🧪 AI Game - Unit Tests Only")
    print("=" * 40)
    
    runner = TestRunner()
    runner.start_time = time.time()
    
    # Run unit tests
    unit_tests = [
        ("Package Structure", test_functions.get('package')),
        ("Configuration", test_functions.get('config')),
        ("Logger", test_functions.get('logger')),
        ("Main Script", test_functions.get('main')),
    ]
    
    for module_name, test_function in unit_tests:
        if test_function:
            runner.run_test_module(module_name, test_function)
        else:
            print(f"⚠️  Skipping {module_name}: Not available")
            runner.results[module_name] = {
                'success': False,
                'duration': 0,
                'error': 'Test function not available'
            }
    
    runner.end_time = time.time()
    return runner.print_summary()


def run_integration_tests():
    """Run integration tests only (requires API key)."""
    print("🔗 AI Game - Integration Tests")
    print("=" * 40)
    
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  No OPENAI_API_KEY found. Integration tests require an API key.")
        print("   Set environment variable to run integration tests.")
        return False
    
    runner = TestRunner()
    runner.start_time = time.time()
    
    # Run integration tests
    integration_tests = [
        ("AI Inference", test_functions.get('ai_inference')),
    ]
    
    for module_name, test_function in integration_tests:
        if test_function:
            runner.run_test_module(module_name, test_function)
        else:
            print(f"⚠️  Skipping {module_name}: Not available")
            runner.results[module_name] = {
                'success': False,
                'duration': 0,
                'error': 'Test function not available'
            }
    
    runner.end_time = time.time()
    return runner.print_summary()


def main():
    """Main test runner entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Game Test Runner")
    parser.add_argument(
        '--mode', 
        choices=['all', 'unit', 'integration', 'quick'],
        default='all',
        help='Test mode to run'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print(f"Running in {args.mode} mode with verbose output")
    
    # Run tests based on mode
    if args.mode == 'all':
        runner = TestRunner()
        success = runner.run_all_tests()
    elif args.mode == 'unit':
        success = run_unit_tests()
    elif args.mode == 'integration':
        success = run_integration_tests()
    elif args.mode == 'quick':
        runner = TestRunner()
        success = runner.run_quick_tests()
    else:
        print(f"Unknown mode: {args.mode}")
        return 1
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 