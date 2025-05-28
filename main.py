#!/usr/bin/env python3
"""
AI Game - Main Entry Point

Simple demonstration of the AI inference capabilities.
"""

import os
from dataclasses import dataclass
from aigame import generate_text_response, generate_json_response

@dataclass
class SimpleConfig:
    """Simple configuration for AI inference demonstration."""
    debug_mode: bool = False  # Changed to False for cleaner console output
    model: str = "gpt-4o-mini"
    api_key: str = None  # Will use OPENAI_API_KEY environment variable
    api_base: str = None
    api_version: str = None
    request_timeout: int = 30
    force_ipv4: bool = False
    max_retries: int = 2
    retry_delay: float = 1.0

if __name__ == "__main__":
    print("🎮 AI Game - Inference Demo")
    print("=" * 40)
    
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  No OPENAI_API_KEY found. Set environment variable to run real demos.")
        print("   Example: export OPENAI_API_KEY='your-key-here'")
        exit(1)
    
    config = SimpleConfig()
    
    try:
        # Demonstrate text generation
        print("\n📝 Text Generation Demo:")
        text_messages = [{"role": "user", "content": "Say hello and introduce yourself as an AI game assistant"}]
        text_result = generate_text_response(text_messages, config)
        print(f"Response: {text_result['content']}")
        if text_result['reasoning']:
            print(f"Reasoning: {text_result['reasoning']}")
        
        # Demonstrate JSON generation
        print("\n🔧 JSON Generation Demo:")
        json_messages = [
            {"role": "system", "content": "Respond with valid JSON only"},
            {"role": "user", "content": "Create a simple game character in JSON format with name, level, and health"}
        ]
        json_result = generate_json_response(json_messages, config)
        print(f"JSON Response: {json_result['content']}")
        if json_result['reasoning']:
            print(f"Reasoning: {json_result['reasoning']}")
            
        print("\n✅ Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("Check your API key and network connection.")