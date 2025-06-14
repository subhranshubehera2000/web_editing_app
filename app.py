# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS 
import os
import threading 
import time
import json
import traceback 
import shutil 
import tempfile 
import boto3 
from botocore.exceptions import ClientError
from botocore.client import Config
import numpy as np

from tasks import celery_app, process_video_task 
from celery.result import AsyncResult 

from main_editor import ( 
    DEFAULT_REEL_MIN_DURATION_SEC, 
    DEFAULT_REEL_MAX_DURATION_SEC,
    DEFAULT_REEL_THEME_PLACEHOLDER,
)

app = Flask(__name__)
CORS(app, origins=["http://subhranshupage.s3-website.ap-south-1.amazonaws.com", "http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:5000"], 
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "Authorization", "X-Requested-With", "X-Amz-Content-Sha256", "X-Amz-Date", "X-Amz-Security-Token"], 
     expose_headers=["ETag"], supports_credentials=False, max_age=86400 )

S3_INPUT_BUCKET = "ai-edit-input-bucket"  # REPLACE
S3_OUTPUT_BUCKET_APP = "ai-edit-output-bucket" # Worker also needs output bucket name config
S3_REGION = "ap-south-1" 

s3_app_client = None 
try:
    s3_app_client = boto3.client('s3', region_name=S3_REGION, config=Config(signature_version='s3v4'))
    print(f"App S3 client for presigned URLs initialized for region {S3_REGION}.")
except Exception as e_s3_init: print(f"CRITICAL: App S3 client init failed: {e_s3_init}.")

job_status_store = {} 
current_display_job_id_counter = 0 
job_lock = threading.Lock() 

def _update_app_job_status(display_job_id, status, progress, message, download_url=None, celery_task_id_to_associate=None):
    global job_status_store 
    progress = max(0, min(100, int(progress)))
    with job_lock:
        current_job_data = job_status_store.get(display_job_id, {"job_id": display_job_id})
        current_job_data.update({ "status": status, "progress": progress, "message": message })
        if download_url is not None: current_job_data["download_url"] = download_url # Handle null download_url explicitly
        if celery_task_id_to_associate and "celery_task_id" not in current_job_data: current_job_data["celery_task_id"] = celery_task_id_to_associate
        job_status_store[display_job_id] = current_job_data
    print(f"[APP UI STATUS] DisplayJobID: {display_job_id} (CeleryID: {current_job_data.get('celery_task_id','N/A')}) - {status} - {progress}% - {message}" + (f" - DL: {download_url if download_url is not None else 'N/A'}" ))

@app.route('/generate-upload-url', methods=['POST']) 
def generate_upload_url_route(): 
    data = request.json; filename = data.get('filename'); file_type = data.get('fileType', 'application/octet-stream') 
    if not filename: return jsonify({"error": "Filename required"}), 400
    if not s3_app_client: return jsonify({"error": "S3 client not active"}), 500
    s3_key = f"uploads/session_{int(time.time())}_{np.random.randint(100,999)}/{os.path.basename(filename)}"
    try:
        presigned_url = s3_app_client.generate_presigned_url('put_object', Params={'Bucket':S3_INPUT_BUCKET,'Key':s3_key},ExpiresIn=3600)
        return jsonify({'uploadUrl': presigned_url, 's3Key': s3_key}) 
    except ClientError as e: print(f"Err gen presigned URL:{e}"); return jsonify({"error":"S3 client err"}),500
    except Exception as e_g: print(f"Unexp err gen URL:{e_g}");traceback.print_exc(); return jsonify({"error": "Server err gen URL"}),500

