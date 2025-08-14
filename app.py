# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from botocore.exceptions import ClientError
import os
import uuid
import tempfile
import shutil
import traceback

from audio_analyzer import find_best_segments
from bedrock_director import suggest_audio_segment
from tasks import process_video_task

app = Flask(__name__)

# =====================================================================
# <<< --- THIS IS THE SINGLE, CRITICAL FIX --- >>>
# This new configuration is more explicit and should resolve the CORS issue.
CORS(app, resources={r"/*": {"origins": "*"}})
# =====================================================================


# --- S3 Configuration ---
S3_INPUT_BUCKET = os.environ.get("S3_INPUT_BUCKET", "ai-edit-input-bucket")
S3_REGION = os.environ.get("S3_REGION", "ap-south-1")

s3_client = None
try:
    s3_client = boto3.client('s3', region_name=S3_REGION, config=boto3.session.Config(signature_version='s3v4'))
    print(f"[FlaskAPI] S3 client initialized for API in region {S3_REGION}.")
except Exception as e:
    print(f"[FlaskAPI] CRITICAL: API S3 client initialization failed: {e}")

# ==============================================================================
# API ROUTES
# ==============================================================================

@app.route('/generate-upload-url', methods=['POST'])
def generate_upload_url():
    """
    Generates a pre-signed URL for the browser to directly upload a file to S3.
    """
    if not s3_client:
        return jsonify({"error": "S3 client not configured"}), 500

    data = request.json
    filename = data.get('filename')
    file_type = data.get('fileType')
    if not filename or not file_type:
        return jsonify({"error": "filename and fileType are required"}), 400

    safe_filename = f"{uuid.uuid4()}_{os.path.basename(filename)}"
    folder = "audio/" if "audio" in file_type else "videos/"
    s3_key = folder + safe_filename
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': S3_INPUT_BUCKET, 'Key': s3_key, 'ContentType': file_type},
            ExpiresIn=3600
        )
        return jsonify({'uploadUrl': presigned_url, 's3Key': s3_key})
    except ClientError as e:
        print(f"Error generating presigned URL: {e}")
        return jsonify({"error": "Could not generate upload URL"}), 500

@app.route('/generate-download-url', methods=['GET'])
def generate_download_url():
    """
    Generates a temporary URL for the browser to READ/STREAM a file from S3.
    """
    s3_key = request.args.get('s3_key')
    if not s3_key:
        return jsonify({"error": "s3_key parameter is required"}), 400
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': S3_INPUT_BUCKET, 'Key': s3_key},
            ExpiresIn=3600
        )
        return jsonify({"url": url})
    except ClientError as e:
        print(f"Error generating download URL: {e}")
        return jsonify({"error": "Could not generate URL"}), 500

@app.route('/find-audio-segments', methods=['POST'])
def find_audio_segments_route():
    """
    Handles audio analysis and gets AI suggestions for a segment of a specific duration.
    """
    data = request.json
    s3_key = data.get('audio_s3_key')
    reel_duration = data.get('reel_duration')

    if not s3_key or not reel_duration:
        return jsonify({"error": "audio_s3_key and reel_duration are required"}), 400
    try:
        reel_duration = int(reel_duration)
    except (ValueError, TypeError):
        return jsonify({"error": "reel_duration must be an integer."}), 400

    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp()
        local_audio_path = os.path.join(temp_dir, os.path.basename(s3_key))
        
        s3_client.download_file(S3_INPUT_BUCKET, s3_key, local_audio_path)
        
        analysis_result = find_best_segments(local_audio_path, reel_duration)
        if not analysis_result or not analysis_result.get("candidate_segments"):
            return jsonify({"error": "Failed to analyze audio and find candidate segments"}), 500
            
        ai_suggestions = suggest_audio_segment(
            analysis_result["candidate_segments"], 
            reel_duration
        )
        return jsonify({"ai_suggestions": ai_suggestions})
    except Exception as e:
        print(f"Error in /find-audio-segments route: {e}\n{traceback.format_exc()}")
        return jsonify({"error": "An internal error occurred during audio analysis"}), 500
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.route('/start-edit', methods=['POST'])
def start_edit():
    """
    Kicks off the main Celery task.
    """
    data = request.get_json()
    audio_s3_key = data.get('audio_s3_key')
    video_s3_keys = data.get('video_s3_keys')
    theme = data.get('theme')
    audio_start = data.get('audio_start_sec')
    audio_end = data.get('audio_end_sec')

    if not all([audio_s3_key, video_s3_keys, theme, audio_start is not None, audio_end is not None]):
        return jsonify({"error": "Missing required parameters."}), 400

    display_job_id = str(uuid.uuid4().hex)[:12]
    
    task = process_video_task.delay(
        display_job_id,
        theme,
        audio_s3_key,
        video_s3_keys,
        audio_start,
        audio_end
    )
    return jsonify({'job_id': task.id, 'display_job_id': display_job_id})

@app.route('/job-status', methods=['GET'])
def job_status():
    """
    Allows the frontend to poll for the status of a Celery task.
    """
    job_id = request.args.get('job_id')
    if not job_id: return jsonify({"status": "error", "message": "job_id is required"}), 400
    task = process_video_task.AsyncResult(job_id)
    response_data = {'job_id': job_id, 'status': task.state.upper(), 'progress': 0, 'message': 'Retrieving status...', 'download_url': None}
    
    if task.state == 'PENDING':
        response_data['message'] = 'Job is pending in the queue.'
    elif task.state == 'PROGRESS':
        response_data.update({'progress': task.info.get('progress_percent', 0), 'message': task.info.get('message', 'Processing...')})
    elif task.state == 'SUCCESS':
        response_data.update({'progress': 100, 'message': task.info.get('message', 'Job completed!'), 'download_url': task.info.get('download_url')})
    elif task.state == 'FAILURE':
        response_data['message'] = task.info.get('message_for_user', "An error occurred during processing.")
    
    return jsonify(response_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
