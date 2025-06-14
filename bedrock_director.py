# bedrock_director.py
import boto3
import json
import os
import traceback
import numpy as np
import re 

AWS_REGION = "ap-south-1"
THEME_SUGGESTION_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0" # Using Haiku for themes
EDIT_PLAN_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0" 

bedrock_runtime = boto3.client(service_name='bedrock-runtime', region_name=AWS_REGION)

def director_print(message): print(f"[bedrock_director] {message}")

def suggest_reel_themes(audio_data_summary, video_shots_summary, num_suggestions=1):
    director_print(f"Suggesting themes with Bedrock model: {THEME_SUGGESTION_MODEL_ID}")
    audio_energy_desc = "varied"
    if audio_data_summary.get("simplified_energy_values_at_times"):
        try:
            avg_energy = np.mean([e[1] for e in audio_data_summary["simplified_energy_values_at_times"] if isinstance(e,(list,tuple)) and len(e)==2 and isinstance(e[1],(int,float))])
            if avg_energy > 60: audio_energy_desc = "high energy"
            elif avg_energy < 30: audio_energy_desc = "low energy or chill"
            else: audio_energy_desc = "medium energy"
        except Exception: pass
    prompt = f"""You are a creative assistant... (same theme suggestion prompt as last full version)...
Audio Characteristics: Tempo: {audio_data_summary.get('tempo','N/A'):.0f} BPM, Energy: "{audio_energy_desc}", Duration: {audio_data_summary.get('duration','N/A'):.0f}s
Video Overview: Shots: {video_shots_summary.get('num_shots','N/A')}, Avg Motion: {video_shots_summary.get('avg_motion_score','N/A'):.1f}, Avg Brightness: {video_shots_summary.get('avg_brightness','N/A'):.0f}
Your task: suggest {num_suggestions} themes for a short social media reel. Concise (3-6 words). Examples: "Energetic Urban Adventure", "Serene Nature Escape".
Output: VALID JSON list of strings. E.g., ["Theme 1", "Theme 2"] ONLY the list.
"""
    try:
        req_body=json.dumps({"anthropic_version":"bedrock-2023-05-31","max_tokens":256,"temperature":0.75,"messages":[{"role":"user","content":[{"type":"text","text":prompt}]}]})
        director_print("Invoking Bedrock for theme suggestions...");resp=bedrock_runtime.invoke_model(body=req_body,modelId=THEME_SUGGESTION_MODEL_ID,accept='application/json',contentType='application/json')
        resp_str=resp.get('body').read().decode('utf-8');director_print(f"Theme raw response: '{resp_str[:200]}...'")
        json_txt_content="";resp_data=json.loads(resp_str)
        if resp_data.get('content') and resp_data.get('content')[0].get('type')=='text':json_txt_content=resp_data.get('content')[0].get('text')
        ls=json_txt_content.find('[');le=json_txt_content.rfind(']')+1
        if ls!=-1 and le>ls:
            json_l_str=json_txt_content[ls:le];
            try:
                sug_themes=json.loads(json_l_str)
                if isinstance(sug_themes,list) and all(isinstance(t,str) for t in sug_themes):director_print(f"Parsed themes: {sug_themes}");return sug_themes
                else: director_print(f"WARN: Themes not list of str: {sug_themes}")
            except json.JSONDecodeError as je: director_print(f"ERR parsing theme JSON: {je}. Str:'{json_l_str}'")
        else: director_print(f"ERR: No JSON list in theme response: '{json_txt_content}'")
        return []
    except Exception as e:director_print(f"CRIT ERR suggesting themes:{e}");traceback.print_exc();return []

