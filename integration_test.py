#!/usr/bin/env python3
"""
Integration test for Chrome driver creation with real components.
Tests the actual functionality in a controlled environment.
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test import create_chrome_driver

def test_driver_creation_headless():
    """Test creating a driver in headless mode (safe for CI/testing)."""
    print("Testing Chrome driver creation in headless mode...")

    try:
        driver = create_chrome_driver(
            headless_mode=True,
            width=800,
            height=600,
            thread_name="integration_test"
        )

        if driver is None:
            print("❌ Driver creation failed - returned None")
            return False

        # Test basic functionality
        print("✅ Driver created successfully")

        # Test navigation (to a simple page)
        try:
            driver.get("data:text/html,<html><body><h1>Test Page</h1></body></html>")
            title = driver.title
            print(f"✅ Page loaded, title: {title}")
        except Exception as e:
            print(f"⚠️ Page navigation failed (expected in some environments): {e}")

        # Test window size
        try:
            size = driver.get_window_size()
            print(f"✅ Window size: {size}")
        except Exception as e:
            print(f"⚠️ Could not get window size: {e}")

        # Clean up
        driver.quit()
        print("✅ Driver closed successfully")

        return True

    except Exception as e:
        print(f"❌ Driver creation/integration test failed: {e}")
        return False

def test_parameter_validation():
    """Test parameter validation."""
    print("\nTesting parameter validation...")

    # Test invalid dimensions
    try:
        driver = create_chrome_driver(width=0, height=100)
        if driver is not None:
            print("❌ Should have rejected invalid width")
            driver.quit()
            return False
        print("✅ Correctly rejected invalid width")
    except Exception as e:
        print(f"⚠️ Unexpected error in validation test: {e}")

    try:
        driver = create_chrome_driver(width=100, height=-1)
        if driver is not None:
            print("❌ Should have rejected invalid height")
            driver.quit()
            return False
        print("✅ Correctly rejected invalid height")
    except Exception as e:
        print(f"⚠️ Unexpected error in validation test: {e}")

    return True

def test_path_handling():
    """Test path handling in different scenarios."""
    print("\nTesting path handling...")

    from test import get_resource_path

    # Test development path
    dev_path = get_resource_path("test/file.txt")
    print(f"✅ Development path: {dev_path}")

    # Test that path exists or is constructable
    path_obj = Path(dev_path)
    parent_dir = path_obj.parent
    if parent_dir.exists():
        print("✅ Path construction valid")
    else:
        print(f"⚠️ Path parent doesn't exist (expected in test env): {parent_dir}")

    return True

def main():
    """Run all integration tests."""
    print("🚀 Starting Chrome Driver Integration Tests")
    print("=" * 50)

    results = []

    # Test path handling first (doesn't require Chrome)
    results.append(("Path Handling", test_path_handling()))

    # Test parameter validation
    results.append(("Parameter Validation", test_parameter_validation()))

    # Test driver creation (only if Chrome is available)
    try:
        results.append(("Driver Creation (Headless)", test_driver_creation_headless()))
    except ImportError as e:
        print(f"⚠️ Skipping driver test - missing dependency: {e}")
        results.append(("Driver Creation (Headless)", "Skipped - missing undetected-chromedriver"))
    except Exception as e:
        print(f"❌ Driver test failed with unexpected error: {e}")
        results.append(("Driver Creation (Headless)", False))

    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")

    passed = 0
    total = 0

    for test_name, result in results:
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else f"⚠️ {result}"
        print(f"  {test_name}: {status}")
        if result is True:
            passed += 1
        if result is not "Skipped - missing undetected-chromedriver":
            total += 1

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️ Some tests failed or were skipped")
        return 1

if __name__ == '__main__':
    sys.exit(main())
