# Save as: weather_checker.py

import requests
from bs4 import BeautifulSoup

def check_weather(city="Tamluk"):
    url = f"https://www.timeanddate.com/weather/India/{city}"
    
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find temperature (site structure may change)
        temp_element = soup.find(class_='h2')
        
        if temp_element:
            print(f"Current temperature in {city.title()}: {temp_element.text.strip()}")
        else:
            # Fallback search
            print("Could not find temperature. Here's some page info:")
            print(f"Title: {soup.title.text}")
            
    except Exception as e:
        print(f"Error: {e}")

# Run it
check_weather("Tamluk")
