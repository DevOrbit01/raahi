"""BaankNet scraper (fixed automatic session + csrf)"""
import requests
from bs4 import BeautifulSoup
import urllib3
from config import BAANKNET_STATE_IDS
import concurrent.futures

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


def scrape_single_property_baanknet(session, card, state, i, total):
    """Scrape a single property from baanknet"""
    try:
        link = card.find("a", href=lambda h: h and "view-property" in h)
        if not link:
            return None

        property_id = ""
        import re
        match = re.search(r"/view-property/(\d+)", link["href"])
        if match:
            property_id = match.group(1)

        link2 = card.find("a", href=lambda h: h and "view-auction-notice" in h)
        if not link2:
            return None

        detail_url = f"https://baanknet.com/eauction-psb/api/view-property-detail/{property_id}/1"
        details = session.get(detail_url, timeout=30).json().get("respData", {})

        # Check if name is empty, skip if it is
        name = details.get("propertyType", "").strip() + " for sale in " + details.get("locality", "").strip() + " " + details.get("city", "").strip()
        if not name:
            return None

        notice = f"https://baanknet.com{link2['href']}"

        media_urls = get_property_media_urls(session, property_id)

        resp = session.get(notice, timeout=30)
        soup = BeautifulSoup(resp.text, "html.parser")

        inspectionDate = soup.select_one("#xMainContentAfterLoginDiv > div.card > div.card-body.p-0 > form > div > div > div:nth-child(5) > div.from-details-content > div > div:nth-child(1) > div > div > div > div")
        if inspectionDate:
            inspectionDate = inspectionDate.text.strip()
        else:
            inspectionDate = ""

        incrementBid = soup.select_one("#xMainContentAfterLoginDiv > div.card > div.card-body.p-0 > form > div > div > div:nth-child(7) > div.from-details-content > div > div:nth-child(4) > div > div > div > div")
        if incrementBid:
            incrementBid = incrementBid.text.strip().replace(',', '')
        else:
            incrementBid = "0"

        # Build dict
        auction_details = details.get("auctionDetails", {})
        common_details = details.get("commonPropertyDetails", {})
        dept = common_details.get("department", {})

        return {
            "newListingId": "",
            "schemeName": f"{name} BANK AUCTION".upper(),
            "name": name,
            "category": details.get("propertyType", ""),
            "state": state,
            "city": details.get("city", ""),
            "areaTown": common_details.get("districtId", {}).get("districtname", ""),
            "date": auction_details.get("Auctionstartdate", ""),
            "reservePrice": auction_details.get("ReservePrice", 0),
            "emd": auction_details.get("EMD", 0),
            "incrementBid": incrementBid,
            "bankName": details.get("bankName", ""),
            "branchName": dept.get("departmentName", ""),
            "contactDetails": dept.get("phoneNo", ""),
            "description": common_details.get("address", dept.get("summaryDesc", "")),
            "address": "",
            "note": "",
            "borrowerName": common_details.get("borrowerName", ""),
            "publishingDate": common_details.get("verifiedOn", ""),
            "inspectionDate": inspectionDate,
            "applicationSubmissionDate": auction_details.get("paymentEndDate", ""),
            "auctionStartDate": auction_details.get("Auctionstartdate", ""),
            "auctionEndTime": auction_details.get("AuctionEndDate", ""),
            "auctionType": details.get("typeOfAction", ""),
            "listingId": details.get("bankPropertyId", ""),
            "images": ",".join(media_urls)
            if media_urls
            else "https://d14q55p4nerl4m.cloudfront.net/" + details.get("propertyPhoto", ""),
            "notice": notice,
            "source": "baanknet",
            "url": link["href"],
        }
    except Exception as e:
        print(f"[BaankNet] ❌ Error scraping property {i+1}/{total}: {str(e)[:100]}")
        if i < 3:  # Print detailed error for first 3 failures
            print(f"[BaankNet] 🔍 Error details: {e}")
            import traceback
            traceback.print_exc()
        return None


