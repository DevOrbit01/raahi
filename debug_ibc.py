
import requests
from bs4 import BeautifulSoup
import urllib3
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def debug_scrape():
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ibbi.baanknet.com/eauction-ibbi/home",
    })

    print("Establishing session...")
    home = session.get("https://ibbi.baanknet.com/eauction-ibbi/home")
    soup = BeautifulSoup(home.text, "html.parser")
    csrf_meta = soup.find("meta", {"name": "_csrf"})
    if not csrf_meta:
        print("No CSRF token found")
        return
    csrf_token = csrf_meta["content"]
    print(f"CSRF: {csrf_token}")
    session.headers["X-CSRF-TOKEN"] = csrf_token

    url = "https://ibbi.baanknet.com/eauction-ibbi/ajax/search-asset"
    
    # Try different payloads
    payloads = [
        # 1. As implemented
        {
            "currentPage": "1",
            "perPage": "200",
            "astatus": "1",
            "searchType": "1",
            "stateId": "9", # Delhi
            "_csrf": csrf_token,
        },
        # 2. Minimal (as user suggested?)
        {
            "currentPage": "1",
            "stateId": "9",
            "astatus": "1",
            "_csrf": csrf_token,
        }
    ]

    for i, data in enumerate(payloads):
        print(f"\nTesting payload {i+1}: {json.dumps(data)}")
        resp = session.post(url, json=data)
        print(f"Status: {resp.status_code}")
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(".eproc-listing-main")
        print(f"Found {len(cards)} cards")
        
        if len(cards) > 0:
            print("First card full HTML written to debug_card.html")
            with open("debug_card.html", "w", encoding="utf-8") as f:
                f.write(cards[0].prettify())
            
            # Try fetching the page directly
            link = cards[0].find("a", href=lambda h: h and "home-view-asset" in h)
            if link:
                href = link.get("href")
                full_url = "https://ibbi.baanknet.com" + href
                print(f"GET page {full_url}")
                r = session.get(full_url)
                print(f"Status: {r.status_code}")
                if r.status_code == 200:
                    page_soup = BeautifulSoup(r.text, "html.parser")
                    print("Page Title:", page_soup.title.string if page_soup.title else "No title")
                    
                    # Write detail page to file
                    with open("debug_detail.html", "w", encoding="utf-8") as f:
                        f.write(page_soup.prettify())
                    print("Detail page written to debug_detail.html")
            else:
                print("No detail link found in card")
            
            break # Stop after printing one card
        elif len(cards) == 0:
            print("Response preview:", resp.text[:5000])

if __name__ == "__main__":
    debug_scrape()
