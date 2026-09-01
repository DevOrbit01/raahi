import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_api():
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://baanknet.com",
        "Referer": "https://baanknet.com/property-listing",
    })

    # 1. Get CSRF Token
    print("Getting CSRF token...")
    try:
        home = session.get("https://baanknet.com/eauction-psb/home", timeout=30)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(home.text, "html.parser")
        csrf_meta = soup.find("meta", {"name": "_csrf"})
        if csrf_meta:
            csrf_token = csrf_meta["content"]
            session.headers["X-CSRF-TOKEN"] = csrf_token
            print(f"CSRF Token: {csrf_token}")
        else:
            print("No CSRF token found in meta tags")
    except Exception as e:
        print(f"Error getting home page: {e}")

    # 2. Call the API
    url = "https://baanknet.com/eauction-psb/api/property-listing-data/1?page=0&size=10"
    payload = {
        "state": "Andhra Pradesh",
        "stateId": 2,
        "cityId": None,
        "city": "",
        "searchType": "",
        "priceFrom": "0",
        "priceTo": "1000000000",
        "sortBy": "3"
    }

    print(f"Calling API: {url}")
    try:
        resp = session.post(url, json=payload, timeout=30)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data:
                items = data["data"]
                print(f"Found {len(items)} items")
                if items:
                    first = items[0]
                    print("First item sample:", json.dumps(first, indent=2))
                    
                    # Test detail API
                    prop_id = first.get("propertyId")
                    if prop_id:
                        detail_url = f"https://baanknet.com/eauction-psb/api/view-property-detail/{prop_id}/1"
                        print(f"Calling Detail API: {detail_url}")
                        d_resp = session.get(detail_url)
                        if d_resp.status_code == 200:
                            d_data = d_resp.json()
                            if "respData" in d_data:
                                rd = d_data["respData"]
                                print("RespData keys:", rd.keys())
                                if "auctionDetails" in rd:
                                    print("Auction Details:", json.dumps(rd["auctionDetails"], indent=2))
                        else:
                            print(f"Detail API failed: {d_resp.status_code}")

            else:
                print("Unexpected JSON structure:", data.keys())
        else:
            print("Response:", resp.text)
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    test_api()
