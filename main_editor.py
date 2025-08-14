import os
import json
import shutil
import time
import numpy as np
import cv2

from audio_analyzer import analyze_audio_segment
from video_analyzer import detect_shots, extract_shot_visual_features, get_visual_content_description
from bedrock_director import generate_ai_edit_plan, suggest_reel_themes
from reel_assembler import assemble_reel

DEFAULT_REEL_THEME_PLACEHOLDER = "ai will suggest a theme"
DEFAULT_REEL_THEME_FALLBACK = "Engaging Visual Montage"

PROFILE_STEPS = True

class NpEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer): return int(obj)
        if isinstance(obj, np.floating): return float(obj)
        if isinstance(obj, np.ndarray): return obj.tolist()
        if isinstance(obj, np.bool_): return bool(obj)
        return super(NpEncoder, self).default(obj)

def create_ai_edited_reel(
    user_theme_override,
    audio_file_full_path,
    video_file_full_paths_list,
    output_base_dir_for_job,
    audio_segment_start_sec,
    audio_segment_end_sec,
    job_id="unknown_job",
    progress_update_callback=None
):
    reel_target_duration = audio_segment_end_sec - audio_segment_start_sec
    min_reel_duration = reel_target_duration - 0.2
    max_reel_duration = reel_target_duration + 0.2

    if not os.path.exists(output_base_dir_for_job):
        os.makedirs(output_base_dir_for_job, exist_ok=True)

    edit_plan_file = os.path.join(output_base_dir_for_job, f"ai_edit_plan_{job_id}.json")
    all_shots_metadata_file = os.path.join(output_base_dir_for_job, f"all_shots_metadata_{job_id}.json")
    audio_analysis_file = os.path.join(output_base_dir_for_job, f"audio_analysis_{job_id}.json")
    final_reel_file_output_path = os.path.join(output_base_dir_for_job, f"final_reel_{job_id}.mp4")

    def report_progress(percent, message_detail):
        if progress_update_callback: progress_update_callback(percent, message_detail)
        print(f"[MainEditor Progress {job_id}] {percent}% - {message_detail}")

    overall_start_time = time.time()
    report_progress(0, "Initializing editing process...")

    # --- Step 1: Analyze Specified Audio Segment ---
    step_start_time = time.time(); report_progress(5, "Analyzing audio segment...")
    audio_data = analyze_audio_segment(audio_file_full_path, start_sec=audio_segment_start_sec, end_sec=audio_segment_end_sec)
    if not audio_data:
        report_progress(10, "Detailed audio analysis on segment failed."); return False, None
    report_progress(20, "Audio segment analysis complete.")
    try:
        with open(audio_analysis_file, "w") as f: json.dump(audio_data, f, indent=2, cls=NpEncoder)
    except Exception as e: print(f"Warn: Could not save audio analysis file: {e}")
    if PROFILE_STEPS: print(f"Step 1 duration: {time.time() - step_start_time:.2f}s")


    # --- Step 2: Analyze Video Clips ---
    step_start_time = time.time(); report_progress(21, "Analyzing video shots & features...")
    all_shots_metadata_list = []
    global_shot_id_counter = 0
    if not video_file_full_paths_list:
        report_progress(22, "No video files specified."); return False, None

    for video_idx, video_path in enumerate(video_file_full_paths_list):
        prog = 21 + int((video_idx / len(video_file_full_paths_list)) * 39)
        report_progress(prog, f"Analyzing video {video_idx + 1}/{len(video_file_full_paths_list)}...")
        shots_from_scenedetect = detect_shots(video_path)

        if shots_from_scenedetect:
            for shot_info in shots_from_scenedetect:
                shot_info["global_shot_id"] = global_shot_id_counter
                visual_features = extract_shot_visual_features(shot_info["original_video_path"], shot_info["start_time_sec"], shot_info["end_time_sec"])
                shot_info.update(visual_features)
                all_shots_metadata_list.append(shot_info)
                global_shot_id_counter += 1
        else:
            try:
                cap = cv2.VideoCapture(video_path)
                if not cap.isOpened():
                    print(f"    WARNING: Could not open video {video_path} with OpenCV. Skipping.")
                    continue
                fps = cap.get(cv2.CAP_PROP_FPS); frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cap.release()
                if fps > 0 and frame_count > 0:
                    video_duration = frame_count / fps
                    shot_info = {"original_video_path":video_path,"shot_index_in_video":0,"start_time_sec":0.0,"end_time_sec":video_duration,"duration_sec":video_duration,"global_shot_id":global_shot_id_counter}
                    visual_features = extract_shot_visual_features(video_path, 0.0, video_duration)
                    shot_info.update(visual_features)
                    all_shots_metadata_list.append(shot_info)
                    global_shot_id_counter += 1
            except Exception as e: print(f"    ERROR processing full video duration for {video_path}: {e}. Skipping.")

    if not all_shots_metadata_list: report_progress(60, "No usable video shots could be extracted."); return False, None
    report_progress(60, "Video analysis complete.")
    with open(all_shots_metadata_file, "w") as f: json.dump(all_shots_metadata_list, f, indent=2, cls=NpEncoder)
    if PROFILE_STEPS: print(f"Step 2 duration: {time.time() - step_start_time:.2f}s")


    # --- Step 2.5: Determine Theme (with new Visual Analysis) ---
    report_progress(61, "Determining creative theme...")
    final_theme_for_edit_plan = DEFAULT_REEL_THEME_FALLBACK

    if user_theme_override and user_theme_override.strip().lower() not in ["", DEFAULT_REEL_THEME_PLACEHOLDER.lower()]:
        final_theme_for_edit_plan = user_theme_override
        report_progress(62, f"Using user-provided theme: '{final_theme_for_edit_plan}'.")
    else:
        report_progress(62, "Performing deep content analysis for theme suggestion...")
        audio_summary = {k: audio_data.get(k) for k in ["tempo", "duration", "simplified_energy_values_at_times"]}

        shots_to_describe = sorted(all_shots_metadata_list, key=lambda x: x.get('duration_sec', 0), reverse=True)[:4]
        
        visual_descriptions = []
        for shot in shots_to_describe: # <-- Correct loop variable is 'shot'
            desc = get_visual_content_description(
                shot["original_video_path"], # <-- Use 'shot' here
                shot["start_time_sec"],      # <-- and here
                shot["end_time_sec"]         # <-- and here
            )
            visual_descriptions.append(desc)
            time.sleep(1)

        video_summary = {
            "num_shots": len(all_shots_metadata_list),
            "avg_motion_score": np.mean([s.get('avg_motion_score',0) for s in all_shots_metadata_list] or [0]),
            "avg_brightness": np.mean([s.get('avg_brightness',0) for s in all_shots_metadata_list] or [0]),
            "visual_content": list(set(visual_descriptions))
        }
        ai_suggested_themes_list = suggest_reel_themes(audio_summary, video_summary, num_suggestions=1)

        if ai_suggested_themes_list:
            final_theme_for_edit_plan = ai_suggested_themes_list[0]
            report_progress(65, f"AI suggested theme: '{final_theme_for_edit_plan}'.")
        else:
            report_progress(65, "AI theme suggestion failed. Using fallback theme.")


    # --- Step 3: Generate Edit Plan ---
    report_progress(66, f"Generating AI edit plan with theme: '{final_theme_for_edit_plan}'...")
    ai_edit_plan = generate_ai_edit_plan(
        audio_data, all_shots_metadata_list, min_reel_duration, max_reel_duration,
        final_theme_for_edit_plan,
        audio_segment_start_sec=audio_segment_start_sec
    )
    if not ai_edit_plan or not ai_edit_plan.get("edit_plan"):
        report_progress(80,"AI failed to generate a valid edit plan."); return False,None
    report_progress(85, "AI edit plan generated.")


    # --- Step 4: Assemble Reel ---
    report_progress(86, "Starting reel assembly...")
    all_shots_dict = {s['global_shot_id']: s for s in all_shots_metadata_list}
    success_assembly, actual_output_path = assemble_reel(
        ai_edit_plan, all_shots_dict, audio_data, final_reel_file_output_path
    )
    if not success_assembly:
        report_progress(98,"Reel assembly failed."); return False, None
    report_progress(99, "Reel assembled successfully.")

    return True, actual_output_path

if __name__ == "__main__":
    print(">>> Running main_editor.py in standalone test mode <<<")
    TEST_AUDIO_PATH = "input_audio/test_audio.mp3" 
    TEST_VIDEO_PATHS = ["input_videos/test_video.mp4"]
    TEST_AUDIO_START = 15.0
    TEST_AUDIO_END = 30.0

    if os.path.exists(TEST_AUDIO_PATH) and all(os.path.exists(p) for p in TEST_VIDEO_PATHS):
        success, final_path = create_ai_edited_reel(
            user_theme_override="AI will suggest a theme",
            audio_file_full_path=TEST_AUDIO_PATH,
            video_file_full_paths_list=TEST_VIDEO_PATHS,
            output_base_dir_for_job="output/test_run",
            audio_segment_start_sec=TEST_AUDIO_START,
            audio_segment_end_sec=TEST_AUDIO_END,
            job_id=f"test_{int(time.time())}"
        )
        if success: print(f"✅ SUCCESS! Reel at: {final_path}")
        else: print("❌ FAILED.")
    else:
        print("❌ Test aborted. Please check that test files exist.")
