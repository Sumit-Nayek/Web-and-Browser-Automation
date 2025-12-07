# Save as: bs4_scraping.py
# Run: Press F5 in IDLE

import requests
from bs4 import BeautifulSoup

print("Fetching webpage...")

# Get webpage content
url = "https://books.toscrape.com/"  # Free practice site
response = requests.get(url)

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract page title
    title = soup.title.text
    print(f"Page Title: {title}")
    
    # Extract all book titles (first 5)
    books = soup.find_all('h3')[:5]
    print("\nFirst 5 Books:")
    for i, book in enumerate(books, 1):
        print(f"{i}. {book.a['title']}")
    
    # Extract all links
    links = soup.find_all('a')[:10]
    print("\nFirst 10 Links:")
    for i, link in enumerate(links, 1):
        href = link.get('href', 'No href')
        text = link.text.strip()[:30]  # First 30 chars
        print(f"{i}. {text} -> {href}")
        
else:
    print(f"Failed to fetch page. Status code: {response.status_code}")
