# video_analyzer.py
from scenedetect import open_video, SceneManager, ContentDetector
from scenedetect.frame_timecode import FrameTimecode # Import FrameTimecode
import cv2
import numpy as np
import os
import traceback
import json # For NpEncoder test in main

def detect_shots(video_path, content_detector_threshold=27.0):
    shots_data = []
    video_stream = None
    try:
        print(f"Detecting shots in video: {video_path} (Threshold: {content_detector_threshold})")
        video_stream = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=content_detector_threshold))
        
        scene_manager.detect_scenes(video=video_stream, show_progress=False)
        scene_list = scene_manager.get_scene_list()
        print(f"  Detected {len(scene_list)} shots initially in {os.path.basename(video_path)}.")
        
        if not scene_list and video_stream.duration.get_seconds() > 0:
            print("  No specific scenes detected by ContentDetector. Treating entire video as a single shot.")
            start_timecode_obj = None
            current_fps = video_stream.frame_rate
            
            if isinstance(current_fps, (float, int)):
                start_timecode_obj = FrameTimecode(timecode=0, fps=float(current_fps))
            elif hasattr(current_fps, 'fps'): 
                start_timecode_obj = FrameTimecode(timecode=0, fps=current_fps.fps)
            else: 
                print(f"Warning: video_stream.frame_rate is an unexpected type ({type(current_fps)}). Defaulting to 30.0 fps for start timecode.")
                start_timecode_obj = FrameTimecode(timecode=0, fps=30.0)
            scene_list = [(start_timecode_obj, video_stream.duration)]

        for i, (start_tc, end_tc) in enumerate(scene_list):
            if not isinstance(start_tc, FrameTimecode) or not isinstance(end_tc, FrameTimecode):
                print(f"  Warning: Invalid timecode types for shot {i} in {video_path}. Skipping. Start: {type(start_tc)}, End: {type(end_tc)}")
                continue
            start_seconds = start_tc.get_seconds()
            end_seconds = end_tc.get_seconds()
            duration_seconds = end_seconds - start_seconds
            
            if duration_seconds < 0.01: 
                continue

            shots_data.append({
                "original_video_path": video_path,
                "shot_index_in_video": i,
                "start_time_sec": start_seconds,
                "end_time_sec": end_seconds,
                "duration_sec": duration_seconds,
            })
    except Exception as e:
        print(f"ERROR detecting shots in {video_path}: {e}")
        print("Full Traceback for shot detection error:")
        traceback.print_exc()
    return shots_data

def extract_shot_visual_features(video_path, start_sec, end_sec):
    features = {
        "avg_brightness": 0.0, "avg_color_rgb": [0, 0, 0], "avg_motion_score": 0.0,
    }
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): print(f"Error: CV Could not open video {video_path}"); return features
        fps = cap.get(cv2.CAP_PROP_FPS); fps = 30.0 if fps <= 0 or fps is None else fps # Ensure fps is positive
        start_frame_idx = int(start_sec * fps); end_frame_idx = max(start_frame_idx, int(end_sec * fps))
        num_shot_frames = max(1, end_frame_idx - start_frame_idx + 1)
        sample_count = min(15, num_shot_frames)
        
        indices_to_sample = np.array([start_frame_idx]) if num_shot_frames == 1 else \
                            np.unique(np.linspace(start_frame_idx, end_frame_idx, sample_count, dtype=int))

        brightness_vals, color_bgr_vals, motion_vals = [], [], []
        prev_gray = None
        frames_read_successfully = 0
        for frame_idx in indices_to_sample:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret: 
                # print(f"Warning: Could not read frame {frame_idx} in {video_path}") # Optional: too verbose usually
                continue
            frames_read_successfully +=1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_vals.append(np.mean(gray))
            color_bgr_vals.append(np.mean(frame, axis=(0, 1)))
            if prev_gray is not None: motion_vals.append(np.mean(cv2.absdiff(gray, prev_gray)))
            prev_gray = gray.copy()

        if not frames_read_successfully :
            print(f"Warning: No frames could be read for segment {start_sec:.2f}-{end_sec:.2f} in {video_path}")
            # Features will remain default (0s)

        if brightness_vals: features["avg_brightness"] = float(np.mean(brightness_vals))
        if color_bgr_vals: avg_bgr = np.mean(color_bgr_vals, axis=0); features["avg_color_rgb"] = [int(round(c)) for c in avg_bgr[[2,1,0]]] # BGR to RGB
        if motion_vals: features["avg_motion_score"] = float(np.mean(motion_vals))
        elif frames_read_successfully > 1 and not motion_vals : # More than one frame but no motion calculated (should be rare with this logic)
            features["avg_motion_score"] = 0.0 # Still يعتبر no motion
        # If only 1 frame read, motion_vals will be empty, so avg_motion_score correctly remains 0.0

    except Exception as e:
        print(f"ERROR extracting features from {video_path} ({start_sec:.2f}s-{end_sec:.2f}s): {e}"); traceback.print_exc()
    finally:
        if cap: cap.release()
    return features

