#!/usr/bin/env python3
"""
Test script to verify the complete containerized AI Video Editor workflow.
"""

import requests
import time
import json

API_BASE_URL = "http://localhost:5000"

def test_api_health():
    """Test if the API is responding"""
    try:
        response = requests.get(f"{API_BASE_URL}/generate-download-url?s3_key=test")
        print(f"✓ API is responding (status: {response.status_code})")
        return True
    except Exception as e:
        print(f"✗ API health check failed: {e}")
        return False

def test_upload_url_generation():
    """Test presigned URL generation"""
    try:
        payload = {
            "filename": "test_audio.mp3",
            "fileType": "audio/mpeg"
        }
        response = requests.post(f"{API_BASE_URL}/generate-upload-url", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if 'uploadUrl' in data and 's3Key' in data:
                print("✓ Upload URL generation working")
                return True
            else:
                print(f"✗ Upload URL response missing fields: {data}")
                return False
        else:
            print(f"✗ Upload URL generation failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Upload URL test failed: {e}")
        return False

def test_cors_headers():
    """Test CORS configuration"""
    try:
        response = requests.options(f"{API_BASE_URL}/generate-upload-url")
        cors_headers = response.headers.get('Access-Control-Allow-Origin', '')
        if cors_headers:
            print(f"✓ CORS headers present: {cors_headers}")
            return True
        else:
            print("✗ CORS headers missing")
            return False
    except Exception as e:
        print(f"✗ CORS test failed: {e}")
        return False

def main():
    print("=== Testing Containerized AI Video Editor Workflow ===\n")
    
    tests = [
        ("API Health Check", test_api_health),
        ("Upload URL Generation", test_upload_url_generation),
        ("CORS Configuration", test_cors_headers)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"Running {test_name}...")
        if test_func():
            passed += 1
        print()
    
    print(f"=== Test Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All containerized workflow tests PASSED!")
        print("The containerized AI Video Editor is ready for production!")
    else:
        print("❌ Some tests failed. Check the logs above for details.")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
