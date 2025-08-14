#!/usr/bin/env python3
"""
Test script to check if the API can import and start properly.
"""

try:
    import app
    print("✓ App imports successfully")
    
    flask_app = app.app
    print("✓ Flask app created successfully")
    
    import tasks
    print("✓ Tasks module imports successfully")
    
    import main_editor
    print("✓ Main editor module imports successfully")
    
    print("All imports successful - API should start properly")
    
except Exception as e:
    print(f"✗ Import error: {e}")
    import traceback
    traceback.print_exc()
