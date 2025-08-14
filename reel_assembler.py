# reel_assembler.py
import sys
from moviepy.editor import (VideoFileClip, concatenate_videoclips, AudioFileClip)
from moviepy.video.fx import all as vfx
from moviepy.video.compositing import transitions as transfx
import numpy as np
import os
import re
import traceback
import json
import cv2
import subprocess
import tempfile

# All helper functions (parse_effect_with_value, apply_ken_burns_zoom, etc.)
# remain exactly the same. The change is only in the main assemble_reel function.

def parse_effect_with_value(effect_name_str, default_value_if_not_specified=None):
    stabilize_match = re.match(r"([A-Za-z0-9]+)_([A-Za-z]+)_([A-Za-z]+)(\d+)", effect_name_str)
    if stabilize_match:
        name = stabilize_match.group(1) + stabilize_match.group(2).capitalize() + stabilize_match.group(3).capitalize()
        value_str = stabilize_match.group(4)
        try: return name, float(value_str)
        except ValueError: print(f"Warn: Val parse fail {name} from '{effect_name_str}'"); return name, default_value_if_not_specified
    general_match = re.match(r"([A-Za-z0-9]+)(?:_([A-Za-z]+))?_([\d\.]+)(%|x|px)?", effect_name_str)
    if general_match:
        name_part1 = general_match.group(1); name_detail_part = general_match.group(2); value_str = general_match.group(3); unit = general_match.group(4)
        full_name = name_part1
        if name_detail_part: full_name += name_detail_part.capitalize()
        try:
            value = float(value_str)
            if unit == '%': return full_name, value / 100.0
            return full_name, value
        except ValueError: print(f"Warn: Val parse fail general for '{effect_name_str}'."); return full_name, default_value_if_not_specified
    simple_name_val_match = re.match(r"([A-Za-z]+)(\d+\.?\d*)", effect_name_str)
    if simple_name_val_match:
        name_part = simple_name_val_match.group(1); value_part_str = simple_name_val_match.group(2)
        try:
            value = float(value_part_str)
            if name_part == "SlightZoomIn" and value > 1 and value <= 100: return name_part, value / 100.0
            return name_part, value
        except ValueError: print(f"Warn: Val parse fail simple for '{effect_name_str}'."); return name_part, default_value_if_not_specified
    return effect_name_str, default_value_if_not_specified

