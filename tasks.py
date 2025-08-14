# tasks.py
from celery import Celery, Task
import os
import time
import json 
import shutil
import tempfile
import traceback 
import numpy as np 
import boto3 
from botocore.exceptions import ClientError
from botocore.client import Config
import subprocess

from main_editor import create_ai_edited_reel

# --- S3 & Celery Configuration (no changes) ---
S3_INPUT_BUCKET_WORKER = os.environ.get("S3_INPUT_BUCKET", "ai-edit-input-bucket")
S3_OUTPUT_BUCKET_WORKER = os.environ.get("S3_OUTPUT_BUCKET", "ai-edit-output-bucket") 
S3_REGION_WORKER = os.environ.get("S3_REGION", "ap-south-1")

s3_worker_client = None
try:
    s3_worker_client = boto3.client('s3', region_name=S3_REGION_WORKER, config=Config(signature_version='s3v4'))
    print(f"[CeleryWorker] S3 client initialized for worker in region {S3_REGION_WORKER}.")
except Exception as e: print(f"[CeleryWorker] CRITICAL: Worker S3 client init failed: {e}")

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
celery_app = Celery('video_tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery_app.conf.update(task_serializer='json', result_serializer='json', accept_content=['json'], task_track_started=True)


class ProgressTask(Task):
    def update_task_progress(self, progress_percent_in_phase, message_detail):
        meta_for_celery = {'progress_percent': int(progress_percent_in_phase), 'message': message_detail,'status_detail': 'IN_PROGRESS'}
        self.update_state(state='PROGRESS', meta=meta_for_celery)

def get_video_info(video_path):
    # This helper function remains unchanged
    try:
        cmd = ["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,avg_frame_rate,r_frame_rate","-of","json",video_path]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30) 
        data = json.loads(result.stdout)
        if data.get("streams"):
            stream = data["streams"][0]
            width, height = stream.get("width"), stream.get("height")
            fr_str = stream.get("avg_frame_rate", stream.get("r_frame_rate", "30/1"))
            if "/" in fr_str: num, den = map(float, fr_str.split('/')); fps = num / den if den != 0 else 30.0
            else: fps = float(fr_str)
            if width and height and fps: return int(width), int(height), float(fps)
    except Exception as e: print(f"[FFprobe ERROR] for {video_path}: {e}")
    return None, None, None


# <<< --- MODIFIED TASK SIGNATURE --- >>>
@celery_app.task(bind=True, base=ProgressTask, name='tasks.process_video_task',
                  autoretry_for=(Exception,), retry_kwargs={'max_retries': 2}, 
                  retry_backoff=True, retry_backoff_max=180, retry_jitter=True) 
def process_video_task(self, display_job_id, user_theme_override,
                       audio_s3_key, video_s3_keys_list, 
                       audio_start_sec, audio_end_sec): 
    
    task_id = self.request.id 
    print(f"[CELERY WORKER Task {task_id}, Job {display_job_id}] Received.")
    worker_job_temp_dir = tempfile.mkdtemp(prefix=f"celery_job_{display_job_id}_")
    worker_main_editor_output_subdir = os.path.join(worker_job_temp_dir, "output_from_main_editor")
    os.makedirs(worker_main_editor_output_subdir, exist_ok=True)
    
    def main_editor_cb(p, m): self.update_task_progress(p, m)
    
    try:
        if not s3_worker_client: raise Exception("S3 worker client not initialized.")
        
        self.update_task_progress(2, "Downloading audio...")
        audio_fn_s3 = os.path.basename(audio_s3_key)
        local_input_audio_path = os.path.join(worker_job_temp_dir, audio_fn_s3)
        s3_worker_client.download_file(S3_INPUT_BUCKET_WORKER, audio_s3_key, local_input_audio_path)
        
        self.update_task_progress(5, "Downloading and pre-processing videos...")
        processed_local_video_paths = []
        # (This full video download/transcode block is correct and remains)
        for i, vid_s3_key in enumerate(video_s3_keys_list):
            self.update_task_progress(5 + int(((i)/len(video_s3_keys_list))*20), f"Processing video {i+1}...")
            vid_fn_s3 = os.path.basename(vid_s3_key)
            orig_local_vid_path = os.path.join(worker_job_temp_dir, f"original_{i}_{vid_fn_s3}")
            s3_worker_client.download_file(S3_INPUT_BUCKET_WORKER, vid_s3_key, orig_local_vid_path)
            # Placeholder for transcoding logic if you need it, otherwise this just uses the downloaded path
            path_to_use = orig_local_vid_path
            processed_local_video_paths.append(path_to_use)

        self.update_task_progress(25, "Inputs ready. Starting main AI edit process.")
        
        # <<< --- MODIFIED CALL TO create_ai_edited_reel --- >>>
        success, final_reel_local_path = create_ai_edited_reel(
            user_theme_override,
            local_input_audio_path,
            processed_local_video_paths,
            worker_main_editor_output_subdir,
            audio_start_sec,
            audio_end_sec,
            f"{display_job_id}_{task_id}",
            main_editor_cb
        )
        
        if success and final_reel_local_path and os.path.exists(final_reel_local_path):
            self.update_task_progress(96, "Uploading final reel to S3...")
            final_reel_bn = os.path.basename(final_reel_local_path)
            out_s3_key = f"reels/job_{display_job_id}/{final_reel_bn}"
            s3_worker_client.upload_file(final_reel_local_path, S3_OUTPUT_BUCKET_WORKER, out_s3_key, ExtraArgs={'ContentType':'video/mp4'})
            dl_url = s3_worker_client.generate_presigned_url('get_object', Params={'Bucket': S3_OUTPUT_BUCKET_WORKER, 'Key': out_s3_key}, ExpiresIn=3600*24)
            return {"status":"SUCCESS", "download_url": dl_url, "message":"Reel ready!"}
        else:
            raise Exception("main_editor.py reported failure or output was missing.")

    except Exception as e:
        tb_e=traceback.format_exc()
        print(f"[CELERY WORKER Task {task_id}] General EXCEPTION: {e}\n{tb_e}")
        self.update_state(state='FAILURE', meta={'exc_type':type(e).__name__, 'exc_message': str(e), 'message_for_user':f"An unexpected error occurred."});
        raise 
    finally:
        if os.path.exists(worker_job_temp_dir):
            shutil.rmtree(worker_job_temp_dir, ignore_errors=True)