if __name__ == '__main__':
    if not os.path.exists("output"): os.makedirs("output", exist_ok=True)
    input_videos_dir = "input_videos"
    if not os.path.exists(input_videos_dir): os.makedirs(input_videos_dir, exist_ok=True)

    dummy_video_file_path = os.path.join(input_videos_dir, "dummy_test_video.mp4")
    if not os.path.exists(dummy_video_file_path):
        try:
            print(f"Creating dummy video file: {dummy_video_file_path}")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v'); out_dummy = cv2.VideoWriter(dummy_video_file_path, fourcc, 30.0, (640, 480))
            for i in range(150): # 5 seconds
                frame_dummy = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(frame_dummy, f'Frame {i}', (50, 50 + (i%10)*10 ), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, (i*5)%255), 2)
                if i % 75 < 35 : cv2.circle(frame_dummy, (100 + i*2, 240), 30, (0, (i*10)%255, 0), -1)
                else: cv2.rectangle(frame_dummy, (300, 200 - i//3), (400, 280 + i//3), (0,0,(i*7)%255), 5)
                out_dummy.write(frame_dummy)
            out_dummy.release(); print("Dummy video created.")
        except Exception as ex_vid: print(f"Could not create dummy video (is opencv-python installed?): {ex_vid}. Add a video to 'input_videos'.")

    test_video_files = [f for f in os.listdir(input_videos_dir) if f.lower().endswith(('.mp4', '.mov'))]
    if test_video_files:
        test_video_path = os.path.join(input_videos_dir, test_video_files[0])
        print(f"\n--- Testing video_analyzer.py on: {test_video_path} ---")
        detected_shots_list = detect_shots(test_video_path)
        test_all_shots_info = []
        if detected_shots_list:
            print(f"\nDetected {len(detected_shots_list)} shots (features for first 3 shown):")
            for i, shot_info in enumerate(detected_shots_list):
                features = extract_shot_visual_features(shot_info["original_video_path"], shot_info["start_time_sec"], shot_info["end_time_sec"])
                if i < 3: print(f"Shot {i}: Start={shot_info['start_time_sec']:.2f}s, End={shot_info['end_time_sec']:.2f}s, Dur={shot_info['duration_sec']:.2f}s, Feat: {features}")
                shot_info_full = shot_info.copy(); shot_info_full.update(features); test_all_shots_info.append(shot_info_full)
            try:
                class NpEncoder(json.JSONEncoder): # For standalone test
                    def default(self, obj):
                        if isinstance(obj, np.integer): return int(obj)
                        if isinstance(obj, np.floating): return float(obj)
                        if isinstance(obj, np.ndarray): return obj.tolist()
                        if isinstance(obj, np.bool_): return bool(obj)
                        return super(NpEncoder, self).default(obj)
                with open("output/test_video_analysis_shots.json", "w") as f_json_vid:
                    json.dump(test_all_shots_info, f_json_vid, indent=2, cls=NpEncoder)
                print("\nTest video analysis saved to output/test_video_analysis_shots.json")
            except Exception as e_json_vid: print(f"Error saving test video analysis JSON: {e_json_vid}")
        else: print("No shots detected in the test video.")
    else: print(f"No video files in '{input_videos_dir}/' for testing. Please add one.")