@app.route('/start-edit', methods=['POST'])
def start_edit_job_route(): 
    global current_display_job_id_counter 
    display_job_id_for_this_request = 0 
    try: 
        # No explicit active job check here anymore; Celery queue handles concurrency.
        # Rate limiting would be a separate concern if needed at API gateway or Flask level.
        data = request.json; 
        if not data: return jsonify({"error": "Missing JSON"}), 400
        
        theme_from_ui_raw = data.get('theme', "").strip(); actual_theme_for_processing = None 
        if not theme_from_ui_raw or theme_from_ui_raw.lower() == DEFAULT_REEL_THEME_PLACEHOLDER.lower(): actual_theme_for_processing = None 
        else: actual_theme_for_processing = theme_from_ui_raw
        
        min_duration = int(data.get('min_duration', DEFAULT_REEL_MIN_DURATION_SEC))
        max_duration = int(data.get('max_duration', DEFAULT_REEL_MAX_DURATION_SEC))
        audio_s3_key = data.get('audio_s3_key'); video_s3_keys = data.get('video_s3_keys') 
        
        if not audio_s3_key: return jsonify({"error": "audio_s3_key req"}), 400
        if not video_s3_keys or not isinstance(video_s3_keys,list) or not video_s3_keys: return jsonify({"error":"video_s3_keys list req"}),400
        if not (3 <= len(video_s3_keys) <= 6): return jsonify({"error": "Need 3-6 videos."}), 400
        
        with job_lock: current_display_job_id_counter += 1; display_job_id_for_this_request = current_display_job_id_counter
        
        _update_app_job_status(display_job_id_for_this_request, "queued", 1, "Validating inputs & preparing task...")

        task_args = [ display_job_id_for_this_request, actual_theme_for_processing, min_duration, max_duration, audio_s3_key, video_s3_keys ]
        
        print(f"Job {display_job_id_for_this_request}: Dispatching Celery task process_video_task with S3 keys.")
        celery_task_obj = process_video_task.apply_async(args=task_args)
        print(f"Job {display_job_id_for_this_request}: Celery task ID {celery_task_obj.id} dispatched.")

        _update_app_job_status(display_job_id_for_this_request, "queued_celery", 2, 
                                 f"Job {display_job_id_for_this_request} sent to processing queue.", 
                                 celery_task_id_to_associate=celery_task_obj.id)
        
        return jsonify({"message":"Video editing task submitted to queue.", "job_id":display_job_id_for_this_request, "celery_task_id": celery_task_obj.id}),202
    
    except Exception as e: 
        error_msg=f"Error in /start-edit dispatch: {str(e)}"; print(error_msg); traceback.print_exc();
        if display_job_id_for_this_request > 0: 
             _update_app_job_status(display_job_id_for_this_request, "error", 0, f"Failed to start job: {str(e)}")
        return jsonify({"error":error_msg, "detail": "Failed to initiate job processing."}),500

