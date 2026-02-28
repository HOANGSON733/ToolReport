#!/usr/bin/env python3
"""
Thorough testing script for the improved test.py Chrome driver setup.
Tests parameter validation, path handling, and error conditions.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import logging

# Add current directory to path to import test.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the functions to test
from test import get_resource_path, setup_chrome_options, create_chrome_driver, DEFAULT_CHROME_VERSION

class TestChromeDriverSetup(unittest.TestCase):
    """Test cases for Chrome driver setup functions."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_resource_path_development(self):
        """Test get_resource_path in development environment."""
        with patch('sys.frozen', False, create=True):
            with patch('sys._MEIPASS', self.temp_dir, create=True):
                result = get_resource_path("test/file.txt")
                expected = str(Path(__file__).parent.parent / "test" / "file.txt")
                self.assertEqual(result, expected)

    def test_get_resource_path_frozen_external(self):
        """Test get_resource_path in frozen environment with external=True."""
        with patch('sys.frozen', True, create=True):
            with patch('sys.executable', '/fake/path/app.exe'):
                result = get_resource_path("test/file.txt", external=True)
                self.assertEqual(result, "/fake/path/test/file.txt")

    def test_get_resource_path_frozen_internal(self):
        """Test get_resource_path in frozen environment with external=False."""
        with patch('sys.frozen', True, create=True):
            with patch('sys._MEIPASS', '/fake/meipass'):
                result = get_resource_path("test/file.txt", external=False)
                self.assertEqual(result, "/fake/meipass/test/file.txt")

    def test_setup_chrome_options_basic(self):
        """Test basic Chrome options setup."""
        options = setup_chrome_options()
        self.assertIsNotNone(options)
        # Check that some default arguments are present
        args_str = str(options.arguments)
        self.assertIn("--lang=vi-VN,en-US,en", args_str)
        self.assertIn("--disable-notifications", args_str)

    def test_setup_chrome_options_with_extension(self):
        """Test Chrome options setup with extension."""
        # Create a mock extension directory
        extension_dir = Path(self.temp_dir) / "test_extension"
        extension_dir.mkdir()

        options = setup_chrome_options(extension_path=str(extension_dir))
        args_str = str(options.arguments)
        self.assertIn(f"--load-extension={extension_dir}", args_str)
        self.assertIn(f"--disable-extensions-except={extension_dir}", args_str)

    def test_setup_chrome_options_headless(self):
        """Test Chrome options setup in headless mode."""
        options = setup_chrome_options(headless=True)
        args_str = str(options.arguments)
        self.assertIn("--headless=new", args_str)

    def test_setup_chrome_options_user_agent(self):
        """Test Chrome options setup with custom user agent."""
        custom_ua = "Custom User Agent"
        options = setup_chrome_options(user_agent=custom_ua)
        args_str = str(options.arguments)
        self.assertIn(f"--user-agent={custom_ua}", args_str)

    def test_create_chrome_driver_invalid_dimensions(self):
        """Test that invalid window dimensions are rejected."""
        with patch('logging.error') as mock_log:
            result = create_chrome_driver(width=0, height=100)
            self.assertIsNone(result)
            mock_log.assert_called_once()

        with patch('logging.error') as mock_log:
            result = create_chrome_driver(width=100, height=-1)
            self.assertIsNone(result)
            mock_log.assert_called_once()

    @patch('undetected_chromedriver.Chrome')
    def test_create_chrome_driver_success(self, mock_chrome):
        """Test successful driver creation."""
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        with patch('pathlib.Path.mkdir'):
            with patch('pathlib.Path.exists', return_value=True):
                result = create_chrome_driver(width=800, height=600, thread_name="test_thread")

        self.assertEqual(result, mock_driver)
        mock_chrome.assert_called_once()

    @patch('undetected_chromedriver.Chrome')
    def test_create_chrome_driver_initialization_failure(self, mock_chrome):
        """Test driver creation failure handling."""
        mock_chrome.side_effect = Exception("Chrome init failed")

        with patch('logging.error') as mock_log:
            with patch('pathlib.Path.mkdir'):
                with patch('pathlib.Path.exists', return_value=True):
                    result = create_chrome_driver(thread_name="test_thread")

        self.assertIsNone(result)
        mock_log.assert_called_once()

    @patch('undetected_chromedriver.Chrome')
    def test_create_chrome_driver_window_rect_failure(self, mock_chrome):
        """Test fallback when set_window_rect fails."""
        mock_driver = MagicMock()
        mock_driver.set_window_rect.side_effect = Exception("set_window_rect failed")
        mock_chrome.return_value = mock_driver

        with patch('logging.warning') as mock_log:
            with patch('pathlib.Path.mkdir'):
                with patch('pathlib.Path.exists', return_value=True):
                    result = create_chrome_driver(width=800, height=600, thread_name="test_thread")

        self.assertEqual(result, mock_driver)
        # Should have called set_window_size and set_window_position as fallback
        mock_driver.set_window_size.assert_called_once_with(800, 600)
        mock_driver.set_window_position.assert_called_once_with(0, 0)

    def test_profile_path_creation(self):
        """Test that profile paths are created correctly."""
        with patch('os.getenv', return_value=self.temp_dir):
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                with patch('undetected_chromedriver.Chrome'):
                    with patch('pathlib.Path.exists', return_value=True):
                        create_chrome_driver(thread_name="test_thread")

                # Check that mkdir was called for the profile directory
                expected_profile_path = Path(self.temp_dir) / "TSEO_Profiles" / "Profile_test_thread"
                mock_mkdir.assert_called_with(parents=True, exist_ok=True)

    def test_constants_defined(self):
        """Test that all required constants are defined."""
        self.assertIsInstance(DEFAULT_CHROME_VERSION, int)
        self.assertGreater(DEFAULT_CHROME_VERSION, 100)  # Reasonable version check

    def test_backward_compatibility(self):
        """Test that get_driver_chrome alias works."""
        from test import get_driver_chrome
        self.assertEqual(get_driver_chrome, create_chrome_driver)

if __name__ == '__main__':
    # Set up logging for tests
    logging.basicConfig(level=logging.DEBUG)

    # Run the tests
    unittest.main(verbosity=2)
