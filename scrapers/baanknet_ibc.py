import requests
from bs4 import BeautifulSoup
import urllib3
import json
import concurrent.futures
from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_ibc_property_details(session, detail_url):
    """
    Fetch and parse the detailed property page to get missing fields:
    - Reserve Price
    - EMD
    - Contact Details (Liquidator/IP Name, Phone, Email)
    - Branch Name (if applicable)
    - Detailed Description
    """
    try:
        if not detail_url:
            return {}
            
        resp = session.get(detail_url, timeout=30)
        if resp.status_code != 200:
            return {}
            
        soup = BeautifulSoup(resp.text, "html.parser")
        details = {}
        
        # 1. Reserve Price & EMD
        # Usually in a table or list in the details page
        # Example structure might vary, need generic search
        
        # Look for "Reserve Price" label
        rp_label = soup.find(lambda tag: tag.name == "label" and "Reserve Price" in tag.text)
        if rp_label:
            # Try finding value in next sibling or parent's sibling
            # Often structure is <div class="col-md-3"><label>Reserve Price</label></div><div class="col-md-3"><span>1,00,00,000</span></div>
            # Or <label>Reserve Price : <span>1,00,00,000</span></label>
            
            # Strategy 1: Check if value is inside label or span inside label
            val = rp_label.find("span")
            if val:
                details["reservePrice"] = val.text.strip()
            else:
                # Strategy 2: Look for value in next sibling element
                parent = rp_label.parent
                if parent:
                    next_sibling = parent.find_next_sibling()
                    if next_sibling:
                        val = next_sibling.text.strip()
                        details["reservePrice"] = val

        # Look for "EMD" label
        emd_label = soup.find(lambda tag: tag.name == "label" and "EMD Amount" in tag.text)
        if emd_label:
             val = emd_label.find("span")
             if val:
                 details["emd"] = val.text.strip()
             else:
                 parent = emd_label.parent
                 if parent:
                     next_sibling = parent.find_next_sibling()
                     if next_sibling:
                         val = next_sibling.text.strip()
                         details["emd"] = val

        # 2. Contact Details (Insolvency Professional / Liquidator)
        # Look for "Liquidator Name" or "IP Name"
        contact_info = []
        
        ip_label = soup.find(lambda tag: tag.name == "label" and ("Liquidator Name" in tag.text or "IP Name" in tag.text))
        if ip_label:
            parent = ip_label.parent
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    contact_info.append(next_sibling.text.strip())

        # Look for Email/Phone
        email_label = soup.find(lambda tag: tag.name == "label" and "Email" in tag.text)
        if email_label:
             parent = email_label.parent
             if parent:
                 next_sibling = parent.find_next_sibling()
                 if next_sibling:
                     contact_info.append(next_sibling.text.strip())
                     
        phone_label = soup.find(lambda tag: tag.name == "label" and "Mobile" in tag.text)
        if phone_label:
             parent = phone_label.parent
             if parent:
                 next_sibling = parent.find_next_sibling()
                 if next_sibling:
                     contact_info.append(next_sibling.text.strip())
        
        if contact_info:
            details["contactDetails"] = " | ".join(filter(None, contact_info))

        # 3. Dates (Auction Start/End, Inspection, Application Submission)
        # Auction Start Date
        start_label = soup.find(lambda tag: tag.name == "label" and "Auction Start Date" in tag.text)
        if start_label:
            parent = start_label.parent
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    details["auctionStartDate"] = next_sibling.text.strip()

        # Auction End Date
        end_label = soup.find(lambda tag: tag.name == "label" and "Auction End Date" in tag.text)
        if end_label:
            parent = end_label.parent
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    details["auctionEndTime"] = next_sibling.text.strip()
        
        # Inspection Date
        insp_label = soup.find(lambda tag: tag.name == "label" and "Inspection Date" in tag.text)
        if insp_label:
            parent = insp_label.parent
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    details["inspectionDate"] = next_sibling.text.strip()
                    
        # Application Submission Date (Last Date of EMD)
        sub_label = soup.find(lambda tag: tag.name == "label" and "Last Date of EMD" in tag.text)
        if sub_label:
            parent = sub_label.parent
            if parent:
                next_sibling = parent.find_next_sibling()
                if next_sibling:
                    details["applicationSubmissionDate"] = next_sibling.text.strip()

        # 4. Description / Asset Description
        desc_label = soup.find(lambda tag: tag.name == "label" and "Asset Description" in tag.text)
        if desc_label:
            # Often in a textarea or div below
            # Try finding the nearest following text content
            # Or finding parent's parent and searching
            container = desc_label.find_parent("div", class_="row")
            if container:
                desc_div = container.find_next_sibling("div")
                if desc_div:
                    details["description"] = desc_div.text.strip()
        
        if "description" not in details:
             # Fallback: look for "Asset Title"
             title_label = soup.find(lambda tag: tag.name == "label" and "Asset Title" in tag.text)
             if title_label:
                 parent = title_label.parent
                 if parent:
                     next_sibling = parent.find_next_sibling()
                     if next_sibling:
                         details["description"] = next_sibling.text.strip()

        return details

    except Exception as e:
        print(f"[BaankNet IBC] Error fetching details: {e}")
        return {}