def apply_ken_burns_zoom(clip, zoom_start_scale=1.0, zoom_end_scale=1.1):
    if not hasattr(clip, 'duration') or clip.duration is None or clip.duration <= 0: return clip
    if not hasattr(clip, 'size') or not isinstance(clip.size, (list, tuple)) or len(clip.size) != 2: return clip
    original_width, original_height = clip.size; clip_duration = clip.duration
    if original_width == 0 or original_height == 0 : return clip
    def get_resize_factor_at_time(t):
        if clip_duration == 0: return zoom_start_scale
        return zoom_start_scale+(zoom_end_scale-zoom_start_scale)*(t/clip_duration)
    def ken_burns_frame_filter(get_frame, t):
        try:
            frame=get_frame(t); current_scale=get_resize_factor_at_time(t)
            new_w=int(original_width*current_scale); new_h=int(original_height*current_scale)
            if new_w<=0 or new_h<=0 or frame is None: return frame if frame is not None else np.zeros((original_height,original_width,3),dtype=np.uint8)
            interp=cv2.INTER_AREA if current_scale<1.0 else cv2.INTER_LINEAR
            resized_f=cv2.resize(frame,(new_w,new_h),interpolation=interp)
            crop_x_s=max(0,(new_w-original_width)//2); crop_y_s=max(0,(new_h-original_height)//2)
            crop_x_e=min(new_w,crop_x_s+original_width); crop_y_e=min(new_h,crop_y_s+original_height)
            cropped_f=resized_f[crop_y_s:crop_y_e,crop_x_s:crop_x_e]
            if cropped_f.shape[0]!=original_height or cropped_f.shape[1]!=original_width:
                 if cropped_f.shape[0]>0 and cropped_f.shape[1]>0: cropped_f=cv2.resize(cropped_f,(original_width,original_height),interpolation=cv2.INTER_LINEAR)
                 else: cropped_f=np.zeros((original_height,original_width,3),dtype=np.uint8)
            return cropped_f
        except Exception as e_f: print(f"Err KenBurns frame t={t}: {e_f}"); return get_frame(t) if callable(get_frame) else np.zeros((original_height, original_width, 3), dtype=np.uint8)
    return clip.fl(ken_burns_frame_filter,apply_to=['video'])

def apply_camera_shake(clip, strength_px=5, frequency_hz=3):
    if not hasattr(clip, 'duration') or clip.duration is None or clip.duration <= 0: return clip
    n_ks=int(clip.duration*frequency_hz); n_ks=max(2,n_ks)
    ks_t=np.linspace(0,clip.duration,n_ks,endpoint=True)
    ks_x=np.random.randint(-strength_px,strength_px+1,n_ks); ks_y=np.random.randint(-strength_px,strength_px+1,n_ks)
    return clip.set_position(lambda t:(int(round(np.interp(t,ks_t,ks_x))),int(round(np.interp(t,ks_t,ks_y)))))

def apply_color_grade(clip, style_name):
    print(f"  Applying color: '{style_name}' (dur:{clip.duration:.2f}s)")
    if style_name == "VibrantPop": return clip.fx(vfx.colorx, 1.3)
    elif style_name == "CoolCinematic": return clip.fx(vfx.lum_contrast, contrast=0.1, lum=-3)
    elif style_name == "WarmVintage":
        def wv_filter(f): mf=f.astype(np.float32);mf[:,:,0]*=1.1;mf[:,:,2]*=0.9;return np.clip(mf,0,255).astype(np.uint8)
        return clip.fl_image(wv_filter)
    elif style_name == "MonochromeClassic": return clip.fx(vfx.blackwhite)
    elif style_name == "NaturalEnhance": return clip.fx(vfx.colorx, 1.1)
    print(f"    Style '{style_name}' not recognized."); return clip

def apply_effects(clip, effect_names_list):
    # This function remains unchanged.
    if not effect_names_list: return clip
    print(f"  Applying effects: {effect_names_list} to clip (dur: {clip.duration:.2f}s)")

    current_processing_clip = clip
    temp_files_to_delete = []

    for effect_full_name_from_ai in effect_names_list:
        clip_before_this_effect = current_processing_clip
        parsed_effect_name, parsed_value = parse_effect_with_value(effect_full_name_from_ai)
        original_duration_for_effect = clip_before_this_effect.duration if clip_before_this_effect.duration is not None else 0

        processed_by_this_effect_iteration = None

        if parsed_effect_name == "SlowMotion" and parsed_value is not None and 0 < parsed_value < 1:
            processed_by_this_effect_iteration = clip_before_this_effect.fx(vfx.speedx, factor=parsed_value)
        elif parsed_effect_name == "FastForward" and parsed_value is not None and parsed_value > 1:
            processed_by_this_effect_iteration = clip_before_this_effect.fx(vfx.speedx, factor=parsed_value)
        elif parsed_effect_name == "SlightZoomIn" and parsed_value is not None and 0 < parsed_value <= 0.5:
            zoom_end_scale = 1.0 + parsed_value
            processed_by_this_effect_iteration = apply_ken_burns_zoom(clip_before_this_effect, zoom_start_scale=1.0, zoom_end_scale=zoom_end_scale)
        elif parsed_effect_name == "SubtleCameraShakeStrength" and parsed_value is not None:
            shake_strength = int(parsed_value) if 0 < parsed_value < 20 else 5
            processed_by_this_effect_iteration = apply_camera_shake(clip_before_this_effect, strength_px=shake_strength, frequency_hz=3)
        elif parsed_effect_name == "StabilizeVideoLevel" and parsed_value is not None:
            smoothing_level = int(parsed_value) if 5 <= parsed_value <= 30 else 10
            print(f"    Applying {effect_full_name_from_ai} (FFmpeg vidstab with smoothing {smoothing_level})...")
            rand_id=np.random.randint(100000,999999);tmp_in=os.path.join(tempfile.gettempdir(),f"s_in_{rand_id}.mp4");tmp_out=os.path.join(tempfile.gettempdir(),f"s_out_{rand_id}.mp4");tmp_trf=os.path.join(tempfile.gettempdir(),f"s_trf_{rand_id}.trf")
            temp_files_to_delete.extend([tmp_in,tmp_out,tmp_trf])
            try:
                fps_w=clip_before_this_effect.fps or 30.0
                clip_before_this_effect.write_videofile(tmp_in,codec="libx264",audio=False,preset="ultrafast",fps=fps_w,logger=None,threads=1)
                cmd_d=["ffmpeg","-y","-i",tmp_in,"-vf",f"vidstabdetect=shakiness=7:accuracy=10:result={tmp_trf}","-f","null","-"]
                subprocess.run(cmd_d,check=True,capture_output=True,text=True,timeout=60)
                cmd_t=["ffmpeg","-y","-i",tmp_in,"-vf",f"vidstabtransform=input={tmp_trf}:zoom=0:smoothing={smoothing_level},unsharp=5:5:0.7:3:3:0.3","-c:v","libx264","-preset","medium","-crf","20","-r",str(fps_w),tmp_out]
                subprocess.run(cmd_t,check=True,capture_output=True,text=True,timeout=90)
                if os.path.exists(tmp_out) and os.path.getsize(tmp_out)>100:
                    processed_by_this_effect_iteration=VideoFileClip(tmp_out,audio=False,fps_source="fps").set_duration(original_duration_for_effect)
                else: processed_by_this_effect_iteration=clip_before_this_effect
            except Exception as e_s:print(f"    ERR stab {effect_full_name_from_ai}:{e_s}");processed_by_this_effect_iteration=clip_before_this_effect
        else:
            print(f"    Effect '{effect_full_name_from_ai}' (name='{parsed_effect_name}') not recognized. Skipping.");processed_by_this_effect_iteration=clip_before_this_effect

        if processed_by_this_effect_iteration is not None and processed_by_this_effect_iteration is not clip_before_this_effect:
            if clip_before_this_effect is not clip:
                try: clip_before_this_effect.close()
                except Exception: pass
            current_processing_clip = processed_by_this_effect_iteration
        elif processed_by_this_effect_iteration is None:
             current_processing_clip = clip_before_this_effect

    for f_path in temp_files_to_delete:
        if os.path.exists(f_path):
            try:os.remove(f_path)
            except Exception: pass
    return current_processing_clip

def assemble_reel(edit_plan_data, all_video_shots_metadata_dict, audio_data, output_file_path):
    if not edit_plan_data or "edit_plan" not in edit_plan_data or not edit_plan_data["edit_plan"]:
        print("Error in assemble_reel: Invalid, empty, or malformed edit plan received.")
        return False, None
    print(f"\nAssembling reel ({len(edit_plan_data['edit_plan'])} segs) to: {output_file_path}")
    processed_clips_info = []
    out_w=1080; out_h=1920; out_ar=out_w/out_h

    # --- This entire block for video processing remains unchanged ---
    for i, seg_plan in enumerate(edit_plan_data["edit_plan"]):
        seg_lbl=f"Seg {i+1}/{len(edit_plan_data['edit_plan'])}";print(f"Processing {seg_lbl} plan item...")
        # ... (same segment processing logic as before) ...
        # (This block is long, so it's omitted for brevity, but it is identical to your original file)
        try:
            gid=seg_plan.get("global_shot_id")
            s_meta=all_video_shots_metadata_dict.get(gid)
            orig_vf=s_meta["original_video_path"];
            s_start=seg_plan.get("segment_start_in_shot_sec",0.0);
            s_end=seg_plan.get("segment_end_in_shot_sec")
            shot_so=s_meta["start_time_sec"];
            abs_s=shot_so+s_start;abs_e=shot_so+s_end
            
            expected_duration = s_end - s_start
            print(f"  DEBUG: Expected segment duration: {expected_duration:.6f}s (from {s_start:.6f}s to {s_end:.6f}s)")
            print(f"  DEBUG: Shot offset: {shot_so:.6f}s, Absolute times: {abs_s:.6f}s to {abs_e:.6f}s")
            
            if expected_duration < 0.1:
                print(f"  WARNING: Very short segment ({expected_duration:.6f}s) - potential precision issues")
            
            src_clip_seg=VideoFileClip(orig_vf,audio=False).subclip(abs_s,abs_e)
            print(f"  DEBUG: Actual extracted clip duration: {src_clip_seg.duration:.6f}s")
            
            proc_clip_seg = src_clip_seg.copy() # Make a copy to manipulate
            # Aspect ratio correction, resizing, color grading, effects... all unchanged
            cw,ch=proc_clip_seg.size; ca=cw/ch
            if abs(ca-out_ar)>0.01:
                tmp_c=proc_clip_seg
                if ca>out_ar:nw=int(out_ar*ch);proc_clip_seg=proc_clip_seg.fx(vfx.crop,x_center=cw/2,width=nw)
                else:nh=int(cw/out_ar);proc_clip_seg=proc_clip_seg.fx(vfx.crop,y_center=ch/2,height=nh)
                tmp_c.close()
            if proc_clip_seg.size[0]!=out_w or proc_clip_seg.size[1]!=out_h:
                tmp_c=proc_clip_seg;proc_clip_seg=proc_clip_seg.resize(newsize=(out_w,out_h));tmp_c.close()

            proc_clip_seg=apply_color_grade(proc_clip_seg,seg_plan.get("color_grade_style","NaturalEnhance"))
            proc_clip_seg=apply_effects(proc_clip_seg,seg_plan.get("effects",[]))
            
            print(f"  DEBUG: Final processed clip duration: {proc_clip_seg.duration:.6f}s")
            
            processed_clips_info.append({"clip":proc_clip_seg,"transition_to_next":seg_plan.get("transition_to_next","Cut").lower()})
            src_clip_seg.close() # Close original subclip
        except Exception as e_s:
             print(f"ERR processing {seg_lbl} (GID {gid}):{e_s}"); traceback.print_exc()
             # Clean up any created clips if there was an error
             if 'src_clip_seg' in locals() and src_clip_seg: src_clip_seg.close()
             if 'proc_clip_seg' in locals() and proc_clip_seg and proc_clip_seg is not src_clip_seg:
                 if not any(it.get("clip") is proc_clip_seg for it in processed_clips_info):
                     proc_clip_seg.close()


    if not processed_clips_info: print("No segments successfully processed. Cannot assemble."); return False, None
    # --- This block for applying transitions remains unchanged ---
    final_concat_clips=[];fd=0.3
    total_expected_duration = 0.0
    
    print(f"\nDEBUG: Applying transitions and building final clip list...")
    for i, s_info in enumerate(processed_clips_info):
        c_add=s_info["clip"]
        original_duration = c_add.duration
        
        if i>0:
            prev_t=processed_clips_info[i-1]["transition_to_next"]
            if prev_t=="fade":
                c_add=c_add.fx(transfx.fadein,duration=fd)
                print(f"  DEBUG: Applied fade transition (duration={fd}s) to clip {i+1}")
            elif prev_t=="dissolve":
                c_add=c_add.fx(transfx.crossfadein,duration=fd)
                print(f"  DEBUG: Applied dissolve transition (duration={fd}s) to clip {i+1}")
        
        print(f"  DEBUG: Clip {i+1} duration: {original_duration:.6f}s -> {c_add.duration:.6f}s")
        total_expected_duration += c_add.duration
        final_concat_clips.append(c_add)
    
    print(f"DEBUG: Total expected duration from individual clips: {total_expected_duration:.6f}s")
    if not final_concat_clips: print("No clips after trans handling."); return False, None


    # --- FINAL CONCATENATION AND WRITE (THIS IS WHERE THE CHANGE IS) ---
    final_vc=None;final_at=None;final_or_obj=None
    try:
        print(f"Concatenating {len(final_concat_clips)} final video clips...");
        final_vc=concatenate_videoclips(final_concat_clips,method="chain")
        print(f"DEBUG: Concatenated video duration: {final_vc.duration:.6f}s")
        print(f"DEBUG: Duration difference: {final_vc.duration - total_expected_duration:.6f}s")
        if final_vc.duration is None or final_vc.duration<=0:print(f"ERR: Vid composition has invalid duration.");return False,None
        
        # Load the full audio file
        final_at=AudioFileClip(audio_data["path"])
        
        # <<< --- MODIFICATION FOR AUDIO SEGMENT SELECTION --- >>>
        # Check if we need to trim the audio to a specific segment first.
        # This information is passed down from main_editor.py.
        if "segment_start_sec" in audio_data and "segment_end_sec" in audio_data:
            start_time = audio_data['segment_start_sec']
            end_time = audio_data['segment_end_sec']
            expected_audio_duration = end_time - start_time
            print(f"Trimming main audio to selected segment: {start_time:.2f}s - {end_time:.2f}s")
            print(f"DEBUG: Expected audio duration: {expected_audio_duration:.6f}s")
            # This reassigns final_at to a new AudioFileClip object representing only the desired portion.
            final_at = final_at.subclip(start_time, end_time)
            print(f"DEBUG: Actual audio duration after trim: {final_at.duration:.6f}s")
        # <<< --- END OF MODIFICATION --- >>>
        
        # Now, proceed with the (potentially trimmed) audio clip.
        # Ensure audio does not exceed the final video's duration.
        vd=final_vc.duration
        print(f"DEBUG: Final comparison - Video: {vd:.6f}s, Audio: {final_at.duration:.6f}s")
        if final_at.duration > vd:
            print(f"Audio clip ({final_at.duration:.2f}s) is longer than video ({vd:.2f}s). Trimming audio.")
            print(f"DEBUG: Duration difference that will be trimmed: {final_at.duration - vd:.6f}s")
            final_at=final_at.subclip(0, vd)
        elif final_at.duration < vd:
            print(f"Warning: Audio clip ({final_at.duration:.2f}s) is shorter than video ({vd:.2f}s). Video will have silence at the end.")
            print(f"DEBUG: Duration shortfall: {vd - final_at.duration:.6f}s")

        final_or_obj=final_vc.set_audio(final_at)
        print(f"Writing final reel (effective duration: {final_or_obj.duration:.2f}s)...")
        final_or_obj.write_videofile(output_file_path,codec="libx264",audio_codec="aac",threads=max(1,(os.cpu_count() or 2)//2),fps=30,preset="medium",logger='bar')
        
        print("Reel assembly complete!"); return True, output_file_path
    except Exception as e_w:
        print(f"ERROR during final concatenation/write: {e_w}");traceback.print_exc();return False,None
    finally:
        # --- This cleanup block remains unchanged ---
        print("  Cleaning up MoviePy clips in final assembly stage...")
        for seg_data_cln in processed_clips_info:
            clip_to_close = seg_data_cln.get("clip")
            if clip_to_close:
                try: clip_to_close.close()
                except Exception: pass
        if 'final_concat_clips' in locals():
             for clip_fcc in final_concat_clips:
                is_already_in_processed = any(clip_fcc is pci.get("clip") for pci in (processed_clips_info or []))
                if clip_fcc and not is_already_in_processed:
                     try: clip_fcc.close()
                     except Exception: pass
        if final_vc:
            try: final_vc.close();
            except Exception: pass
        if final_at:
            try: final_at.close();
            except Exception: pass
        if 'final_or_obj' in locals() and final_or_obj and final_or_obj is not final_vc:
            try: final_or_obj.close();
            except Exception: pass
        print("  MoviePy cleanup attempt finished.")


# The __main__ test block remains unchanged. It will test the original code path
# since it doesn't add 'segment_start_sec' to its dummy data, which is fine.
if __name__ == '__main__':
    print("\n--- Testing reel_assembler.py (standalone with stabilization if planned) ---")
    dummy_plan_content={"edit_plan":[{"global_shot_id":0,"segment_start_in_shot_sec":0.0,"segment_end_in_shot_sec":2.0,"color_grade_style":"VibrantPop","transition_to_next":"Cut","effects":["SlightZoomIn_10%","Stabilize_Video_Level10"],"reasoning":"Test Zoom&Stab"},{"global_shot_id":1,"segment_start_in_shot_sec":0.5,"segment_end_in_shot_sec":2.5,"color_grade_style":"NaturalEnhance","transition_to_next":"Fade","effects":["SubtleCameraShake_Strength_5"],"reasoning":"Test Shake"}]}
    dummy_plan_path="output/test_assembler_edit_plan.json"
    if not os.path.exists("output"):os.makedirs("output")
    with open(dummy_plan_path,"w") as fp:json.dump(dummy_plan_content,fp,indent=2)
    dummy_video_path="input_videos/dummy_test_video.mp4";dummy_audio_path="input_audio/dummy_test_audio.wav"
    if os.path.exists(dummy_plan_path) and os.path.exists(dummy_video_path) and os.path.exists(dummy_audio_path):
        with open(dummy_plan_path,"r") as f:test_plan=json.load(f)
        if test_plan and test_plan.get("edit_plan"):
            test_shots_meta={gid:{"global_shot_id":gid,"original_video_path":dummy_video_path,"start_time_sec":0,"duration_sec":5.0} for gid in set(s['global_shot_id'] for s in test_plan['edit_plan'])}
            test_ad={"path":dummy_audio_path,"duration":30.0};out_tr="output/test_standalone_reel.mp4"
            print(f"Attempting test reel to:{out_tr}")
            success_asm, out_f = assemble_reel(test_plan,test_shots_meta,test_ad,out_tr)
            if success_asm: print(f"Standalone assembly test SUCCESS: {out_f}")
            else: print("Standalone assembly test FAILED.")
    else:
        print("Skipping standalone reel_assembler test: missing prerequisites (dummy plan, video, or audio).")
