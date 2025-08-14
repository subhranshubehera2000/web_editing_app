#!/usr/bin/env python3
"""
Test script to run the video processing with debugging enabled
to identify where video duration is being lost.
"""

import sys
import json
sys.path.append('.')

from reel_assembler import assemble_reel

def main():
    print("=== Testing video processing with debugging enabled ===")
    
    with open('output/ai_edit_plan.json', 'r') as f:
        edit_plan = json.load(f)
    
    with open('output/all_shots_metadata.json', 'r') as f:
        shots_metadata = json.load(f)
    
    shots_dict = {shot['global_shot_id']: shot for shot in shots_metadata}
    
    with open('output/audio_analysis_summary.json', 'r') as f:
        audio_analysis = json.load(f)
    
    segment_info = audio_analysis.get('selected_segment', {})
    segment_start = segment_info.get('start_sec', 10.0)
    segment_end = segment_info.get('end_sec', 20.0)
    
    audio_data = {
        'path': 'input_audio/myoudio.mp3',
        'duration': 30.0,
        'segment_start_sec': segment_start,
        'segment_end_sec': segment_end
    }
    
    expected_audio_duration = segment_end - segment_start
    
    print(f'Edit plan has {len(edit_plan["edit_plan"])} segments')
    print(f'Audio segment: {segment_start:.3f}s to {segment_end:.3f}s ({expected_audio_duration:.3f}s duration)')
    
    total_planned_duration = 0.0
    for i, seg in enumerate(edit_plan["edit_plan"]):
        seg_duration = seg["segment_end_in_shot_sec"] - seg["segment_start_in_shot_sec"]
        total_planned_duration += seg_duration
        print(f'  Segment {i+1}: {seg_duration:.3f}s (effects: {seg.get("effects", [])})')
    
    print(f'Total planned video duration: {total_planned_duration:.3f}s')
    print(f'Expected audio duration: {expected_audio_duration:.3f}s')
    print(f'Duration difference: {total_planned_duration - expected_audio_duration:.3f}s')
    print()
    
    print("Running video assembly with debugging...")
    success, output_file = assemble_reel(edit_plan, shots_dict, audio_data, 'output/debug_test_reel.mp4')
    
    print(f'\nAssembly result: {success}')
    if success:
        print(f'Output file: {output_file}')
    else:
        print('Assembly failed!')

if __name__ == '__main__':
    main()