def generate_ai_edit_plan(audio_data, all_video_shots_metadata,
                          desired_reel_duration_min_sec, desired_reel_duration_max_sec,
                          reel_theme="general upbeat and engaging"):
    director_print(f"Generating edit plan with model: {EDIT_PLAN_MODEL_ID} for theme: '{reel_theme}'")
    audio_beats_sum = list(np.round(audio_data.get('beat_times', [])[:25], 2))
    audio_onsets_sum = list(np.round(audio_data.get('onset_times', [])[:25], 2))
    audio_energy_sum = audio_data.get('simplified_energy_values_at_times', [])[:20]
    prompt_parts = [f"""You are an expert AI video editor... (The full, long, detailed prompt from your LAST "COMPLETE bedrock_director.py" which had all rhythmic guidance, highlight quality, effect usage like stabilization, repetition discouragement, and the refined JSON example)
Reel Specs: Theme: "{reel_theme}", Duration: {desired_reel_duration_min_sec}-{desired_reel_duration_max_sec}s.
Audio Info: Tempo {audio_data.get('tempo','N/A'):.2f}BPM, Beats: {audio_beats_sum}, Onsets: {audio_onsets_sum}, Energy: {audio_energy_sum}, Total Dur: {audio_data.get('duration','N/A'):.2f}s.
Available Video Shots: (brightness, motion_score, duration_of_this_shot. `motion_score` can be subject motion OR camera shake)"""]
    MAX_SHOTS=60;shots_prompt=all_video_shots_metadata
    if len(all_video_shots_metadata)>MAX_SHOTS:
        director_print(f"WARN:Shots({len(all_video_shots_metadata)})>MAX({MAX_SHOTS}).Sampling.");
        usable=[s for s in all_video_shots_metadata if s.get('duration_sec',0)>0.5];
        if len(usable)>MAX_SHOTS: shots_prompt=sorted(usable,key=lambda x:(x.get('avg_motion_score',0),x.get('avg_brightness',0)),reverse=True)[:MAX_SHOTS]
        else: shots_prompt=usable
        director_print(f" Using {len(shots_prompt)} shots after filter/sample.")
    elif not all_video_shots_metadata:director_print("ERR:No shots for edit plan.");return None
    for i,sm in enumerate(shots_prompt):
        prompt_parts.append(f"- GID:{sm.get('global_shot_id','N/A')},Hint:{'_'.join(os.path.basename(sm.get('original_video_path','N/A')).split('_')[:2])},Dur:{sm.get('duration_sec',0):.2f}s,Bright:{sm.get('avg_brightness',0):.0f},Motion:{sm.get('avg_motion_score',0):.1f}")
    prompt_parts.append(f"""
**Your Task: Create JSON Edit Plan** (MUST be SINGLE VALID JSON, root key "edit_plan": list of "segment" objects)
Segment Keys: "global_shot_id"(int), "segment_start_in_shot_sec"(float), "segment_end_in_shot_sec"(float), "color_grade_style"(str: "VibrantPop", "CoolCinematic", "NaturalEnhance", "WarmVintage", "MonochromeClassic"), "transition_to_next"(str: "Cut", "Fade", "Dissolve"; "None" for last), "effects"(list[str], e.g., "SlowMotion_0.5x", "SlightZoomIn_10%", "SubtleCameraShake_Strength_5", "Stabilize_Video_Level10"), "reasoning"(str, max 20 words).
**EXAMPLE JSON:**
```json
{{
  "edit_plan": [
    {{"global_shot_id":2,"segment_start_in_shot_sec":0.1,"segment_end_in_shot_sec":1.6,"color_grade_style":"VibrantPop","transition_to_next":"Cut","effects":["SlightZoomIn_15%"],"reasoning":"Opening, energetic on main beat."}},
    {{"global_shot_id":0,"segment_start_in_shot_sec":3.5,"segment_end_in_shot_sec":5.5,"color_grade_style":"NaturalEnhance","transition_to_next":"Fade","effects":["Stabilize_Video_Level10"],"reasoning":"Scenic, stabilize for smoothness."}},
    {{"global_shot_id":4,"segment_start_in_shot_sec":0.0,"segment_end_in_shot_sec":1.2,"color_grade_style":"CoolCinematic","transition_to_next":"None","effects":["SlowMotion_0.5x"],"reasoning":"Final dramatic shot, slow."}}
  ]
}}
```
**Critical Instructions for Editing:**
1. **Rhythmic Precision & Pacing:** Cuts ON/slightly BEFORE prominent `beat_times`/`onset_times` (kicks, snares, phrase starts). High audio energy (Energy Profile > 45-55 or fast beats) -> SHORTER segments (0.6-1.5s), HIGH `motion_score` shots (>15-20, if not shake). Medium energy (25-45) -> 1.2-2.2s segments. Low energy (<25 or melodic) -> LONGER segments (1.8-3.5s) IF visually compelling OR for calm. VARY segment durations with music structure.
2. **"Highlight" Quality & Visual Storytelling:** For "{reel_theme}", choose segments with clear subjects, good composition, evoking desired mood (excitement, beauty). Prioritize engaging ACTION/VIEWS *within* longer shots. Use `motion_score` and `brightness` as clues. Good SHOT VARIETY (avoid GID repeats unless for very short rhythmic effect; if repeating, use different time segments). Sequence for a pleasing visual journey.
3. **Shot Boundaries & Duration Math:** Segments MUST be within chosen GID's `duration_of_this_shot`. Account for speed effects ("SlowMotion_0.5x" DOUBLES duration, "FastForward_2x" HALVES) in TOTAL reel duration.
4. **Transitions & Effects:** "Cut" for rhythm. "Fade"/"Dissolve" (~0.3s) purposefully for mood/scene shifts or softer music. "SlightZoomIn_X%": on static/slow shots (X% is total zoom e.g. 10%->1.1x). "SubtleCameraShake_Strength_X": on static shots (X=pixels e.g. 3,5; avoid if `motion_score` already high from subject movement). "Stabilize_Video_LevelX": if high `motion_score` (>20-25) seems like UNWANTED SHAKE (e.g. static scenery, NOT intentional fast action); use Level10 (moderate) or Level15 (stronger). "SlowMotion_0.5x": for impactful moments/musical slowdowns. "FastForward_2x": for energy/quick montages. Use effects SPARINGLY, with intent (1-2 subtle per segment often best). Logical effect order: Stabilize -> Spatial (Zoom) -> Temporal (Speed).
5. **Total Reel Duration:** Sum of *final effective segment durations* MUST be {desired_reel_duration_min_sec}-{desired_reel_duration_max_sec}s. This is critical.
Generate ONLY the JSON.
""")
    final_e_prompt="".join(prompt_parts)
    try: 
        req_b_dict={"anthropic_version":"bedrock-2023-05-31","max_tokens":4096,"temperature":0.35,"top_p":0.9,"system":"You are an AI assistant... (same system prompt as your last working version)","messages":[{"role":"user","content":[{"type":"text","text":final_e_prompt}]}]}
        req_b_json=json.dumps(req_b_dict);director_print(f"Invoke model {EDIT_PLAN_MODEL_ID}. Prompt len:{len(final_e_prompt)} chars.")
        resp=bedrock_runtime.invoke_model(body=req_b_json,modelId=EDIT_PLAN_MODEL_ID,accept='application/json',contentType='application/json')
        director_print("Model invoked for plan. Processing...");resp_b_raw=resp.get('body').read();resp_b_str=resp_b_raw.decode('utf-8') 
        director_print(f"Plan raw resp (300):'{resp_b_str[:300]}...'");resp_b_obj=json.loads(resp_b_str);director_print("Plan resp body loaded.")
        ai_resp_txt=""
        if resp_b_obj.get('content') and isinstance(resp_b_obj.get('content'),list) and resp_b_obj.get('content'):
             msg_c=resp_b_obj.get('content')[0];
             if msg_c.get('type')=='text':ai_resp_txt=msg_c.get('text')
        director_print(f"Plan extracted AI text (300):'{ai_resp_txt[:300]}...'");plan_j_str=None
        json_md_match=re.search(r"```json\s*(\{[\s\S]*?\})\s*```",ai_resp_txt,re.DOTALL) 
        if json_md_match:plan_j_str=json_md_match.group(1);director_print("Extracted plan JSON from markdown.")
        else:
            js=ai_resp_txt.find('{');je=ai_resp_txt.rfind('}')+1
            if js!=-1 and je>js:plan_j_str=ai_resp_txt[js:je];director_print("Extracted plan JSON using boundaries.")
            else:director_print("ERR:No JSON boundaries in plan.");director_print(f"Full AI Plan Resp:'{ai_resp_txt}'");return None
        if plan_j_str:
            director_print(f"Parse plan JSON (300):'{plan_j_str[:300]}...'")
            try: 
                p_plan=json.loads(plan_j_str)
                if "edit_plan" not in p_plan or not isinstance(p_plan["edit_plan"],list):director_print("ERR:'edit_plan' missing/invalid.");director_print(f"Parsed:{p_plan}");return None
                if not p_plan["edit_plan"]:director_print("WARN:Bedrock returned empty 'edit_plan'.")
                director_print(f"OK parsed plan:{len(p_plan['edit_plan'])} segs.");return p_plan
            except json.JSONDecodeError as j_e:director_print(f"PlanJSONParseErr:{j_e}");director_print(f"Problem JSON(full):'{plan_j_str}'");return None
        else: director_print("ERR:plan_json_str None.");return None
    except ClientError as ce: # Catch Boto3 client errors specifically
        director_print(f"CRITICAL Bedrock ClientError for Edit Plan: {ce}"); traceback.print_exc()
        # Re-raise specific error type or a custom one if Celery task needs to see it
        raise # Allow Celery's autoretry to handle it if it's a ThrottlingException
    except Exception as e: director_print(f"CRITICAL Bedrock/Plan Resp Err:{e}");traceback.print_exc();return None

