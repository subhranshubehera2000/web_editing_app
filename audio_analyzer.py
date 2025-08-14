# audio_analyzer.py 
import librosa
import numpy as np
import traceback

def find_best_segments(audio_path, reel_duration_sec=15):
    """
    NEW FUNCTION. Analyzes the full audio file to find candidate segments
    for a reel based on musical structure and energy.
    This is called ONCE right after the user uploads the full audio file.
    """
    try:
        print(f"Finding best audio segments in: {audio_path}")
        # Load up to 5 minutes to keep it reasonable
        y, sr = librosa.load(audio_path, duration=300) 
        full_duration = librosa.get_duration(y=y, sr=sr)
        
        # We need a fallback if the uploaded audio is shorter than the reel
        if full_duration < reel_duration_sec:
             print(f"  Warning: Audio duration ({full_duration:.2f}s) is less than reel duration ({reel_duration_sec}s). Using full audio.")
             return {
                "candidate_segments": [{
                    "start_time": 0.0,
                    "end_time": full_duration,
                    "duration": full_duration,
                    "avg_energy_score": np.mean(librosa.feature.rms(y=y)[0]) * 1000
                }],
                "full_duration": full_duration
             }


        # 1. Structural Segmentation to find parts like verse, chorus
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        # k=10 is a good starting point to find ~10 major sections in a song
        boundaries = librosa.segment.agglomerative(chroma, k=10) 
        segment_times = librosa.frames_to_time(boundaries, sr=sr)
        
        full_segment_times = np.concatenate(([0.0], segment_times, [full_duration]))
        
        # 2. Analyze the energy of each segment
        rms_energy = librosa.feature.rms(y=y)[0]
        candidate_segments = []
        for i in range(len(full_segment_times) - 1):
            start_time = full_segment_times[i]
            end_time = full_segment_times[i+1]
            duration = end_time - start_time
            
            # We are interested in segments that are at least long enough for our reel
            if duration >= reel_duration_sec:
                start_frame = librosa.time_to_frames(start_time, sr=sr)
                end_frame = librosa.time_to_frames(end_time, sr=sr)
                avg_energy = np.mean(rms_energy[start_frame:end_frame])
                
                candidate_segments.append({
                    "start_time": float(start_time),
                    "end_time": float(end_time),
                    "duration": float(duration),
                    "avg_energy_score": float(avg_energy) * 1000 
                })

        if not candidate_segments: # Fallback if no segment is long enough
             print("  Warning: No segments long enough. Returning full audio as candidate.")
             return { "candidate_segments": [{"start_time":0.0, "end_time":full_duration, "duration":full_duration, "avg_energy_score":1.0}], "full_duration": full_duration }

        # Sort by energy to find the most "exciting" parts
        candidate_segments = sorted(candidate_segments, key=lambda x: x['avg_energy_score'], reverse=True)
        print(f"  Found {len(candidate_segments)} potential audio segments.")

        return {
            "path": audio_path,
            "candidate_segments": candidate_segments[:5], # Return top 5 most energetic
            "full_duration": full_duration
        }
    except Exception as e:
        print(f"ERROR in find_best_segments: {e}"); traceback.print_exc(); return None


def analyze_audio_segment(audio_path, start_sec, end_sec):
    """
    ORIGINAL FUNCTION, NOW MODIFIED. Analyzes ONLY a specific segment of an audio file
    to get detailed features (beats, onsets) for the editor AI.
    This is called AFTER the user confirms their chosen audio segment.
    """
    try:
        duration = end_sec - start_sec
        print(f"Analyzing audio SEGMENT: {audio_path} from {start_sec:.2f}s to {end_sec:.2f}s (Dur: {duration:.2f}s)")
        
        # Load only the specified segment of the audio file for efficiency
        y, sr = librosa.load(audio_path, offset=start_sec, duration=duration)
        
        print(f"  Loaded audio segment: y.shape={y.shape}, sr={sr}")

        # --- ALL THE DETAILED ANALYSIS FROM YOUR ORIGINAL FILE NOW RUNS ON THE SEGMENT ---
        # 1. Tempo and Beat Detection
        tempo_array, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        # Your original tempo logic was solid, so we keep it
        actual_tempo_scalar = np.mean(tempo_array) if isinstance(tempo_array, np.ndarray) and tempo_array.size > 0 else 120.0
        
        # 2. Onset Detection
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        # 3. RMS Energy for prompt
        rms_energy_frames = librosa.feature.rms(y=y)[0]
        rms_times = librosa.times_like(rms_energy_frames, sr=sr)
        simplified_energy_values_at_times = []
        # Your original simplification logic is also kept
        num_energy_points = 15 
        if len(rms_times) > 1:
             indices = np.linspace(0, len(rms_times) - 1, num_energy_points, dtype=int)
             for i in indices:
                 energy_val = rms_energy_frames[i]
                 simplified_energy_values_at_times.append(
                    (float(round(rms_times[i], 2)), float(round(energy_val * 100, 1)))
                 )
        
        print(f"  Segment Analysis Summary: Tempo {actual_tempo_scalar:.1f} BPM, {len(beat_times)} beats")

        # The data returned is for the AI director to use for video editing
        return {
            "path": audio_path,
            "tempo": float(actual_tempo_scalar),
            "beat_times": beat_times.tolist(),
            "onset_times": onset_times.tolist(),
            "duration": float(duration), # The duration of the segment
            "simplified_energy_values_at_times": simplified_energy_values_at_times,
            "segment_start_sec": start_sec, # Important for the reel assembler
            "segment_end_sec": end_sec,
        }
    except Exception as e:
        print(f"ERROR in analyze_audio_segment for {audio_path}: {e}"); traceback.print_exc(); return None
