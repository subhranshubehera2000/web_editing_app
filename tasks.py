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

from main_editor import create_ai_edited_reel, NpEncoder 

S3_INPUT_BUCKET_WORKER = os.environ.get("S3_INPUT_BUCKET", "ai-edit-input-bucket") # REPLACE
S3_OUTPUT_BUCKET_WORKER = os.environ.get("S3_OUTPUT_BUCKET", "ai-edit-input-bucket") # REPLACE
S3_REGION_WORKER = os.environ.get("S3_REGION", "ap-south-1") # REPLACE

s3_worker_client = None
try:
    s3_worker_client = boto3.client('s3', region_name=S3_REGION_WORKER, config=Config(signature_version='s3v4'))
    print(f"[CeleryWorker] S3 client initialized for worker in region {S3_REGION_WORKER}.")
except Exception as e_s3_worker_init:
    print(f"[CeleryWorker] CRITICAL: Worker S3 client init failed: {e_s3_worker_init}")

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
celery_app = Celery('video_tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery_app.conf.update(task_serializer='json', result_serializer='json', accept_content=['json'], task_track_started=True)

class ProgressTask(Task):
    def update_task_progress(self, progress_percent_in_phase, message_detail, status_override=None):
        current_celery_state = status_override if status_override else 'PROGRESS'
        progress_percent_in_phase = max(0, min(100, int(progress_percent_in_phase)))
        meta_for_celery = {'progress_percent': progress_percent_in_phase, 'message': message_detail,'status_detail': 'PROGRESS_MAIN_EDITOR'}
        self.update_state(state='PROGRESS', meta=meta_for_celery)

def get_video_info(video_path):
    try:
        cmd = ["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,avg_frame_rate,r_frame_rate","-of","json",video_path]
        result = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=30) 
        data = json.loads(result.stdout)
        if data.get("streams") and len(data["streams"]) > 0:
            stream = data["streams"][0]
            width = stream.get("width"); height = stream.get("height")
            fr_str = stream.get("avg_frame_rate", stream.get("r_frame_rate", "30/1"))
            if "/" in fr_str: num, den = map(float, fr_str.split('/')); fps = num / den if den != 0 else 30.0
            else: fps = float(fr_str)
            if width and height and fps: return int(width), int(height), float(fps)
    except subprocess.TimeoutExpired: print(f"[FFprobe TIMEOUT] for {video_path}")
    except Exception as e: print(f"[FFprobe ERROR] for {video_path}: {e}")
    return None, None, None

@celery_app.task(bind=True, base=ProgressTask, name='tasks.process_video_task',
                  autoretry_for=(Exception,), retry_kwargs={'max_retries': 2}, 
                  retry_backoff=True, retry_backoff_max=180, retry_jitter=True) 
