import os
import sys
import threading
import logging
import time
from pathlib import Path
from selenium import webdriver

# Constants
DEFAULT_WINDOW_SIZE = (600, 800)
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def get_chrome_version():
    """Get the installed Chrome version."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version, _ = winreg.QueryValueEx(key, "version")
        return int(version.split('.')[0])
    except:
        # Fallback: try to detect from common paths
        try:
            import subprocess
            result = subprocess.run(['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'version' in line.lower():
                        version = line.split()[-1]
                        return int(version.split('.')[0])
        except:
            pass
        return None

def get_resource_path(relative_path: str, external: bool = False) -> str:
    """Get the absolute path to a resource, handling both development and packaged environments."""
    if getattr(sys, "frozen", False):
        base_path = sys.executable if external else sys._MEIPASS
    else:
        base_path = Path(__file__).parent.parent

    return str(Path(base_path) / relative_path)

def setup_chrome_options(
    extension_path: str = None,
    chrome_exe_path: str = None,
    headless: bool = False,
    window_size: tuple = DEFAULT_WINDOW_SIZE,
    window_position: tuple = (0, 0),
    user_agent: str = None,
    profile_path: str = None
) -> webdriver.ChromeOptions:
    """Set up Chrome options for the driver."""
    options = webdriver.ChromeOptions()

    # Add extension if provided
    if extension_path and Path(extension_path).exists():
        options.add_argument(f"--load-extension={extension_path}")
        options.add_argument(f"--disable-extensions-except={extension_path}")

    # Set binary location if provided
    if chrome_exe_path and Path(chrome_exe_path).exists():
        options.binary_location = chrome_exe_path

    # Window settings
    options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")
    options.add_argument(f"--window-position={window_position[0]},{window_position[1]}")
    options.add_argument("--force-device-scale-factor=1")

    # Other arguments
    options.add_argument("--lang=vi-VN,en-US,en")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if user_agent:
        options.add_argument(f"--user-agent={user_agent}")
    if headless:
        options.add_argument("--headless=new")
    if profile_path:
        options.add_argument(f"--user-data-dir={profile_path}")

    return options

def create_chrome_driver(
    proxy: str = None,
    headless_mode: bool = False,
    window_position: tuple = (0, 0),
    user_agent: str = None,
    width: int = 600,
    height: int = 800,
    thread_name: str = None,
) -> webdriver.Chrome:
    """Create and configure a Chrome WebDriver instance.

    Args:
        proxy: Proxy server address (not implemented yet)
        headless_mode: Run browser in headless mode
        window_position: Tuple of (x, y) coordinates for window position
        user_agent: Custom user agent string
        width: Browser window width
        height: Browser window height
        thread_name: Name of the thread for profile isolation

    Returns:
        Configured Chrome WebDriver instance or None if initialization fails
    """
    if not thread_name:
        thread_name = threading.current_thread().name

    # Validate parameters
    if width <= 0 or height <= 0:
        logging.error(f"Thread {thread_name} - Invalid window dimensions: {width}x{height}")
        return None

    try:
        # Setup paths
        extension_path = r"D:\Salon\GG Sea\RektCaptcha_Extension"
        chrome_exe_path = r"D:\Salon\GG Sea\chrome-win64\chrome.exe"
        driver_path = get_resource_path("tools/chromedriver.exe", external=True)

        # Create profile path - new profile each run
        app_data_path = os.getenv("LOCALAPPDATA", Path.home())
        profile_path = Path(app_data_path) / "TSEO_Profiles" / f"Profile_{thread_name}_{int(time.time())}"
        profile_path.mkdir(parents=True, exist_ok=True)

        # Setup options
        options = setup_chrome_options(
            extension_path=extension_path,
            chrome_exe_path=chrome_exe_path,
            headless=headless_mode,
            window_size=(width, height),
            window_position=window_position,
            user_agent=user_agent or DEFAULT_USER_AGENT,
            profile_path=str(profile_path)
        )

        # Note: Selenium webdriver handles Chrome version compatibility automatically

        # Initialize driver
        driver = webdriver.Chrome(
            options=options,
            executable_path=driver_path if Path(driver_path).exists() else None,
        )

        # Set window properties
        if not headless_mode:
            try:
                driver.set_window_rect(x=window_position[0], y=window_position[1], width=width, height=height)
            except Exception as e:
                logging.warning(f"Thread {thread_name} - Could not set window rect: {e}")
                try:
                    driver.set_window_size(width, height)
                    driver.set_window_position(*window_position)
                except Exception as e2:
                    logging.warning(f"Thread {thread_name} - Could not set window size/position: {e2}")

        # Custom quit method
        original_quit = driver.quit
        def custom_quit():
            logging.info(f"Thread {thread_name} - Closing driver...")
            try:
                original_quit()
            except Exception as e:
                logging.error(f"Thread {thread_name} - Error during driver quit: {e}")
        driver.quit = custom_quit

        logging.info(f"Thread {thread_name} - Chrome driver initialized successfully")
        return driver

    except Exception as e:
        logging.error(f"Thread {thread_name} - Failed to initialize Chrome driver: {e}")
        return None

# Alias for backward compatibility
get_driver_chrome = create_chrome_driver

if __name__ == "__main__":
    # Demo/Test when running the script directly
    import logging
    import time
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    print("🚀 Testing Chrome Driver Setup...")
    print("This will attempt to create a Chrome driver in headless mode.")
    print("Note: This may take 10-30 seconds on first run...")

    start_time = time.time()

    try:
        print("⏳ Initializing Chrome driver...")
        driver = create_chrome_driver(
            headless_mode=False,  # Set to False to show browser window for testing
            width=800,
            height=600,
            thread_name="demo_thread"
        )

        if driver:
            init_time = time.time() - start_time
            print(f"✅ Chrome driver created successfully in {init_time:.1f}s")
            print(f"   Window size: {driver.get_window_size()}")
            print("   Navigating to test page...")

            # Test navigation
            driver.get("https://www.google.com/recaptcha/api2/demo")
            print(f"   Page title: {driver.title}")

            # Keep browser open for testing
            print("   Browser is open. Press Enter to close...")
            input()

            # Clean up
            driver.quit()
            total_time = time.time() - start_time
            print(f"✅ Test completed successfully in {total_time:.1f}s")
        else:
            print("❌ Failed to create Chrome driver")
            print("💡 Possible issues:")
            print("   - Chrome browser not installed")
            print("   - undetected-chromedriver not properly installed")
            print("   - Missing dependencies")

    except Exception as e:
        print(f"❌ Error during testing: {e}")
    print("💡 Troubleshooting tips:")
    print("   1. Make sure Google Chrome is installed")
    print("   2. Run: pip install selenium")
    print("   3. Check if Chrome is up to date")
    import traceback
    traceback.print_exc()
