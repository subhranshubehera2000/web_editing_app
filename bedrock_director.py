# bedrock_director.py
import boto3
import json
import os
import traceback
import numpy as np
import re
from botocore.exceptions import ClientError

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
# Using Haiku for simple, fast, and cheap suggestion tasks is best practice
SUGGESTION_MODEL_ID = "apac.anthropic.claude-3-sonnet-20240229-v1:0"
# Using Sonnet for the main creative task is appropriate
EDIT_PLAN_MODEL_ID = "apac.anthropic.claude-3-sonnet-20240229-v1:0"

bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)

def director_print(message):
    print(f"[bedrock_director] {message}")

def suggest_reel_themes(audio_data_summary, video_shots_summary, num_suggestions=1):
    director_print(f"Suggesting themes with CONTEXT from Bedrock model: {SUGGESTION_MODEL_ID}")
    audio_energy_desc = "varied"
    try:
        if audio_data_summary.get("simplified_energy_values_at_times"):
            avg_energy = np.mean([e[1] for e in audio_data_summary["simplified_energy_values_at_times"]])
            if avg_energy > 60: audio_energy_desc = "high energy"
            elif avg_energy < 30: audio_energy_desc = "low energy or chill"
    except Exception: pass
    visual_content_str = ", ".join(video_shots_summary.get("visual_content", ["general footage"]))

    prompt = f"""You are a creative director. Suggest {num_suggestions} themes (3-6 words) for a social media reel based on this summary:
- Audio Vibe: Tempo around {audio_data_summary.get('tempo','N/A'):.0f} BPM, "{audio_energy_desc}" energy.
- Visual Content: **{visual_content_str}**.
- Visual Feel: Average motion score is {video_shots_summary.get('avg_motion_score','N/A'):.1f}.
Examples: "Serene Coastal Escape", "Dynamic Urban Energy", "Vibrant Kitchen Creations".
Output ONLY a valid JSON list of strings. Example: ["My Suggested Theme"].
"""
    try:
        req_body=json.dumps({"anthropic_version":"bedrock-2023-05-31","max_tokens":256,"temperature":0.75,"messages":[{"role":"user","content":[{"type":"text","text":prompt}]}]})
        resp=bedrock_runtime.invoke_model(body=req_body,modelId=SUGGESTION_MODEL_ID,accept='application/json',contentType='application/json')
        resp_str=resp.get('body').read().decode('utf-8')
        json_txt_content=json.loads(resp_str).get('content', [{}])[0].get('text', '')
        match = re.search(r'\[.*?\]', json_txt_content, re.DOTALL)
        if match:
            sug_themes = json.loads(match.group(0))
            if isinstance(sug_themes, list) and all(isinstance(t, str) for t in sug_themes):
                director_print(f"Parsed themes: {sug_themes}")
                return sug_themes
        return []
    except ClientError as e: director_print(f"Bedrock ClientError in themes: {e}"); raise
    except Exception as e: director_print(f"CRITICAL ERROR suggesting themes: {e}"); traceback.print_exc(); return []

def suggest_audio_segment(candidate_segments, reel_duration, num_suggestions=3):
    director_print(f"Asking Bedrock to choose from {len(candidate_segments)} audio candidates.")
    prompt = f"""You are an expert audio producer. From the high-energy song segments below, select the best {num_suggestions} options for a reel exactly **{reel_duration}** seconds long.

Available Segments:
{json.dumps(candidate_segments, indent=2)}

Your Task:
1.  Prioritize high-energy segments.
2.  Select a start and end time WITHIN a candidate's range to create a clip of **exactly {reel_duration} seconds**.
3.  Provide a short "reasoning" for each choice.
4.  Respond with ONLY a valid JSON object.

EXAMPLE JSON:
```json
{{
  "suggestions": [
    {{"start_time": 45.5, "end_time": 60.5, "reasoning": "Starts on the main chorus."}}
  ]
}}
```
"""
    try:
        req_body = json.dumps({"anthropic_version":"bedrock-2023-05-31","max_tokens":1024,"temperature":0.5,"messages":[{"role":"user","content":[{"type":"text","text":prompt}]}]})
        resp = bedrock_runtime.invoke_model(body=req_body,modelId=SUGGESTION_MODEL_ID,accept='application/json',contentType='application/json')
        resp_str = resp.get('body').read().decode('utf-8')
        json_txt_content = json.loads(resp_str).get('content', [{}])[0].get('text', '')
        match = re.search(r"\{[\s\S]*\}", json_txt_content)
        if match:
            parsed_json = json.loads(match.group(0))
            if "suggestions" in parsed_json and isinstance(parsed_json["suggestions"], list):
                director_print(f"Bedrock suggested {len(parsed_json['suggestions'])} audio segments.")
                return parsed_json["suggestions"]
        return []
    except ClientError as e: director_print(f"Bedrock ClientError in audio segment: {e}"); raise
    except Exception as e: director_print(f"CRITICAL ERROR suggesting audio segment: {e}"); traceback.print_exc(); return []

