#!/usr/bin/env python3
"""
Direct test of the effects parsing fix with dictionary-format effects.
This bypasses the S3 workflow and tests the specific TypeError fix.
"""

import sys
import json
import tempfile
import os
sys.path.append('.')

from reel_assembler import assemble_reel

def create_test_data_with_dictionary_effects():
    """Create test data that includes the problematic dictionary-format effects."""
    
    edit_plan = {
        "edit_plan": [
            {
                "global_shot_id": 0,
                "segment_start_in_shot_sec": 0.0,
                "segment_end_in_shot_sec": 2.5,
                "color_grade_style": "VibrantPop",
                "transition_to_next": "Cut",
                "effects": [
                    {"name": "color_grade", "settings": {"look": "warm_tropical"}},
                    "SlightZoomIn_15%"
                ],
                "reasoning": "Test mixed effects formats"
            },
            {
                "global_shot_id": 1,
                "segment_start_in_shot_sec": 1.0,
                "segment_end_in_shot_sec": 3.0,
                "color_grade_style": "CoolCinematic",
                "transition_to_next": "Dissolve",
                "effects": [
                    {"name": "color_grade", "settings": {"look": "vibrant"}},
                    {"name": "slow_motion", "settings": {"factor": 0.5}}
                ],
                "reasoning": "Test all dictionary effects"
            }
        ]
    }
    
    shots_metadata = {
        0: {
            "global_shot_id": 0,
            "original_video_path": "/home/ubuntu/web_editing_app/sample_files/sample_video1.mp4",
            "start_time_sec": 0.0,
            "end_time_sec": 10.0,
            "duration_sec": 10.0
        },
        1: {
            "global_shot_id": 1,
            "original_video_path": "/home/ubuntu/web_editing_app/sample_files/sample_video2.mp4",
            "start_time_sec": 0.0,
            "end_time_sec": 8.0,
            "duration_sec": 8.0
        }
    }
    
    audio_data = {
        "path": "/home/ubuntu/web_editing_app/sample_files/sample_audio.wav",
        "duration": 30.0,
        "segment_start_sec": 0.0,
        "segment_end_sec": 5.5
    }
    
    return edit_plan, shots_metadata, audio_data

def test_effects_parsing_fix():
    """Test the effects parsing fix with dictionary-format effects."""
    print("=== Testing Effects Parsing Fix with Dictionary Effects ===")
    
    edit_plan, shots_metadata, audio_data = create_test_data_with_dictionary_effects()
    
    print(f"Created test data with {len(edit_plan['edit_plan'])} segments")
    for i, seg in enumerate(edit_plan['edit_plan']):
        print(f"  Segment {i+1} effects: {seg['effects']}")
    
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
        output_path = tmp_file.name
    
    try:
        print("\nRunning reel assembly with dictionary effects...")
        success, actual_output = assemble_reel(edit_plan, shots_metadata, audio_data, output_path)
        
        if success:
            print(f"✅ SUCCESS! Effects parsing fix works correctly.")
            print(f"   Output file: {actual_output}")
            if os.path.exists(actual_output):
                file_size = os.path.getsize(actual_output)
                print(f"   File size: {file_size} bytes")
            return True
        else:
            print(f"❌ FAILED! Reel assembly failed.")
            return False
            
    except Exception as e:
        print(f"❌ ERROR! Exception during processing: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except:
                pass

if __name__ == '__main__':
    success = test_effects_parsing_fix()
    if success:
        print("\n🎉 Effects parsing fix verified successfully!")
        print("   The TypeError for dictionary-format effects has been resolved.")
    else:
        print("\n💥 Effects parsing fix test failed!")
        print("   The TypeError may still occur with dictionary-format effects.")
    
    sys.exit(0 if success else 1)
