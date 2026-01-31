from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time

chrome_options = Options()

chrome_options.add_argument('--user-data-dir=C:/ChromeProfileSelenium/User Data')

# chrome_options.add_argument('--profile-directory=Default')
chrome_options.add_argument("--profile-directory=Profile 1")

driver = webdriver.Chrome(options=chrome_options)

time.sleep(5)

print(driver.execute_script("return navigator.userAgent"))

driver.quit()