def generate_ai_edit_plan(audio_data, all_video_shots_metadata,
                          min_reel_duration, max_reel_duration,
                          reel_theme,
                          audio_segment_start_sec=0.0):
    director_print(f"Generating professional edit plan for theme: '{reel_theme}'")

    audio_beats_sum = list(np.round(audio_data.get('beat_times', [])[:30], 2))
    audio_energy_sum = audio_data.get('simplified_energy_values_at_times', [])
    available_shots_prompt_str = ""
    for s in all_video_shots_metadata:
        available_shots_prompt_str += (f"- GID:{s.get('global_shot_id','N/A')}, Dur:{s.get('duration_sec',0):.2f}s, "
                                       f"Bright:{s.get('avg_brightness',0):.0f}, Motion:{s.get('avg_motion_score',0):.1f}\n")
    
    # <<< --- THIS IS THE FINAL, BULLETPROOF PROMPT --- >>>
    prompt = f"""You are an expert AI video editor. Your task is to create a JSON-based edit plan. You must follow all rules precisely.

**Creative Brief:**
- **Theme:** "{reel_theme}"
- **Target Duration:** Create a final sequence between **{min_reel_duration:.1f} and {max_reel_duration:.1f} seconds**.

**Provided Assets:**
1.  **Audio Analysis:** Key Beat Times (sec): {audio_beats_sum}
2.  **Video Shot Library (Footage available):**
{available_shots_prompt_str}

**Your Task: Create a Master Edit Plan in JSON format**

**CRITICAL RULES & DATA FORMATTING:**
1.  **VALID GIDs ONLY:** You **MUST ONLY** use `global_shot_id` (GID) values from the "Video Shot Library".
2.  **VALID TIMECODES ARE MANDATORY:** The `"segment_start_in_shot_sec"` and `"segment_end_in_shot_sec"` keys are **REQUIRED** for every segment. Their values **MUST** be numbers (float or integer). They **CANNOT** be `null` or missing.
3.  **LOGICAL TIMECODES:** For any given segment, the `"segment_end_in_shot_sec"` value **MUST BE GREATER THAN** the `"segment_start_in_shot_sec"` value.
4.  **WITHIN SHOT DURATION:** The chosen segment `segment_end_in_shot_sec` **MUST NOT EXCEED** the total `Dur` of its `GID`. For example, for GID 0 which has a Dur of 10.5s, `segment_end_in_shot_sec` must be less than or equal to 10.5.
5.  **TOTAL DURATION:** The total duration of your final reel plan (the sum of all segment durations) **MUST** be between {min_reel_duration:.1f} and {max_reel_duration:.1f} seconds.

**ARTISTIC DIRECTIVES:**
- Create a narrative arc: Hook, Build-up, Climax, Outro.
- Sync cuts to the rhythm and mood of the music.
- Use effects and color grading purposefully to enhance emotion.

Generate ONLY the valid JSON edit plan.
"""

    try:
        req_b_dict = {"anthropic_version":"bedrock-2023-05-31", "max_tokens":4096, "temperature":0.4, "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]}
        req_b_json = json.dumps(req_b_dict)
        
        director_print(f"Invoking Bedrock for edit plan...")
        
        resp = bedrock_runtime.invoke_model(body=req_b_json, modelId=EDIT_PLAN_MODEL_ID, accept='application/json', contentType='application/json')
        resp_str = resp.get('body').read().decode('utf-8')
        ai_resp_txt = json.loads(resp_str).get('content', [{}])[0].get('text', '')

        json_match = re.search(r"\{[\s\S]*\}", ai_resp_txt)
        if json_match:
            plan_j_str = json_match.group(0)
            p_plan = json.loads(plan_j_str)
            if "edit_plan" in p_plan and isinstance(p_plan["edit_plan"], list):
                # Simple validation to ensure critical keys are present
                is_valid = all(
                    isinstance(seg.get("global_shot_id"), int) and
                    isinstance(seg.get("segment_start_in_shot_sec"), (int, float)) and
                    isinstance(seg.get("segment_end_in_shot_sec"), (int, float))
                    for seg in p_plan["edit_plan"]
                )
                if is_valid:
                    director_print(f"OK, successfully parsed and validated edit plan with {len(p_plan['edit_plan'])} segments.")
                    return p_plan
                else:
                    director_print("ERR: Parsed edit plan has missing or invalid required keys.")
        
        director_print("ERR: Could not parse a valid JSON object with 'edit_plan' from AI response.")
        return None
    except ClientError as e: director_print(f"Bedrock ClientError in plan generation: {e}"); raise
    except Exception as e: director_print(f"CRITICAL Bedrock/Plan Resp Err:{e}"); traceback.print_exc(); return None
