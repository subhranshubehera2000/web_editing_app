# audio_analyzer.py
import librosa
import numpy as np
import traceback

def analyze_audio(audio_path):
    """
    Analyzes an audio file to extract tempo, beat times, onset times, duration, and energy.
    """
    try:
        print(f"Analyzing audio file: {audio_path}")
        y, sr = librosa.load(audio_path)
        print(f"  Loaded audio: y.shape={y.shape if isinstance(y, np.ndarray) else 'N/A'}, sr={sr}")

        # 1. Tempo and Beat Detection
        print("  Attempting beat tracking...")
        tempo_array, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        if isinstance(tempo_array, np.ndarray):
            # Handle cases where tempo_array might be empty or not a single value
            if tempo_array.size > 0:
                actual_tempo_scalar = tempo_array.item() if tempo_array.size == 1 else np.mean(tempo_array)
            else:
                print("Warning: Beat tracking returned empty tempo_array. Defaulting tempo to 120.")
                actual_tempo_scalar = 120.0 # Default if beat tracking fails badly
        else:
            actual_tempo_scalar = tempo_array # Assume it's already a scalar
        print(f"  Extracted scalar tempo: {actual_tempo_scalar}")

        # 2. Detect onsets
        print("  Attempting onset detection...")
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
        onset_times = librosa.frames_to_time(onset_frames, sr=sr)

        # 3. Calculate RMS Energy per frame
        print("  Attempting RMS energy calculation...")
        frame_length = 2048
        hop_length = 512
        rms_energy_frames = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_times = librosa.times_like(rms_energy_frames, sr=sr, hop_length=hop_length) # Corrected frame_length arg if needed or use default

        # For the prompt, provide a simplified list of energy transitions or key points
        num_energy_points_for_prompt = 15 # Increase number of points for better representation
        simplified_energy_values_at_times = []
        if len(rms_times) > 1 and len(rms_energy_frames) > 1:
            if len(rms_times) > num_energy_points_for_prompt:
                energy_indices = np.linspace(0, len(rms_times) - 1, num_energy_points_for_prompt, dtype=int)
                for i in energy_indices:
                    # Ensure rms_energy_frames[i] is a scalar before rounding
                    energy_val = rms_energy_frames[i]
                    if isinstance(energy_val, np.ndarray): energy_val = energy_val.item() # Get scalar if it's a 0-d array
                    simplified_energy_values_at_times.append(
                        (float(round(rms_times[i], 2)), float(round(energy_val * 100, 1))) # Scale energy for easier LLM use (0-100+)
                    )
            else: # If fewer points than desired, take all of them
                for i in range(len(rms_times)):
                    energy_val = rms_energy_frames[i]
                    if isinstance(energy_val, np.ndarray): energy_val = energy_val.item()
                    simplified_energy_values_at_times.append(
                        (float(round(rms_times[i], 2)), float(round(energy_val * 100, 1)))
                    )
        else:
            print("Warning: Not enough RMS energy frames to simplify for prompt.")


        print(f"  Simplified RMS energy values at times for prompt: {simplified_energy_values_at_times[:5]}...")

        duration = librosa.get_duration(y=y, sr=sr)
        
        print("\n  --- Audio Analysis Summary (for Bedrock) ---")
        print(f"    Tempo: {actual_tempo_scalar:.2f} BPM")
        print(f"    Beat Times (first 10): {np.round(beat_times[:10], 2).tolist() if isinstance(beat_times, np.ndarray) else []}")
        print(f"    Onset Times (first 10): {np.round(onset_times[:10], 2).tolist() if isinstance(onset_times, np.ndarray) else []}")
        print(f"    Energy Points (first 5): {simplified_energy_values_at_times[:5]}")
        print(f"    Duration: {duration:.2f}s")
        print("  --- End Audio Analysis Summary ---")

        return_data = {
            "path": audio_path,
            "tempo": float(actual_tempo_scalar),
            "beat_times": beat_times.tolist() if isinstance(beat_times, np.ndarray) else [],
            "onset_times": onset_times.tolist() if isinstance(onset_times, np.ndarray) else [],
            "duration": float(duration),
            "simplified_energy_values_at_times": simplified_energy_values_at_times
        }
        print("  Successfully constructed audio return_data dictionary.")
        return return_data

    except Exception as e:
        print(f"ERROR in analyze_audio for {audio_path}: {e}")
        print("Full Traceback:")
        traceback.print_exc()
        return None

if __name__ == '__main__':
    # Example usage:
    import os
    if not os.path.exists("output"): os.makedirs("output", exist_ok=True)
    input_audio_dir = "input_audio"
    if not os.path.exists(input_audio_dir): os.makedirs(input_audio_dir, exist_ok=True)
    
    # Create a dummy audio file if none exists (for testing)
    dummy_audio_file_path = os.path.join(input_audio_dir, "dummy_test_audio.wav")
    if not os.path.exists(dummy_audio_file_path):
        try:
            print(f"Creating dummy audio file: {dummy_audio_file_path}")
            sr_dummy = 22050
            duration_dummy = 5 # seconds
            frequency_dummy = 440 # A4 note
            t_dummy = np.linspace(0, duration_dummy, int(sr_dummy * duration_dummy), False)
            note_dummy = 0.5 * np.sin(2 * np.pi * frequency_dummy * t_dummy)
            # Add some clicks for beats
            for i in range(duration_dummy):
                note_dummy[i*sr_dummy : i*sr_dummy+100] += np.random.rand(100)*0.3
            import soundfile as sf
            sf.write(dummy_audio_file_path, note_dummy, sr_dummy)
            print("Dummy audio created.")
        except Exception as ex_audio:
            print(f"Could not create dummy audio file: {ex_audio}. Please add an audio file to 'input_audio'.")


    test_audio_files = [f for f in os.listdir(input_audio_dir) if f.lower().endswith(('.mp3', '.wav', '.aac'))]
    if test_audio_files:
        print(f"Testing with audio file: {test_audio_files[0]}")
        audio_data_result = analyze_audio(os.path.join(input_audio_dir, test_audio_files[0]))
        if audio_data_result:
            print("\n--- Audio Analysis Result (from test block) ---")
            for key, value in audio_data_result.items():
                if isinstance(value, list):
                    if len(value) > 10:
                        print(f"  {key}: {str(value[:10])[:100]}... (and {len(value)-10} more elements)")
                    else:
                        print(f"  {key}: {str(value)[:100]}")
                elif isinstance(value, (float, int)):
                     print(f"  {key}: {value:.2f}" if isinstance(value, float) else f"  {key}: {value}")
                else:
                    print(f"  {key}: {str(value)[:100]}")

            # Try saving to JSON as a test
            try:
                class NpEncoder(json.JSONEncoder): # Copied from main_editor.py for standalone test
                    def default(self, obj):
                        if isinstance(obj, np.integer): return int(obj)
                        if isinstance(obj, np.floating): return float(obj)
                        if isinstance(obj, np.ndarray): return obj.tolist()
                        return super(NpEncoder, self).default(obj)
                with open("output/test_audio_analysis.json", "w") as f_json:
                    json.dump(audio_data_result, f_json, indent=2, cls=NpEncoder)
                print("Test audio analysis saved to output/test_audio_analysis.json")
            except Exception as e_json:
                print(f"Error saving test audio analysis to JSON: {e_json}")

        else:
            print("Audio analysis returned None in test block.")
    else:
        print(f"No audio files found in '{input_audio_dir}/' for testing audio_analyzer.py. Please add one.")
