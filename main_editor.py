# main_editor.py
import os
import json
import shutil
import time
import numpy as np 

from audio_analyzer import analyze_audio
from video_analyzer import detect_shots, extract_shot_visual_features
from bedrock_director import generate_ai_edit_plan, suggest_reel_themes 
from reel_assembler import assemble_reel

# --- Defaults for standalone or if app.py doesn't provide ---
DEFAULT_REEL_MIN_DURATION_SEC = 10 
DEFAULT_REEL_MAX_DURATION_SEC = 20 
# This placeholder string is what the UI might send if user wants AI to suggest.
# It should match exactly (case-insensitively) what app.py checks for.
DEFAULT_REEL_THEME_PLACEHOLDER = "ai will suggest a theme" 
DEFAULT_REEL_THEME_FALLBACK = "Engaging Visual Montage" # Used if AI suggestion fails AND user theme was placeholder/empty

PROFILE_STEPS = True # For development timing

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating):
            if np.isnan(obj): return None 
            if np.isinf(obj): return str(obj)
            return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super(NpEncoder, self).default(obj)

def create_ai_edited_reel(
    user_theme_override, # Can be user's theme, the placeholder string, or None (from app.py)
    user_min_duration,
    user_max_duration,
    audio_file_full_path,      # FULL PATH to the (downloaded) audio file
    video_file_full_paths_list, # List of FULL PATHS to (downloaded) video files
    output_base_dir_for_job,      # e.g., /tmp/ai_editor_job_XXXXXX/output
    job_id="unknown_job",
    progress_update_callback=None  # Callback function for progress
):
    min_duration = int(user_min_duration) if user_min_duration is not None else DEFAULT_REEL_MIN_DURATION_SEC
    max_duration = int(user_max_duration) if user_max_duration is not None else DEFAULT_REEL_MAX_DURATION_SEC
    
    if not os.path.exists(output_base_dir_for_job):
        os.makedirs(output_base_dir_for_job, exist_ok=True) 
    
    # Define output paths relative to job's output dir
    edit_plan_file = os.path.join(output_base_dir_for_job, f"ai_edit_plan_job_{job_id}.json")
    all_shots_metadata_file = os.path.join(output_base_dir_for_job, f"all_shots_metadata_job_{job_id}.json")
    audio_analysis_file = os.path.join(output_base_dir_for_job, f"audio_analysis_summary_job_{job_id}.json")
    # The assembler will use output_base_dir_for_job to construct the final path too for consistency if modified
    final_reel_file_output_path_in_job_dir = os.path.join(output_base_dir_for_job, f"final_ai_reel_job_{job_id}.mp4")

    def report_progress(percent, message_detail):
        print(f"[MainEditor Progress Job {job_id}] {percent}% - {message_detail}")
        if progress_update_callback:
            progress_update_callback(percent, f"{message_detail}") # Just pass message_detail

    print(f"Starting AI Reel for Job ID: {job_id} in dir {output_base_dir_for_job}")
    print(f"  Expecting audio at full path: {audio_file_full_path}")
    for vid_p_idx, vid_p in enumerate(video_file_full_paths_list): print(f"  Expecting video {vid_p_idx+1} at: {vid_p}")

    overall_start_time = time.time()
    report_progress(0, "Initializing main editing process...")

    # --- Step 1: Analyze Specified Audio ---
    step_start_time = time.time(); report_progress(5, "Analyzing audio file...")
    if not os.path.exists(audio_file_full_path):
        msg = f"Audio file '{audio_file_full_path}' (passed as full path) NOT FOUND."
        report_progress(10, msg); print(f"Error: {msg}"); return False, None 
    
    audio_data = analyze_audio(audio_file_full_path) 
    if not audio_data: 
        report_progress(10, "Audio analysis failed."); print("Error: Audio analysis failed."); return False, None
    report_progress(20, "Audio analysis complete.")
    try: 
        with open(audio_analysis_file, "w") as f: json.dump(audio_data, f, indent=2, cls=NpEncoder) 
        print(f"Audio analysis summary saved to {audio_analysis_file}")
    except Exception as e: print(f"Warn: Could not save audio summary: {e}")
    if PROFILE_STEPS: print(f"Step 1 duration: {time.time() - step_start_time:.2f}s")

    # --- Step 2: Analyze Specified Video Clips ---
    step_start_time = time.time(); report_progress(21, "Starting video analysis...")
    all_shots_metadata_list = []; global_shot_id_counter = 0
    if not video_file_full_paths_list: 
        report_progress(22, "No videos specified."); print("Error:No videos specified."); return False, None
    
    num_videos = len(video_file_full_paths_list)
    video_analysis_total_progress_share = 39 # Video analysis makes up from 21% to 60% (39 points)

    for video_idx, current_video_full_path in enumerate(video_file_full_paths_list):
        video_file_basename = os.path.basename(current_video_full_path)
        # Calculate progress within this step more granularly
        progress_within_this_step_start = 21 + int(((video_idx) / num_videos) * video_analysis_total_progress_share)
        report_progress(progress_within_this_step_start, f"Analyzing video {video_idx + 1}/{num_videos}: {video_file_basename}")
        
        if not os.path.exists(current_video_full_path) or os.path.getsize(current_video_full_path)<1024: 
            print(f"    Warning: Video file {current_video_full_path} missing/small after download. Skipping."); continue
        
        shots_in_this_video = detect_shots(current_video_full_path) # detect_shots expects a full path
        if not shots_in_this_video: 
            print(f"    No shots detected in {video_file_basename}."); continue

        for shot_info in shots_in_this_video:
            # IMPORTANT: Ensure shot_info["original_video_path"] from detect_shots IS the full path.
            # If detect_shots stores relative paths, this needs adjustment.
            # Assuming detect_shots populates 'original_video_path' with the full path it received.
            shot_info["global_shot_id"] = global_shot_id_counter
            print(f"    Extracting features for GID {global_shot_id_counter} (from {video_file_basename}: "
                  f"{shot_info['start_time_sec']:.2f}s - {shot_info['end_time_sec']:.2f}s, ShotDur: {shot_info['duration_sec']:.2f}s)")
            
            if shot_info['duration_sec'] < 0.05: # Min duration for feature extraction
                print(f"      Skipping feature extraction for very short fragment (duration {shot_info['duration_sec']:.3f}s)."); 
                visual_features = {"avg_brightness": 0.0, "avg_motion_score": 0.0, "avg_color_rgb": [0,0,0]}
            else:
                visual_features = extract_shot_visual_features(
                    shot_info["original_video_path"], # This must be the full path
                    shot_info["start_time_sec"],
                    shot_info["end_time_sec"]
                )
            shot_info.update(visual_features)
            all_shots_metadata_list.append(shot_info)
            print(f"      Extracted Features: Brightness={visual_features.get('avg_brightness', 0.0):.1f}, "
                  f"Motion={visual_features.get('avg_motion_score', 0.0):.1f}")
            global_shot_id_counter += 1
        
        progress_within_this_step_end = 21 + int(((video_idx + 1) / num_videos) * video_analysis_total_progress_share)
        report_progress(progress_within_this_step_end, f"Finished analyzing video {video_idx + 1}/{num_videos}")

    if not all_shots_metadata_list: 
        report_progress(60,"No usable shots extracted from videos."); print("Error: No usable shots found."); return False, None
    report_progress(60, "Video analysis complete.")
    try: 
        with open(all_shots_metadata_file, "w") as f: json.dump(all_shots_metadata_list,f,indent=2,cls=NpEncoder)
        print(f"All shots metadata saved to {all_shots_metadata_file}")
    except Exception as e: print(f"Warn: Could not save all_shots_metadata.json: {e}")
    if PROFILE_STEPS: print(f"Step 2 duration: {time.time() - step_start_time:.2f}s")
    
    # --- Step 2.5: Determine Theme ---
    final_theme_for_edit_plan = DEFAULT_REEL_THEME_FALLBACK # Initialize with a fallback

    # Check if user provided a theme AND it's not the placeholder/empty
    if user_theme_override and \
       user_theme_override.strip() != "" and \
       user_theme_override.strip().lower() != DEFAULT_REEL_THEME_PLACEHOLDER.lower():
        final_theme_for_edit_plan = user_theme_override
        report_progress(61, f"Using user-provided theme: '{final_theme_for_edit_plan}'.")
        print(f"Using user-provided theme: '{final_theme_for_edit_plan}'")
    else:
        # User theme is None, empty, or the placeholder string, so attempt AI theme suggestion.
        report_progress(62, "No specific user theme or placeholder detected; attempting AI theme suggestion...")
        # Prepare summaries for theme suggestion
        audio_summary_for_theme_gen = {k: audio_data.get(k) for k in ["tempo", "duration", "simplified_energy_values_at_times"]}
        video_summary_for_theme_gen = {
            "num_shots": len(all_shots_metadata_list),
            "avg_motion_score": np.mean([s.get('avg_motion_score',0) for s in all_shots_metadata_list if s.get('avg_motion_score') is not None] or [0.0]),
            "avg_brightness": np.mean([s.get('avg_brightness',0) for s in all_shots_metadata_list if s.get('avg_brightness') is not None] or [0.0]),
            "total_video_duration_sec": sum(s.get('duration_sec',0) for s in all_shots_metadata_list)
        }
        ai_suggested_themes_list = suggest_reel_themes(audio_summary_for_theme_gen, video_summary_for_theme_gen, num_suggestions=1)
        
        if ai_suggested_themes_list and isinstance(ai_suggested_themes_list, list) and ai_suggested_themes_list:
            final_theme_for_edit_plan = ai_suggested_themes_list[0] # Auto-use the first suggestion
            report_progress(65, f"AI suggested theme will be used: '{final_theme_for_edit_plan}'.")
            print(f"AI successfully suggested theme: '{final_theme_for_edit_plan}'")
        else:
            # final_theme_for_edit_plan remains DEFAULT_REEL_THEME_FALLBACK
            report_progress(65, "AI theme suggestion failed or returned no themes. Using fallback theme.")
            print(f"AI theme suggestion failed. Using fallback theme: '{final_theme_for_edit_plan}'")
    
    # --- Step 3: Generate Edit Plan (using final_theme_for_edit_plan) ---
    step_start_time = time.time(); report_progress(66, f"Generating AI edit plan with theme: '{final_theme_for_edit_plan}'...")
    ai_edit_plan = generate_ai_edit_plan(
        audio_data, all_shots_metadata_list, min_duration, max_duration, reel_theme=final_theme_for_edit_plan
    )
    if not ai_edit_plan or "edit_plan" not in ai_edit_plan or not ai_edit_plan["edit_plan"]:
        report_progress(80,"Bedrock failed to generate a valid edit plan."); print("Error:Bedrock plan generation failed."); return False,None
    report_progress(85,f"AI edit plan generated ({len(ai_edit_plan['edit_plan'])} segments).")
    try: 
        with open(edit_plan_file,"w") as f:json.dump(ai_edit_plan,f,indent=2,cls=NpEncoder)
        print(f"AI Edit Plan saved to: {edit_plan_file}")
    except Exception as e: print(f"Error saving AI edit plan: {e}")
    if PROFILE_STEPS:print(f"Step 3 duration: {time.time()-step_start_time:.2f}s")

    # --- Step 4: Assemble Reel ---
    step_start_time = time.time(); report_progress(86, "Starting reel assembly process...")
    all_shots_dict={s['global_shot_id']:s for s in all_shots_metadata_list};
    
    # The assembler will write to final_reel_file_output_path_in_job_dir
    success_assembly, actual_output_path_from_assembler = assemble_reel(
        ai_edit_plan,all_shots_dict,audio_data,final_reel_file_output_path_in_job_dir
    )
    
    if success_assembly and os.path.exists(actual_output_path_from_assembler): 
        report_progress(98, "Reel assembled successfully.")
    else: 
        report_progress(98,"Reel assembly failed or output file not found."); success_assembly=False
    
    if PROFILE_STEPS:print(f"Step 4 duration: {time.time()-step_start_time:.2f}s")
    print(f"\nTotal main_editor.py processing duration for Job {job_id}: {time.time()-overall_start_time:.2f}s")
    
    return success_assembly, final_reel_file_output_path_in_job_dir if success_assembly else None

