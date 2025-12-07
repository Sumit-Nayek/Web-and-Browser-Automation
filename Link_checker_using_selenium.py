# Save as: link_checker.py

from selenium import webdriver
from selenium.webdriver.common.by import By

def check_links(url):
    driver = webdriver.Chrome()
    
    try:
        driver.get(url)
        links = driver.find_elements(By.TAG_NAME, "a")
        
        print(f"Found {len(links)} links on {url}\n")
        
        # Print first 10 links
        for i, link in enumerate(links[:10], 1):
            text = link.text[:50]  # First 50 chars
            href = link.get_attribute("href")
            print(f"{i}. Text: {text}")
            print(f"   Link: {href}\n")
            
    finally:
        driver.quit()

# Run it
check_links("https://www.python.org")