@app.route('/job-status', methods=['GET']) 
def get_job_status_route(): 
    global job_status_store 
    display_job_id_query = request.args.get('job_id',type=int) 
    if display_job_id_query is None: return jsonify({"error": "job_id query param required"}), 400

    with job_lock: stored_job_entry = job_status_store.get(display_job_id_query)
    
    if not stored_job_entry or 'celery_task_id' not in stored_job_entry:
        return jsonify({"job_id":display_job_id_query, "status":"NOT_FOUND","message":f"Job {display_job_id_query} not found or not Celery task."}), 404

    celery_task_id_to_check = stored_job_entry['celery_task_id']
    task = AsyncResult(celery_task_id_to_check, app=celery_app)
    
    current_ui_status = stored_job_entry.copy(); current_ui_status["celery_state_raw"] = task.state 

    # Map Celery states and task.info to UI display
    # Base progress for different phases of the overall job handled by the app
    DOWNLOAD_COMPLETE_PERCENT = 15  # After app.py has downloaded inputs (no longer used here as worker downloads)
    WORKER_PROCESSING_START_PERCENT = 2 # After Celery task is queued by app.py
    WORKER_MAIN_EDITOR_PHASE_START = 15 # UI % when main_editor begins
    WORKER_MAIN_EDITOR_PHASE_END = 95   # UI % when main_editor finishes
    WORKER_S3_UPLOAD_START_PERCENT = 96 # UI % when worker starts uploading final reel

    if task.state == 'PENDING':
        current_ui_status["status"] = "queued_celery"
        current_ui_status["message"] = stored_job_entry.get("message", "Task waiting in Celery queue.")
        current_ui_status["progress"] = max(current_ui_status.get("progress", 0), WORKER_PROCESSING_START_PERCENT -1 ) # Progress for queueing
    elif task.state == 'STARTED':
        current_ui_status["status"] = "processing"
        current_ui_status["message"] = "Celery worker started processing files..."
        current_ui_status["progress"] = max(current_ui_status.get("progress", 0), WORKER_PROCESSING_START_PERCENT) 
    elif task.state == 'PROGRESS': 
        current_ui_status["status"] = "processing" 
        if isinstance(task.info, dict): 
            # task.info['progress_percent'] is the 0-100 from worker's main_editor_callback
            main_editor_internal_percent = task.info.get('progress_percent', 0)
            editing_phase_span_on_ui = WORKER_MAIN_EDITOR_PHASE_END - WORKER_MAIN_EDITOR_PHASE_START
            app_level_progress = WORKER_MAIN_EDITOR_PHASE_START + int(main_editor_internal_percent * (editing_phase_span_on_ui / 100.0))
            current_ui_status["progress"] = app_level_progress
            current_ui_status["message"] = task.info.get('message', "Processing video edits...")
    elif task.state == 'SUCCESS':
        result = task.result 
        if isinstance(result, dict) and result.get("status") == "SUCCESS": 
            current_ui_status["status"] = "completed"
            current_ui_status["progress"] = 100
            current_ui_status["message"] = result.get("message", "Reel generation successful!")
            current_ui_status["download_url"] = result.get("download_url") 
        else: 
            current_ui_status["status"] = "error_worker_result"; current_ui_status["progress"]=99
            current_ui_status["message"] = f"Task succeeded but worker result issue: {str(result)[:150]}"
    elif task.state == 'FAILURE':
        current_ui_status["status"] = "error_celery_task"; current_ui_status["progress"]=0
        # Try to get the custom user message or is_throttling from task.result (which is our error_payload from tasks.py)
        user_friendly_error_message = "A processing error occurred in the background worker."
        if isinstance(task.result, dict): # Celery often puts the return value of task here on failure if task didn't re-raise
            if task.result.get("is_throttling"):
                user_friendly_error_message = "AI model services are currently under high demand. Please try again in a few minutes. You could also try again with a user-defined theme, or simplify your request."
            elif task.result.get("message_for_user"):
                user_friendly_error_message = task.result.get("message_for_user")
            elif task.result.get("error_message"):
                 user_friendly_error_message = f"Worker Error: {task.result.get('error_type', 'Unknown')} - {task.result.get('error_message', 'Details unavailable')[:100]}"
        elif isinstance(task.info, Exception): # Celery might put the Exception object in task.info
            if isinstance(task.info, ClientError) and task.info.response.get('Error', {}).get('Code') == 'ThrottlingException':
                 user_friendly_error_message = "AI model services are currently under high demand. Please try again in a few minutes (Throttling)."
            else:
                user_friendly_error_message = f"Task Exception: {str(task.info)[:150]}"
        elif task.info: # Fallback to task.info if task.result isn't our dict
            user_friendly_error_message = f"Task Info: {str(task.info)[:150]}"
        current_ui_status["message"] = user_friendly_error_message
    
    # Update job_status_store with the most recent interpretation
    if job_status_store.get(display_job_id_query) != current_ui_status :
        _update_app_job_status(display_job_id_query, current_ui_status["status"], current_ui_status["progress"], 
                              current_ui_status["message"], current_ui_status.get("download_url"), 
                              celery_task_id_to_associate=celery_task_id_to_check)

    return jsonify(current_ui_status)

if __name__ == '__main__':
    print(f"Flask app (Celery DECOUPLED ARCH) starting. S3 Input: {S3_INPUT_BUCKET}")
    if s3_app_client is None: print("CRITICAL: App S3 client failed init.")
    app.run(debug=False, host='0.0.0.0', port=5000, threaded=True) 