def process_video_task(self, display_job_id, user_theme_override, user_min_duration, user_max_duration,
                       audio_s3_key, video_s3_keys_list): 
    task_id = self.request.id 
    print(f"[CELERY WORKER Task {task_id}, Job {display_job_id}] Received. Theme: '{user_theme_override or 'AI Suggest'}'.")
    worker_job_temp_dir = tempfile.mkdtemp(prefix=f"celery_job_{display_job_id}_{task_id}_")
    worker_main_editor_output_subdir = os.path.join(worker_job_temp_dir, "output_from_main_editor")
    os.makedirs(worker_main_editor_output_subdir, exist_ok=True)
    print(f"[CeleryWorker Task {task_id}] Temp dir: {worker_job_temp_dir}")
    local_input_audio_path = None; processed_local_video_paths = []; final_reel_local_path = None
    def main_editor_cb(p,m): self.update_task_progress(p,m)
    try:
        if not s3_worker_client: raise Exception("S3 worker client not initialized.")
        self.update_task_progress(2, "Downloading audio by worker...")
        audio_fn_s3 = os.path.basename(audio_s3_key)
        local_input_audio_path = os.path.join(worker_job_temp_dir, audio_fn_s3)
        s3_worker_client.download_file(S3_INPUT_BUCKET_WORKER, audio_s3_key, local_input_audio_path)
        self.update_task_progress(5, f"Audio '{audio_fn_s3}' downloaded. Pre-processing videos...")
        vid_proc_prog_share = 20; base_vid_prog = 5 
        for i, vid_s3_key in enumerate(video_s3_keys_list):
            cur_item_prog_start = base_vid_prog + int(((i)/len(video_s3_keys_list))*vid_proc_prog_share)
            self.update_task_progress(cur_item_prog_start, f"Downloading video {i+1}/{len(video_s3_keys_list)}...")
            vid_fn_s3 = os.path.basename(vid_s3_key)
            orig_local_vid_path = os.path.join(worker_job_temp_dir, f"original_{vid_fn_s3}")
            s3_worker_client.download_file(S3_INPUT_BUCKET_WORKER, vid_s3_key, orig_local_vid_path)
            self.update_task_progress(cur_item_prog_start + 1, f"Analyzing video {i+1} metadata...")
            width, height, fps = get_video_info(orig_local_vid_path)
            path_to_use = orig_local_vid_path # Default to original if no transcoding needed/fails
            needs_tc = False; vf_opts = []
            TARGET_H=1080; TARGET_W=1080; TARGET_FPS=30.0 
            if width and height and fps:
                print(f"  Vid {vid_fn_s3}: {width}x{height} @{fps:.2f}fps")
                scaled = False
                if width > height: # Landscape or Square
                    if height > TARGET_H: vf_opts.append(f"scale=-2:{TARGET_H}"); scaled=True
                else: # Portrait
                    if width > TARGET_W: vf_opts.append(f"scale={TARGET_W}:-2"); scaled=True
                if scaled: needs_tc=True; print(f"    Will downscale {vid_fn_s3}.")
                if fps > TARGET_FPS + 0.5:
                    vf_opts.append(f"fps={TARGET_FPS}"); needs_tc=True; print(f"    Will conform {vid_fn_s3} to {TARGET_FPS}FPS.")
            else: print(f"  Warn: No video info for {vid_fn_s3}, using original.")
            
            if needs_tc:
                proc_vid_path=os.path.join(worker_job_temp_dir,f"proc_{vid_fn_s3}")
                cmd_tc=["ffmpeg","-y","-i",orig_local_vid_path,"-vf",",".join(vf_opts),"-c:v","libx264","-preset","medium","-crf","22","-c:a","aac","-b:a","128k",proc_vid_path]
                print(f"    Transcoding {vid_fn_s3} with vf: '{','.join(vf_opts)}' -> {proc_vid_path}")
                try:
                    subprocess.run(cmd_tc,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180) 
                    path_to_use=proc_vid_path # If subprocess successful, use the processed path
                    print(f"    Transcoding successful for {vid_fn_s3}")
                    if orig_local_vid_path != path_to_use and os.path.exists(orig_local_vid_path):
                         try: os.remove(orig_local_vid_path)
                         except OSError as e_rm: print(f"    Warn: Could not remove original downloaded {orig_local_vid_path}: {e_rm}")
                except subprocess.TimeoutExpired:
                    print(f"    TIMEOUT transcoding {vid_fn_s3}. Using original path: {orig_local_vid_path}.")
                    # path_to_use remains orig_local_vid_path
                except subprocess.CalledProcessError as e_tc:
                    print(f"    ERROR transcoding {vid_fn_s3}: {e_tc.stderr.decode() if e_tc.stderr else e_tc}")
                    print(f"    Using original path {orig_local_vid_path} despite transcoding error.")
                    # path_to_use remains orig_local_vid_path
            
            processed_local_video_paths.append(path_to_use)
            cur_item_prog_end=base_vid_prog+int(((i+1)/len(video_s3_keys_list))*vid_proc_prog_share)
            self.update_task_progress(cur_item_prog_end, f"Video {i+1} pre-processed.")
        
        self.update_task_progress(base_vid_prog+vid_proc_prog_share+1, "Inputs ready. Starting main AI edit.")
        success,final_reel_lr=create_ai_edited_reel(user_theme_override,user_min_duration,user_max_duration,
            local_input_audio_path,processed_local_video_paths,worker_main_editor_output_subdir,
            f"{display_job_id}_{task_id}",main_editor_cb)
        final_reel_local_path = final_reel_lr # Capture for S3 upload in success case
        
        if success and final_reel_local_path and os.path.exists(final_reel_local_path):
            self.update_task_progress(96, "Reel assembled. Worker uploading to S3 Output...")
            final_reel_bn=os.path.basename(final_reel_local_path);out_s3_k=f"reels/job_{display_job_id}_task_{task_id}/{final_reel_bn}"
            s3_worker_client.upload_file(final_reel_local_path,S3_OUTPUT_BUCKET_WORKER,out_s3_k,ExtraArgs={'ContentType':'video/mp4'})
            self.update_task_progress(99, "Final reel uploaded to S3 by worker.")
            dl_url=s3_worker_client.generate_presigned_url('get_object',Params={'Bucket':S3_OUTPUT_BUCKET_WORKER,'Key':out_s3_k},ExpiresIn=3600*24)
            print(f"[CELERY WORKER Task {task_id}] SUCCESS. S3 Key: {out_s3_k}");return {"status":"SUCCESS","download_url":dl_url,"message":"Reel generated & uploaded!"}
        else:
            last_m="main_editor.py reported failure or output missing.";
            if isinstance(self.AsyncResult(task_id).info,dict):last_m=self.AsyncResult(task_id).info.get('message',last_m)
            print(f"[CELERY WORKER Task {task_id}] Main editor fail. Last msg: {last_m}");raise Exception(f"create_ai_edited_reel fail: {last_m}")
    except ClientError as ce:
        print(f"[CELERY WORKER Task {task_id}] Boto3 ClientError: {ce}"); tb_ce=traceback.format_exc(); print(tb_ce)
        is_th=ce.response.get('Error',{}).get('Code')=='ThrottlingException';umsg="AI model demand high. Try later." if is_th else f"Cloud service error ({ce.response.get('Error',{}).get('Code','Unknown')})."
        self.update_state(state='FAILURE',meta={'exc_type':type(ce).__name__,'exc_message':str(ce),'is_throttling':is_th,'message_for_user':umsg});raise 
    except Exception as e:
        print(f"[CELERY WORKER Task {task_id}] General EXCEPTION: {e}"); tb_e=traceback.format_exc(); print(tb_e)
        self.update_state(state='FAILURE',meta={'exc_type':type(e).__name__,'exc_message':str(e),'message_for_user':f"Unexpected error: {type(e).__name__}."});raise 
    finally:
        if os.path.exists(worker_job_temp_dir):
            print(f"[CeleryWorker Task {task_id}] Cleaning worker temp: {worker_job_temp_dir}")
            try: shutil.rmtree(worker_job_temp_dir,ignore_errors=True)
            except Exception as e_cln: print(f" Error cleaning worker temp {worker_job_temp_dir}: {e_cln}")
