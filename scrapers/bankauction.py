"""BankAuctions.in scraper"""
import requests
from bs4 import BeautifulSoup
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CITIES = ["Ahemdabad", "Delhi", "Mumbai", "Pune", "Jaipur", "Surat", "Vadodara"]

# City to State mapping
CITY_TO_STATE = {
    "Ahemdabad": "Gujarat",
    "Delhi": "Delhi",
    "Mumbai": "Maharashtra",
    "Pune": "Maharashtra",
    "Jaipur": "Rajasthan",
    "Surat": "Gujarat",
    "Vadodara": "Gujarat"
}

def scrape(state, progress_callback=None):
    try:
        print(f"[BankAuction.in] Starting scrape for {state}")
        
        url = "https://bankauctions.in/wp-json/eauc-table/v1/home_page"

        response = requests.post(url, timeout=30)
        response.raise_for_status()
        
        result = response.json()
        items = result.get('data', [])
        total_items = len(items)

        properties = []

        for i, item in enumerate(items):
            item_city = item.get('city', '')
            
            # Skip if city not in our list
            if item_city not in CITIES:
                continue
            
            # Skip if the city doesn't belong to the selected state
            if CITY_TO_STATE.get(item_city) != state:
                continue

            property_url = item.get('url', '').strip()
            print(property_url)

            prop_response = requests.get(property_url, timeout=30)
            prop_soup = BeautifulSoup(prop_response.text, 'html.parser')

            def get_text(selector):
                elem = prop_soup.select_one(selector)
                return elem.text.strip() if elem else ""

            listing_id = get_text(".table > tbody:nth-child(1) > tr:nth-child(1) > td:nth-child(2)")
            name = get_text(".entry-title")
            property_type = get_text(".table > tbody:nth-child(1) > tr:nth-child(8) > td:nth-child(2)")
            city = get_text(".table > tbody:nth-child(1) > tr:nth-child(11) > td:nth-child(2)")
            d = get_text(".table > tbody:nth-child(1) > tr:nth-child(19) > td:nth-child(2)")
            
            # Determine state from city
            property_state = CITY_TO_STATE.get(item.get('city'), state)

            bank_name = get_text(".table > tbody:nth-child(1) > tr:nth-child(3) > td:nth-child(2)")
            reserve_price = get_text(".table > tbody:nth-child(1) > tr:nth-child(14) > td:nth-child(2) > span:nth-child(1)").replace('₹', '').replace(',', '').strip()
            emd = get_text(".table > tbody:nth-child(1) > tr:nth-child(15) > td:nth-child(2) > span:nth-child(1)").replace('₹', '').replace(',', '').strip()
            branch_name = get_text(".table > tbody:nth-child(1) > tr:nth-child(4) > td:nth-child(2)")
            incrementBid = get_text(".table > tbody:nth-child(1) > tr:nth-child(16) > td:nth-child(2)").replace('₹', '').replace(',', '').strip()

            contact_details = get_text(".table > tbody:nth-child(1) > tr:nth-child(5) > td:nth-child(2)")
            description = get_text(".table > tbody:nth-child(1) > tr:nth-child(10) > td:nth-child(2)")
            borrower_name = get_text(".table > tbody:nth-child(1) > tr:nth-child(7) > td:nth-child(2)")
            auction_end_time = get_text(".table > tbody:nth-child(1) > tr:nth-child(20) > td:nth-child(2)")
            auction_type = get_text(".table > tbody:nth-child(1) > tr:nth-child(2) > td:nth-child(2)")
            application_submission_date = get_text(".table > tbody:nth-child(1) > tr:nth-child(22) > td:nth-child(2)")
            
            notice_elem = prop_soup.select_one(".table > tbody:nth-child(1) > tr:nth-child(23) > td:nth-child(2) > a:nth-child(1)")
            notice = notice_elem.get("href").strip() if notice_elem else ""

            property_data = {
                "newListingId": "",
                "schemeName": f"{name} BANK AUCTION".upper(),
                "name": name,
                "category": property_type,
                "state": property_state,
                "city": city,
                "areaTown": "",
                "date": d,
                "reservePrice": float(reserve_price) if reserve_price else 0,
                "emd": float(emd) if emd else 0,
                "incrementBid": incrementBid if incrementBid else 0,
                "bankName": bank_name,
                "branchName": branch_name,
                "contactDetails": contact_details,
                "description": description,
                "address": "",
                "note": "",
                "borrowerName": borrower_name,
                "publishingDate": "",
                "inspectionDate": "",
                "applicationSubmissionDate": application_submission_date,
                "auctionStartDate": d,
                "auctionEndTime": auction_end_time,
                "auctionType": auction_type,
                "listingId": listing_id,
                "images": "",
                "notice": notice or "",
                "source": "bankauctions.in",
                "url": property_url,
            }
            
            properties.append(property_data)
            print(f"[BankAuction.in] Scraped property: {name}")

    except Exception as e:
        print(f"[BankAuction.in] ❌ Error during scraping for {state}: {e}")
        import traceback
        traceback.print_exc()
        return []

    print(f"[BankAuctions] Completed scraping {state}. Total properties: {len(properties)}")
    return properties