def scrape_single_card(session, card, state):
    """Extract data from a single card"""
    try:
        # 1. Asset ID
        asset_id = ""
        items = card.select(".items .row")
        for row in items:
            data_div = row.select_one(".data")
            if data_div and "Asset ID" in data_div.text:
                span = row.select_one("span")
                if span:
                    asset_id = span.text.strip()
                break
        
        # 2. Asset Name / Title
        title_h4 = card.select_one(".details-title h4")
        name = title_h4.text.strip() if title_h4 else ""
        
        # 3. Company Name
        company_h4 = card.select_one(".company-title h4")
        company_name = company_h4.text.strip() if company_h4 else ""
        
        # 4. Location
        location = ""
        for row in items:
            data_div = row.select_one(".data")
            if data_div and "Location" in data_div.text:
                span = row.select_one("span")
                if span:
                    location = span.text.strip()
                break
        
        city = ""
        state_name = ""
        district = ""
        if location:
            parts = [p.strip() for p in location.split(',')]
            if len(parts) >= 3:
                city = parts[0]
                district = parts[1]
                state_name = parts[2]
            elif len(parts) == 2:
                city = parts[0]
                state_name = parts[1]
            else:
                city = location

        # 5. Auction Date
        auction_date = ""
        for row in items:
            data_div = row.select_one(".data")
            if data_div and "Auction Start Date" in data_div.text:
                span = row.select_one("span")
                if span:
                    auction_date = span.text.strip()
                break
        
        # 6. Images
        image_urls = []
        modal_links = card.select("[data-target^='#imageModal']")
        if modal_links:
            target_id = modal_links[0].get("data-target")
            if target_id:
                modal = card.select_one(target_id)
                if modal:
                    imgs = modal.select("img")
                    for img in imgs:
                        src = img.get("src")
                        if src and "Image_not_available" not in src:
                            image_urls.append(src)
        
        if not image_urls:
            main_img = card.select_one(".img img")
            if main_img:
                src = main_img.get("src")
                if src and "Image_not_available" not in src:
                    image_urls.append(src)

        # 7. Detail Link
        detail_url = ""
        link = card.find("a", href=lambda h: h and "home-view-asset" in h)
        if link:
            detail_url = "https://ibbi.baanknet.com" + link.get("href")
            
        # 8. IP Name (Insolvency Professional)
        ip_name = ""
        for row in items:
            data_div = row.select_one(".data")
            if data_div and "IP Name" in data_div.text:
                span = row.select_one("span")
                if span:
                    ip_name = span.text.strip()
                break

        # --- FETCH DETAILS ---
        # The card data is incomplete. We MUST fetch the detail page to get correct fields.
        details = get_ibc_property_details(session, detail_url)
        
        # Merge/Prioritize details
        reserve_price = details.get("reservePrice", "0")
        emd = details.get("emd", "0")
        contact_details = details.get("contactDetails", ip_name) # Fallback to IP name if details fail
        description = details.get("description", f"Asset ID: {asset_id}. Location: {location}")
        
        final_auction_start_date = details.get("auctionStartDate", auction_date)
        final_auction_end_date = details.get("auctionEndTime", "")
        inspection_date = details.get("inspectionDate", "")
        submission_date = details.get("applicationSubmissionDate", "")

        return {
            "newListingId": "",
            "schemeName": f"{name} - {company_name}".upper(),
            "name": name,
            "category": "IBC Asset",
            "state": state,
            "city": city,
            "areaTown": district,
            "date": final_auction_start_date,
            "reservePrice": reserve_price,
            "emd": emd,
            "incrementBid": "0",
            "bankName": company_name, 
            "branchName": "",    # Corrected: IBC usually doesn't have "Branch Name" like banks. Leave empty or use "IBC".
            "contactDetails": contact_details, # Corrected: Now contains IP Name + Phone + Email
            "description": description,
            "address": location,
            "note": "IBC Auction",
            "borrowerName": company_name,
            "publishingDate": "",
            "inspectionDate": inspection_date,
            "applicationSubmissionDate": submission_date,
            "auctionStartDate": final_auction_start_date,
            "auctionEndTime": final_auction_end_date,
            "auctionType": "IBC",
            "listingId": asset_id,
            "images": ",".join(image_urls),
            "notice": detail_url,
            "source": "baanknet_ibc",
            "url": detail_url,
        }

    except Exception as e:
        print(f"[BaankNet IBC] Error parsing card: {e}")
        return None

