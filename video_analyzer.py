# video_analyzer.py
from scenedetect import open_video, SceneManager, ContentDetector
from scenedetect.frame_timecode import FrameTimecode
import cv2
import numpy as np
import os
import traceback
import json
import base64
import boto3

# --- New: Bedrock client for visual analysis ---
AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
SUGGESTION_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0" 
try:
    bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)
except Exception as e:
    print(f"CRITICAL [video_analyzer]: Could not initialize boto3 client: {e}")
    bedrock_runtime = None

def detect_shots(video_path, content_detector_threshold=27.0):
    # This function is unchanged and correct
    shots_data = []
    try:
        video_stream = open_video(video_path)
        scene_manager = SceneManager()
        scene_manager.add_detector(ContentDetector(threshold=content_detector_threshold))
        scene_manager.detect_scenes(video=video_stream, show_progress=False)
        scene_list = scene_manager.get_scene_list()
        
        if not scene_list and video_stream.duration.get_seconds() > 0:
            start_timecode = FrameTimecode(timecode=0, fps=video_stream.frame_rate)
            scene_list = [(start_timecode, video_stream.duration)]

        for i, (start_tc, end_tc) in enumerate(scene_list):
            start_seconds, end_seconds = start_tc.get_seconds(), end_tc.get_seconds()
            duration_seconds = end_seconds - start_seconds
            if duration_seconds < 0.01: continue
            shots_data.append({
                "original_video_path": video_path,
                "shot_index_in_video": i,
                "start_time_sec": start_seconds,
                "end_time_sec": end_seconds,
                "duration_sec": duration_seconds,
            })
    except Exception as e:
        print(f"ERROR detecting shots in {video_path}: {e}")
        traceback.print_exc()
    return shots_data

def extract_shot_visual_features(video_path, start_sec, end_sec):
    # This function is unchanged and correct
    features = {"avg_brightness": 0.0, "avg_color_rgb": [0,0,0], "avg_motion_score": 0.0}
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return features
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        start_frame_idx = int(start_sec * fps); end_frame_idx = max(start_frame_idx, int(end_sec * fps))
        num_shot_frames = max(1, end_frame_idx - start_frame_idx + 1)
        sample_count = min(15, num_shot_frames)
        indices_to_sample = np.unique(np.linspace(start_frame_idx, end_frame_idx, sample_count, dtype=int))
        brightness_vals, color_bgr_vals, motion_vals, prev_gray = [], [], [], None
        for frame_idx in indices_to_sample:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if not ret: continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness_vals.append(np.mean(gray))
            color_bgr_vals.append(np.mean(frame, axis=(0, 1)))
            if prev_gray is not None: motion_vals.append(np.mean(cv2.absdiff(gray, prev_gray)))
            prev_gray = gray.copy()
        if brightness_vals: features["avg_brightness"] = float(np.mean(brightness_vals))
        if color_bgr_vals: avg_bgr = np.mean(color_bgr_vals, axis=0); features["avg_color_rgb"] = [int(round(c)) for c in avg_bgr[[2,1,0]]]
        if motion_vals: features["avg_motion_score"] = float(np.mean(motion_vals))
    except Exception as e: print(f"ERROR extracting features from {video_path}: {e}")
    finally:
        if cap: cap.release()
    return features


# <<< --- NEW FUNCTION FOR VISUAL CONTENT ANALYSIS --- >>>
def get_visual_content_description(video_path, shot_start_sec, shot_end_sec):
    """
    Extracts a representative frame, sends it to a multimodal AI,
    and returns a textual description of the visual content.
    """
    default_description = "A general video clip."
    if not bedrock_runtime:
        print("    WARNING: Bedrock client not available for visual description.")
        return default_description

    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened(): return default_description

        mid_point_sec = shot_start_sec + (shot_end_sec - shot_start_sec) / 2
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_idx = int(mid_point_sec * fps)
        
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        
        if not ret: return default_description

        # Resize for faster processing and lower cost, maintaining aspect ratio
        max_dim = 512
        h, w = frame.shape[:2]
        if h > w:
            new_h = max_dim
            new_w = int(w * (max_dim / h))
        else:
            new_w = max_dim
            new_h = int(h * (max_dim / w))
        resized_frame = cv2.resize(frame, (new_w, new_h))

        success, encoded_image = cv2.imencode('.jpg', resized_frame)
        if not success: return default_description
            
        base64_image = base64.b64encode(encoded_image).decode('utf-8')

        prompt = "In 5-10 words, describe the primary subject and environment in this image. Focus on concrete nouns and settings. Example: 'A person hiking on a mountain trail.' or 'City skyscrapers at night.'"
        
        request_body = {
            "anthropic_version": "bedrock-2023-05-31", "max_tokens": 75, "temperature": 0.5,
            "messages": [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": base64_image}},
                {"type": "text", "text": prompt}
            ]}]
        }
        
        response = bedrock_runtime.invoke_model(body=json.dumps(request_body), modelId=SUGGESTION_MODEL_ID)
        response_body = json.loads(response.get("body").read())
        description = response_body.get("content", [{}])[0].get("text", default_description).strip()
        print(f"    Visual Description: '{description}'")
        return description

    except Exception as e:
        print(f"    ERROR getting visual description for {os.path.basename(video_path)}: {e}")
        return default_description
    finally:
        if cap: cap.release()
