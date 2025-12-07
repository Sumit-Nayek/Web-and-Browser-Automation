# Save as: selenium_basic.py
# Run: Press F5 in IDLE

from selenium import webdriver
from selenium.webdriver.common.by import By
import time

print("Starting browser...")
driver = webdriver.Chrome()  # Make sure chromedriver is in PATH

try:
    # Open Google
    driver.get("https://www.google.com")
    print(f"Page title: {driver.title}")
    
    # Find search box
    search_box = driver.find_element(By.NAME, "q")
    
    # Type search query
    search_box.send_keys("Sumit Nayek")
    print("Typed search query")
    
    # Press Enter
    search_box.submit()
    
    # Wait a bit
    time.sleep(5)
    
    # Print first result
    results = driver.find_elements(By.CSS_SELECTOR, "h3")
    if results:
        print(f"First result: {results[0].text}")
    
    # Take screenshot ("Location will be change for your case")
    driver.save_screenshot(r"C:\Desktop\google_search.png")
    print("Screenshot saved as google_search.png")
    
finally:
    # Always close browser
    driver.quit()
    print("Browser closed")
