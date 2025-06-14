# check_paths.py (modified)
import sys
import os

print("--- sys.path ---")
for p in sys.path:
    print(p)

print("\n--- PYTHON EXECUTABLE ---")
print(sys.executable)

print("\n--- VIRTUAL_ENV environment variable ---")
print(os.getenv('VIRTUAL_ENV'))

try:
    print("\nAttempting to import moviepy...")
    import moviepy
    print(f"  MoviePy Location: {moviepy.__file__}")
    print("  MoviePy imported successfully!")

    print("\nAttempting to import from moviepy.editor...")
    from moviepy.editor import VideoFileClip # Or any other class from .editor
    print("  from moviepy.editor import VideoFileClip -- SUCCESSFUL!")

except ImportError as e:
    print(f"\n--- Import Error ---")
    print(e)
    print("Import FAILED.")
except Exception as e:
    print(f"\n--- GENERAL ERROR DURING IMPORT ---")
    print(e)
