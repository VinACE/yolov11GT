#!/usr/bin/env python3
"""
Comprehensive test script for YOLOv11 Docker setup
Run this script to verify all components are working correctly
"""

import subprocess
import sys
import time
import requests
from pathlib import Path

def run_command(cmd, description):
    """Run a command and return success status"""
    print(f"🔍 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} - ERROR: {e}")
        return False

def test_docker_services():
    """Test Docker services are running"""
    print("\n=== Testing Docker Services ===")
    
    # Check if containers are running
    success = run_command(
        "docker-compose -f docker-compose.yolov11.yml ps --format 'table {{.Name}}\t{{.Status}}'",
        "Check container status"
    )
    
    return success

def test_yolov11_functionality():
    """Test YOLOv11 functionality in container"""
    print("\n=== Testing YOLOv11 Functionality ===")
    
    # Test basic YOLOv11 installation
    success = run_command(
        "docker-compose -f docker-compose.yolov11.yml exec yolov11 python /app/test_yolov11.py",
        "YOLOv11 installation test"
    )
    
    return success

def test_inference():
    """Test inference with sample data"""
    print("\n=== Testing Inference ===")
    
    # Check if sample image exists
    if not Path("data/sample_image.jpg").exists():
        print("⚠️  Sample image not found, creating one...")
        run_command(
            "python3 -c \"import cv2; import numpy as np; img = np.ones((640, 640, 3), dtype=np.uint8) * 255; cv2.rectangle(img, (100, 100), (200, 200), (0, 0, 255), -1); cv2.imwrite('data/sample_image.jpg', img); print('Sample image created')\"",
            "Create sample image"
        )
    
    # Test inference
    success = run_command(
        "docker-compose -f docker-compose.yolov11.yml exec yolov11 python /app/inference.py --image /app/data/sample_image.jpg",
        "Run inference on sample image"
    )
    
    # Check if output was created
    if Path("outputs/result_sample_image.jpg").exists():
        print("✅ Inference output created successfully")
        return success
    else:
        print("❌ Inference output not found")
        return False

def test_jupyter():
    """Test Jupyter Lab service"""
    print("\n=== Testing Jupyter Lab ===")
    
    # Check if Jupyter is accessible
    try:
        response = requests.get("http://localhost:8888", timeout=5)
        if response.status_code in [200, 302]:
            print("✅ Jupyter Lab is accessible")
            return True
        else:
            print(f"❌ Jupyter Lab returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Jupyter Lab not accessible: {e}")
        return False

def test_volume_mounts():
    """Test volume mounting"""
    print("\n=== Testing Volume Mounts ===")
    
    # Test if we can access mounted directories
    success = run_command(
        "docker-compose -f docker-compose.yolov11.yml exec yolov11 ls -la /app/data /app/outputs /app/models",
        "Check mounted directories"
    )
    
    return success

def main():
    """Run all tests"""
    print("🚀 Starting YOLOv11 Docker Setup Tests")
    print("=" * 50)
    
    tests = [
        ("Docker Services", test_docker_services),
        ("YOLOv11 Functionality", test_yolov11_functionality),
        ("Inference", test_inference),
        ("Volume Mounts", test_volume_mounts),
        ("Jupyter Lab", test_jupyter),
    ]
    
    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
        time.sleep(1)  # Small delay between tests
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! YOLOv11 Docker setup is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
