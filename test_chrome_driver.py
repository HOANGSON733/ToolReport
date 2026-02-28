import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Search_keyword import create_chrome_driver

def test_chrome_driver():
    print("Testing Chrome driver initialization...")
    try:
        driver = create_chrome_driver(
            headless_mode=True,
            width=800,
            height=600,
            thread_name="test_thread"
        )
        if driver:
            print("✅ Chrome driver created successfully")
            print(f"   Window size: {driver.get_window_size()}")
            driver.quit()
            print("✅ Chrome driver closed successfully")
            return True
        else:
            print("❌ Failed to create Chrome driver")
            return False
    except Exception as e:
        print(f"❌ Error during Chrome driver test: {e}")
        return False

if __name__ == "__main__":
    success = test_chrome_driver()
    sys.exit(0 if success else 1)
