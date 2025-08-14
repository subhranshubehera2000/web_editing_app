#!/usr/bin/env python3
"""
Test script to verify effects parsing functions work correctly without importing moviepy.
"""

import re

def parse_effect_with_value(effect_name_str, default_value_if_not_specified=None):
    stabilize_match = re.match(r"([A-Za-z0-9]+)_([A-Za-z]+)_([A-Za-z]+)(\d+)", effect_name_str)
    if stabilize_match:
        name = stabilize_match.group(1) + stabilize_match.group(2).capitalize() + stabilize_match.group(3).capitalize()
        value_str = stabilize_match.group(4)
        try: return name, float(value_str)
        except ValueError: print(f"Warn: Val parse fail {name} from '{effect_name_str}'"); return name, default_value_if_not_specified
    general_match = re.match(r"([A-Za-z0-9]+)(?:_([A-Za-z]+))?_([\d\.]+)(%|x|px)?", effect_name_str)
    if general_match:
        name_part1 = general_match.group(1); name_detail_part = general_match.group(2); value_str = general_match.group(3); unit = general_match.group(4)
        full_name = name_part1
        if name_detail_part: full_name += name_detail_part.capitalize()
        try:
            value = float(value_str)
            if unit == '%': return full_name, value / 100.0
            return full_name, value
        except ValueError: print(f"Warn: Val parse fail general for '{effect_name_str}'."); return full_name, default_value_if_not_specified
    simple_name_val_match = re.match(r"([A-Za-z]+)(\d+\.?\d*)", effect_name_str)
    if simple_name_val_match:
        name_part = simple_name_val_match.group(1); value_part_str = simple_name_val_match.group(2)
        try:
            value = float(value_part_str)
            if name_part == "SlightZoomIn" and value > 1 and value <= 100: return name_part, value / 100.0
            return name_part, value
        except ValueError: print(f"Warn: Val parse fail simple for '{effect_name_str}'."); return name_part, default_value_if_not_specified
    return effect_name_str, default_value_if_not_specified

def parse_dictionary_effect(effect_dict):
    if not isinstance(effect_dict, dict) or 'name' not in effect_dict:
        print(f"Invalid dictionary effect format: {effect_dict}")
        return str(effect_dict), None
    
    effect_name = effect_dict['name']
    settings = effect_dict.get('settings', {})
    
    if effect_name == 'color_grade':
        look = settings.get('look', '')
        color_mapping = {
            'warm_tropical': 'WarmVintage',
            'warm': 'WarmVintage', 
            'tropical': 'WarmVintage',
            'vibrant': 'VibrantPop',
            'pop': 'VibrantPop',
            'cinematic': 'CoolCinematic',
            'cool': 'CoolCinematic',
            'monochrome': 'MonochromeClassic',
            'classic': 'MonochromeClassic',
            'natural': 'NaturalEnhance',
            'enhance': 'NaturalEnhance'
        }
        
        mapped_style = None
        look_lower = look.lower()
        for key, style in color_mapping.items():
            if key in look_lower:
                mapped_style = style
                break
        
        if mapped_style:
            print(f"    Mapped color_grade look '{look}' to style '{mapped_style}'")
            return 'ColorGrade', mapped_style
        else:
            print(f"    Unknown color_grade look '{look}', using NaturalEnhance")
            return 'ColorGrade', 'NaturalEnhance'
    
    elif effect_name in ['slow_motion', 'fast_forward']:
        speed_factor = settings.get('factor', 1.0)
        if effect_name == 'slow_motion':
            return 'SlowMotion', speed_factor
        else:
            return 'FastForward', speed_factor
    
    print(f"    Unknown dictionary effect '{effect_name}', treating as unrecognized")
    return effect_name, settings

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

def test_mixed_effects():
    print("\n=== Testing Mixed Effect Processing ===")
    
    mixed_effects = [
        "SlowMotion_0.5x",
        {'name': 'color_grade', 'settings': {'look': 'warm_tropical'}},
        "FastForward_2x",
        {'name': 'color_grade', 'settings': {'look': 'vibrant'}},
        "SlightZoomIn_15%"
    ]
    
    for effect in mixed_effects:
        if isinstance(effect, dict):
            name, value = parse_dictionary_effect(effect)
            print(f"  DICT: {effect} -> name: {name}, value: {value}")
        elif isinstance(effect, str):
            name, value = parse_effect_with_value(effect)
            print(f"  STR:  {effect} -> name: {name}, value: {value}")
        else:
            print(f"  UNKNOWN: {effect}")

if __name__ == '__main__':
    test_string_effects()
    test_dictionary_effects()
    test_mixed_effects()
    print("\nAll parsing tests completed successfully!")
