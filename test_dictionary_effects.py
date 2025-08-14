#!/usr/bin/env python3
"""
Test script to verify that both string and dictionary effect formats work correctly.
"""

import sys
sys.path.append('.')

from reel_assembler import parse_effect_with_value, parse_dictionary_effect

def test_string_effects():
    print("=== Testing String Effects ===")
    
    test_cases = [
        "SlowMotion_0.5x",
        "FastForward_2x", 
        "SlightZoomIn_15%",
        "Stabilize_Video_Level10"
    ]
    
    for effect in test_cases:
        name, value = parse_effect_with_value(effect)
        print(f"  {effect} -> name: {name}, value: {value}")

def test_dictionary_effects():
    print("\n=== Testing Dictionary Effects ===")
    
    test_cases = [
        {'name': 'color_grade', 'settings': {'look': 'warm_tropical'}},
        {'name': 'color_grade', 'settings': {'look': 'vibrant'}},
        {'name': 'color_grade', 'settings': {'look': 'cinematic'}},
        {'name': 'slow_motion', 'settings': {'factor': 0.5}},
        {'name': 'fast_forward', 'settings': {'factor': 2.0}},
        {'name': 'unknown_effect', 'settings': {'param': 'value'}}
    ]
    
    for effect in test_cases:
        name, value = parse_dictionary_effect(effect)
        print(f"  {effect} -> name: {name}, value: {value}")

if __name__ == '__main__':
    test_string_effects()
    test_dictionary_effects()
    print("\nTest completed!")