if __name__ == "__main__":
    print("Running main_editor.py directly for testing purposes...")
    
    # Define base directories for input files relative to this script
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    TEST_INPUT_AUDIO_DIR = os.path.join(current_script_dir, "input_audio")
    TEST_INPUT_VIDEOS_DIR = os.path.join(current_script_dir, "input_videos")
    TEST_OUTPUT_JOB_ROOT = os.path.join(current_script_dir, "output") # Where job-specific folders will go

    # Ensure directories exist for the test
    for d_path in [TEST_INPUT_AUDIO_DIR, TEST_INPUT_VIDEOS_DIR, TEST_OUTPUT_JOB_ROOT]:
        if not os.path.exists(d_path): os.makedirs(d_path, exist_ok=True)

    # Example files (ensure these exist in your input_audio and input_videos folders for this test)
    example_audio_filename = "myoudio.mp3" 
    example_video_filenames = [ 
        "video_20250603_121539_edit.mp4", 
        "video_20250603_121911_edit.mp4",
        "video_20250603_121829_edit.mp4" # Using 3 videos as per min constraint in UI
    ]
    
    example_audio_fullpath = os.path.join(TEST_INPUT_AUDIO_DIR, example_audio_filename)
    example_video_fullpaths = [os.path.join(TEST_INPUT_VIDEOS_DIR, fn) for fn in example_video_filenames]

    def dummy_progress_callback_for_test(percent, message):
        print(f"[MAIN_EDITOR_TEST_CALLBACK] Progress: {percent}% - Message: {message}")

    all_test_files_exist = True
    if not os.path.exists(example_audio_fullpath): 
        print(f"ERROR for standalone test: Example audio file '{example_audio_fullpath}' not found."); all_test_files_exist = False
    for vp in example_video_fullpaths:
        if not os.path.exists(vp): 
            print(f"ERROR for standalone test: Example video file '{vp}' not found."); all_test_files_exist = False
    
    if all_test_files_exist:
        print("\n--- Standalone Test 1: AI Suggests Theme (user_theme_override=None) ---")
        test1_job_id = "direct_main_suggest_theme_01"
        test1_output_dir_specific = os.path.join(TEST_OUTPUT_JOB_ROOT, test1_job_id) # Job specific output dir
        
        success1, output1 = create_ai_edited_reel( 
            user_theme_override=None, # Let AI suggest
            user_min_duration=7, user_max_duration=15,
            audio_file_full_path=example_audio_fullpath, 
            video_file_full_paths_list=example_video_fullpaths,
            output_base_dir_for_job=test1_output_dir_specific, 
            job_id=test1_job_id, 
            progress_update_callback=dummy_progress_callback_for_test 
        )
        if success1: print(f"Standalone AI Theme Suggest Test SUCCESSFUL. Output: {output1}")
        else: print("Standalone AI Theme Suggest Test FAILED.")

        print("\n--- Standalone Test 2: User Provides Specific Theme ---")
        user_defined_test_theme = "My Epic Test Reel Adventure"
        test2_job_id = "direct_main_custom_theme_01"
        test2_output_dir_specific = os.path.join(TEST_OUTPUT_JOB_ROOT, test2_job_id)

        success2, output2 = create_ai_edited_reel( 
            user_theme_override=user_defined_test_theme, 
            user_min_duration=8,user_max_duration=16, # Slightly different params
            audio_file_full_path=example_audio_fullpath, 
            video_file_full_paths_list=example_video_fullpaths,
            output_base_dir_for_job=test2_output_dir_specific, 
            job_id=test2_job_id,
            progress_update_callback=dummy_progress_callback_for_test
        )
        if success2: print(f"Standalone User Theme Test SUCCESSFUL. Output: {output2}")
        else: print("Standalone User Theme Test FAILED.")
    else:
        print("Cannot run standalone main_editor.py test due to missing example audio/video files. "
              f"Please ensure '{example_audio_filename}' is in '{TEST_INPUT_AUDIO_DIR}' and "
              f"videos like '{example_video_filenames[0]}' are in '{TEST_INPUT_VIDEOS_DIR}'.")