def scrape(state, progress_callback=None):
    print(f"[BaankNet] Starting scrape for {state}")

    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet] State {state} not supported")
        return []

    # Create session (IMPORTANT)
    session = requests.Session()
    session.verify = False

    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://baanknet.com/eauction-psb/home",
    })

    # ------------------------------------------------------------
    # 1️⃣ Step 1 — Load any page to get fresh JSESSIONID & XSRF-TOKEN
    # ------------------------------------------------------------
    print("[BaankNet] Establishing session…")
    home = session.get("https://baanknet.com/eauction-psb/home", timeout=30)

    soup = BeautifulSoup(home.text, "html.parser")
    csrf_meta = soup.find("meta", {"name": "_csrf"})

    if not csrf_meta:
        print("[BaankNet] ERROR: Could not find CSRF meta tag")
        return []

    csrf_token = csrf_meta["content"]
    print("[BaankNet] CSRF token:", csrf_token)

    # For Spring Security, you must send TOKEN in header
    session.headers["X-CSRF-TOKEN"] = csrf_token

    # ------------------------------------------------------------
    # 2️⃣ Step 2 — AJAX filter POST - Get first page to find total pages
    # ------------------------------------------------------------
    main_url = "https://baanknet.com/eauction-psb/ajax/search-auction"

    data = {
        "currentPage": "1",
        "perPage": "200",
        "aucXstatus": "1",
        "searchType": "1",
        "stateId": BAANKNET_STATE_IDS[state],
        "_csrf": csrf_token,   # MUST MATCH COOKIE VALUE
    }

    print("[BaankNet] Sending POST request to get first page and total pages…")

    resp = session.post(main_url, json=data, timeout=30)
    if resp.status_code != 200:
        print(f"[BaankNet] ERROR: POST failed ({resp.status_code})")
        print(resp.text[:500])
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Get total number of pages from #pageTot
    page_tot_elem = soup.select_one("#pageTot")
    total_pages = 1
    if page_tot_elem:
        try:
            total_pages = int(page_tot_elem.text.strip())
            print(f"[BaankNet] Found {total_pages} total pages for {state}")
        except:
            print(f"[BaankNet] Could not parse total pages, defaulting to 1")
            total_pages = 1
    else:
        print(f"[BaankNet] #pageTot not found, defaulting to 1 page")
    
    # Collect all cards from all pages
    all_cards = []
    
    for page_num in range(1, total_pages + 1):
        try:
            print(f"[BaankNet] Fetching page {page_num}/{total_pages}...")
            
            data["currentPage"] = str(page_num)
            
            resp = session.post(main_url, json=data, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet] ERROR: Failed to fetch page {page_num}")
                continue
            
            soup = BeautifulSoup(resp.text, "html.parser")
            list_container = soup.find(class_="list-container")
            
            if not list_container:
                print(f"[BaankNet] No list container found on page {page_num}")
                continue
            
            cards = list_container.find_all("div", recursive=False)
            all_cards.extend(cards)
            print(f"[BaankNet] ✓ Found {len(cards)} cards on page {page_num} (Total: {len(all_cards)})")
            
        except Exception as e:
            print(f"[BaankNet] Error fetching page {page_num}: {e}")
            continue
    
    print(f"[BaankNet] Collected {len(all_cards)} total cards from {total_pages} pages")
    print(f"[BaankNet] Starting parallel property scraping with 10 threads...")

    properties = []

    # ------------------------------------------------------------
    # 3️⃣ Step 3 — Scrape all properties in parallel
    # ------------------------------------------------------------
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape_single_property_baanknet, session, card, state, i, len(all_cards)): i 
                  for i, card in enumerate(all_cards)}
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            
            if progress_callback:
                progress_callback(f"[BaankNet] Scraping {completed}/{len(all_cards)}")
            
            if result:
                properties.append(result)
                if completed % 10 == 0 or completed == 1:
                    print(f"[BaankNet] ✓ Scraped {completed}/{len(all_cards)} properties (Successful: {len(properties)})")

    print(f"[BaankNet] Completed scraping {state}: {len(properties)} records")
    return properties