def scrape(state, progress_callback=None):
    print(f"[BaankNet IBC] Starting scrape for {state}")
    
    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet IBC] State {state} not supported")
        return []
    
    state_id = BAANKNET_STATE_IDS[state]

    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ibbi.baanknet.com/eauction-ibbi/home",
    })

    # 1. Get CSRF Token
    print("[BaankNet IBC] Establishing session...")
    try:
        home = session.get("https://ibbi.baanknet.com/eauction-ibbi/home", timeout=30)
        soup = BeautifulSoup(home.text, "html.parser")
        csrf_meta = soup.find("meta", {"name": "_csrf"})
        if not csrf_meta:
            print("[BaankNet IBC] No CSRF token found")
            return []
        csrf_token = csrf_meta["content"]
        session.headers["X-CSRF-TOKEN"] = csrf_token
    except Exception as e:
        print(f"[BaankNet IBC] Connection error: {e}")
        return []

    url = "https://ibbi.baanknet.com/eauction-ibbi/ajax/search-asset"
    all_properties = []
    
    # 2. Iterate Pages
    page = 1
    max_pages = 100 # Safety limit
    
    while page <= max_pages:
        payload = {
            "currentPage": str(page),
            "perPage": "200", # Fetch more at once
            "astatus": "1",
            "searchType": "1",
            "stateId": state_id,
            "_csrf": csrf_token,
        }
        
        print(f"[BaankNet IBC] Fetching page {page}...")
        if progress_callback:
            progress_callback(f"Fetching page {page}...")
            
        try:
            resp = session.post(url, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet IBC] Page {page} failed with status {resp.status_code}")
                break
                
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".eproc-listing-main")
            
            if not cards:
                print(f"[BaankNet IBC] No more cards found on page {page}")
                break
                
            print(f"[BaankNet IBC] Found {len(cards)} cards on page {page}")
            
            # Process cards using ThreadPool for detail fetching
            # Fetching details for each card is slow, so we MUST parallelize this part
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(scrape_single_card, session, card, state) for card in cards]
                for future in concurrent.futures.as_completed(futures):
                    prop = future.result()
                    if prop:
                        all_properties.append(prop)
            
            # Check for pagination end
            page_tot = soup.select_one("#pageTot")
            if page_tot:
                try:
                    total_pages_avail = int(page_tot.text.strip())
                    if page >= total_pages_avail:
                        break
                except:
                    pass
            
            page += 1
            
        except Exception as e:
            print(f"[BaankNet IBC] Error fetching page {page}: {e}")
            break
            
    print(f"[BaankNet IBC] Finished. Total properties: {len(all_properties)}")
    return all_properties
