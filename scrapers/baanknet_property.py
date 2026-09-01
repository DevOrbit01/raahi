import requests
from bs4 import BeautifulSoup
import urllib3
import json
import concurrent.futures
from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_property_media_urls(session, property_id):
    try:
        media_url = f"https://baanknet.com/eauction-psb/api/get-property-media/{property_id}"
        resp = session.get(media_url, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        media_items = data.get("respData", data)
        urls = []
        items = media_items if isinstance(media_items, list) else [media_items]
        for item in items:
            if not isinstance(item, dict):
                continue
            path = (
                item.get("filePath")
                or item.get("mediaPath")
                or item.get("path")
                or item.get("url")
            )
            if not path:
                continue
            if path.startswith("http://") or path.startswith("https://"):
                urls.append(path)
            else:
                urls.append("https://d14q55p4nerl4m.cloudfront.net/" + path.lstrip("/"))
        return urls
    except Exception:
        return []

def scrape_single_property(session, item, state):
    """Scrape a single property from JSON item"""
    try:
        property_id = str(item.get("propertyId"))
        if not property_id:
            return None

        # Fetch details for EMD and other missing fields
        detail_url = f"https://baanknet.com/eauction-psb/api/view-property-detail/{property_id}/1"
        try:
            d_resp = session.get(detail_url, timeout=30)
            details = d_resp.json().get("respData", {}) if d_resp.status_code == 200 else {}
        except:
            details = {}

        auction_details = details.get("auctionDetails", {})
        common_details = details.get("commonPropertyDetails", {})
        
        # Basic fields from list item
        name = item.get("propertySubType", "") + " for sale in " + item.get("localities", "") + " " + item.get("city", "")
        scheme_name = (item.get("projectName") or name) + " BANK AUCTION"
        
        # Fields from details (preferred) or list item
        reserve_price = auction_details.get("ReservePrice", item.get("price", 0))
        emd = auction_details.get("EMD", 0)
        
        # Dates
        auction_date = item.get("auctionStartDateTime", "").split(' ')[0] # Extract date part
        
        # Media
        media_urls = get_property_media_urls(session, property_id)
        
        # Construct Notice URL
        notice_url = f"https://baanknet.com/view-property-detail/{property_id}"

        return {
            "newListingId": "",
            "schemeName": scheme_name.upper(),
            "name": name,
            "category": item.get("propertySubType", ""),
            "state": state,
            "city": item.get("city", ""),
            "areaTown": item.get("districtname", ""),
            "date": auction_date,
            "reservePrice": reserve_price,
            "emd": emd,
            "incrementBid": "0", # Not available in API
            "bankName": item.get("bankName", ""),
            "branchName": common_details.get("branchName", ""),
            "contactDetails": "",
            "description": item.get("summaryDesc", ""),
            "address": item.get("address", ""),
            "note": "",
            "borrowerName": details.get("coBorrowerNames", ""), # or from commonDetails
            "publishingDate": item.get("postedOn", ""),
            "inspectionDate": item.get("inspectionStartDateTime", ""),
            "applicationSubmissionDate": item.get("emdEndDateTime", ""),
            "auctionStartDate": item.get("auctionStartDateTime", ""),
            "auctionEndTime": item.get("auctionEndDateTime", ""),
            "auctionType": "Bank Auction",
            "listingId": item.get("bankPropertyId", property_id),
            "images": ",".join(media_urls),
            "notice": notice_url,
            "source": "baanknet_property",
            "url": notice_url,
        }

    except Exception as e:
        print(f"[BaankNet Property] Error parsing item {item.get('propertyId')}: {e}")
        return None

def scrape(state, progress_callback=None):
    print(f"[BaankNet Property] Starting scrape for {state}")
    
    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet Property] State {state} not supported")
        return []
    
    state_id = BAANKNET_STATE_IDS[state]

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
    print("[BaankNet Property] Establishing session...")
    try:
        home = session.get("https://baanknet.com/eauction-psb/home", timeout=30)
        soup = BeautifulSoup(home.text, "html.parser")
        csrf_meta = soup.find("meta", {"name": "_csrf"})
        if not csrf_meta:
            print("[BaankNet Property] No CSRF token found")
            return []
        csrf_token = csrf_meta["content"]
        session.headers["X-CSRF-TOKEN"] = csrf_token
    except Exception as e:
        print(f"[BaankNet Property] Connection error: {e}")
        return []

    url = "https://baanknet.com/eauction-psb/api/property-listing-data/1"
    all_properties = []
    
    # 2. Iterate Pages
    page = 0
    size = 100 # Use larger size for efficiency
    max_pages = 100 # Safety limit
    
    while page <= max_pages:
        query_params = f"?page={page}&size={size}"
        full_url = url + query_params
        
        payload = {
            "state": state,
            "stateId": int(state_id),
            "cityId": None,
            "city": "",
            "searchType": "",
            "priceFrom": "0",
            "priceTo": "1000000000",
            "sortBy": "3"
        }
        
        print(f"[BaankNet Property] Fetching page {page}...")
        if progress_callback:
            progress_callback(f"Fetching page {page}...")
            
        try:
            resp = session.post(full_url, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet Property] Page {page} failed with status {resp.status_code}")
                break
                
            data = resp.json()
            items = data.get("data", [])
            
            if not items:
                print(f"[BaankNet Property] No more items found on page {page}")
                break
                
            print(f"[BaankNet Property] Found {len(items)} items on page {page}")
            
            # Use ThreadPoolExecutor for parallel processing of details/media
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(scrape_single_property, session, item, state) for item in items]
                for future in concurrent.futures.as_completed(futures):
                    prop = future.result()
                    if prop:
                        all_properties.append(prop)
            
            # Check for pagination end
            total_count = data.get("totalCount", 0)
            fetched_count = (page + 1) * size
            if fetched_count >= total_count:
                print(f"[BaankNet Property] Reached total count {total_count}")
                break
            
            page += 1
            
        except Exception as e:
            print(f"[BaankNet Property] Error fetching page {page}: {e}")
            break
            
    print(f"[BaankNet Property] Finished. Total properties: {len(all_properties)}")
    return all_properties