if __name__ == '__main__':
    # ... (The __main__ block for testing bedrock_director.py can be the same as the last one I provided,
    #      which tests both suggest_reel_themes and generate_ai_edit_plan with dummy data.)
    # ... For brevity here, it's omitted but ensure it's the complete one.
    dummy_audio_summary = {"tempo":140, "simplified_energy_values_at_times":[(0,0),(1,60),(2,90)],"duration":15}
    dummy_video_summary = {"num_shots":5, "avg_motion_score":25.0,"avg_brightness":150,"total_video_duration_sec":50}
    print("\n--- Test suggest_reel_themes ---");themes = suggest_reel_themes(dummy_audio_summary,dummy_video_summary)
    if themes:
        print(f"Suggested:{themes}");active_th=themes[0]
        print(f"\n--- Test generate_ai_edit_plan with theme:'{active_th}' ---")
        dummy_ad_full={"path":"dummy.mp3","tempo":140,"beat_times":np.linspace(0,10,20).tolist(),"onset_times":np.linspace(0,10,15).tolist(),"duration":15,"simplified_energy_values_at_times":dummy_audio_summary["simplified_energy_values_at_times"]}
        dummy_vs_full=[{"global_shot_id":i,"original_video_path":f"v{i}.mp4","duration_sec":5.0,"avg_brightness":150,"avg_motion_score":20+i*2} for i in range(3)]
        if not os.path.exists("output"):os.makedirs("output")
        plan=generate_ai_edit_plan(dummy_ad_full,dummy_vs_full,5,10,reel_theme=active_th)
        if plan and "edit_plan" in plan:print("\nGenerated Plan (test):");print(json.dumps(plan,indent=2))
        else:print("Fail: Gen plan with suggested theme.")
    else:print("Fail: No themes suggested.")
