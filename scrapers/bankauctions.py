"""BankAuctions scraper"""
import requests
from bs4 import BeautifulSoup
import urllib3
from config import BANKAUCTIONS_STATE_IDS
import traceback
import time
import concurrent.futures

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def scrape_single_property_bankauctions(item, state, idx, total_items):
    """Scrape a single property from bankauctions"""
    try:
        # Build property URL
        uri = f"https://www.bankeauctions.com/{item[12]}-{item[13]}-{item[4].replace(' ', '-')}-{item[10]}".lower()
        
        # Get property page with error handling and retry logic
        prop_response = None
        max_prop_retries = 3
        
        for prop_retry in range(max_prop_retries):
            try:
                prop_response = requests.get(uri, verify=False, timeout=30)
                prop_response.raise_for_status()
                break  # Success, exit retry loop
            except Exception as req_error:
                error_str = str(req_error).lower()
                is_connection_error = ('connection' in error_str or 'reset' in error_str or 
                                     'timeout' in error_str or 'aborted' in error_str)
                
                if is_connection_error and prop_retry < max_prop_retries - 1:
                    wait_time = 2 * (prop_retry + 1)
                    time.sleep(wait_time)
                else:
                    return None
        
        if prop_response is None:
            return None
        
        soup = BeautifulSoup(prop_response.text, 'html.parser')
        
        # Helper function to get text safely
        def get_text(selector):
            elem = soup.select_one(selector)
            return elem.text.strip() if elem else ""
        
        # Extract data
        listing_id = item[1]
        name = f"{item[12]} {item[13]} {item[4]}"
        property_type = get_text(".container-lg > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > div:nth-child(3) > div:nth-child(2)")
        city = item[4]
        d = get_text(".container-lg > div:nth-child(6) > div:nth-child(1) > div:nth-child(1) > div:nth-child(7) > div:nth-child(2)")
        
        # Bank details
        bank_name = get_text("div.row:nth-child(11) > div:nth-child(2)")
        reserve_price = get_text(".container-lg > div:nth-child(5) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)").replace('₹', '').replace(',', '').strip()
        emd = get_text("div.row:nth-child(10) > div:nth-child(2)").replace('₹', '').replace(',', '').strip()
        branch_name = get_text("div.row:nth-child(13) > div:nth-child(2)")
        
        # Other details
        description = get_text(".container-lg > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > div:nth-child(4) > div:nth-child(2)")
        borrower_name = get_text(".container-lg > div:nth-child(4) > div:nth-child(1) > div:nth-child(1) > div:nth-child(5) > div:nth-child(2)")
        auction_end_time = get_text(".container-lg > div:nth-child(6) > div:nth-child(1) > div:nth-child(1) > div:nth-child(8) > div:nth-child(2)")
        auction_type = get_text(".container-lg > div:nth-child(3) > div:nth-child(1) > div:nth-child(1) > div:nth-child(2) > div:nth-child(2)")
        application_submission_date = get_text(".container-lg > div:nth-child(6) > div:nth-child(1) > div:nth-child(1) > div:nth-child(5) > div:nth-child(2)")
        publishingDate = get_text("body > section > div > div:nth-child(6) > div > div > div:nth-child(2) > div.col-md-6.col-sm-7.detl-right")
        bid_increment = get_text("body > section > div > div:nth-child(5) > div > div > div:nth-child(5) > div.col-md-6.col-sm-7.detl-right")
        inspectionDate = get_text("body > section > div > div:nth-child(6) > div > div > div:nth-child(3) > div.col-md-6.col-sm-7.detl-right")
        
        # Notice link
        notice_elem = soup.select_one(".container-lg > div:nth-child(7) > div:nth-child(1) > div:nth-child(1) > div:nth-child(4) > div:nth-child(2) > a:nth-child(1)")
        notice = "https://www.bankeauctions.com" + notice_elem.get("href").strip() if notice_elem else ""
        nit_elem = soup.select_one("body > section > div > div:nth-child(7) > div > div > div:nth-child(2) > div.col-md-6.col-sm-7.detl-right > a")
        nit_elem = "https://www.bankeauctions.com" + nit_elem.get("href").strip() if nit_elem else ""
        
        return {
            "newListingId": "",
            "schemeName": f"{name} BANK AUCTION".upper(),
            "name": name,
            "category": property_type,
            "state": state,
            "city": city,
            "areaTown": "",
            "date": d,
            "reservePrice": float(reserve_price) if reserve_price else 0,
            "emd": float(emd) if emd else 0,
            "incrementBid": bid_increment if bid_increment else 0,
            "bankName": bank_name,
            "branchName": branch_name,
            "contactDetails": "",
            "description": description,
            "address": "",
            "note": "",
            "borrowerName": borrower_name,
            "publishingDate": publishingDate,
            "inspectionDate": inspectionDate,
            "applicationSubmissionDate": application_submission_date,
            "auctionStartDate": d,
            "auctionEndTime": auction_end_time,
            "auctionType": auction_type,
            "listingId": listing_id,
            "images": nit_elem or "",
            "notice": notice or "",
            "source": "bankauctions",
            "url": uri,
        }
    except Exception as e:
        print(f"[BankAuctions] ❌ Error scraping property {idx+1}/{total_items}: {str(e)[:100]}")
        if idx < 3:  # Print detailed error for first 3 failures
            print(f"[BankAuctions] 🔍 Error details: {e}")
            import traceback
            traceback.print_exc()
        return None


def scrape(state, progress_callback=None):
    """
    Scrape properties from BankAuctions
    
    Args:
        state (str): State name
        progress_callback (callable): Optional callback for progress updates
        
    Returns:
        list: List of property dictionaries
    """
    print(f"[BankAuctions] Starting scrape for {state}")
    
    if state not in BANKAUCTIONS_STATE_IDS:
        print(f"[BankAuctions] State {state} not supported")
        return []
    
    properties = []
    
    try:
        url = f"https://www.bankeauctions.com/home/liveAuctionDatatable//?reservePriceMaxRange=&reservePriceMinRange=0&state={BANKAUCTIONS_STATE_IDS[state]}&propertytype=null&tmpAct=0&search_input=&city_name=&bank_id=Organisation%2FBank%20Name&property_sub_type=null&budget_search=Budget"
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0"
        }
        
        # First request to get total records
        data = {
            "sEcho": "1",
            "iColumns": "15",
            "sColumns": "",
            "iDisplayStart": "0",
            "iDisplayLength": "10",
            "sSearch": "",
            "bRegex": "false",
            "iSortCol_0": "0",
            "sSortDir_0": "asc",
            "iSortingCols": "1",
        }
        
        # Add column parameters
        for i in range(15):
            data[f"mDataProp_{i}"] = str(i)
            data[f"sSearch_{i}"] = ""
            data[f"bRegex_{i}"] = "false"
            data[f"bSearchable_{i}"] = "true"
            data[f"bSortable_{i}"] = "true"
        
        # Initial request with retry logic
        total_records = 0
        initial_max_retries = 3
        
        for initial_retry in range(initial_max_retries):
            try:
                response = requests.post(url, data=data, headers=headers, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                total_records = int(result.get('iTotalRecords', 0))
                break  # Success, exit retry loop
                
            except Exception as e:
                error_str = str(e).lower()
                is_connection_error = ('connection' in error_str or 'reset' in error_str or 
                                     'timeout' in error_str or 'aborted' in error_str)
                
                if is_connection_error and initial_retry < initial_max_retries - 1:
                    wait_time = 2 ** (initial_retry + 1)  # 2, 4, 8 seconds
                    print(f"[BankAuctions] ⚠️  Connection error on initial request")
                    print(f"[BankAuctions] 🔄 Retrying in {wait_time} seconds... (Attempt {initial_retry + 1}/{initial_max_retries})")
                    time.sleep(wait_time)
                else:
                    print(f"[BankAuctions] ❌ Failed to connect after {initial_max_retries} retries")
                    raise  # Re-raise to be caught by outer exception handler
        
        print(f"[BankAuctions] 📊 Found {total_records} total property items for {state}")
        
        if total_records == 0:
            print(f"[BankAuctions] ⚠️  No properties found for {state}")
            return properties
        
        # Collect all items by paginating through results
        all_items = []
        display_length = 10  # Changed to 10 to match API response
        pages_fetched = 0
        pages_failed = 0
        
        for start in range(0, total_records, display_length):
            max_retries = 5  # Increased from 3 to 5
            retry_count = 0
            success = False
            
            # Add delay between pagination requests to avoid rate limiting
            if start > 0:
                time.sleep(2)  # Wait 2 seconds between page requests
            
            while retry_count < max_retries and not success:
                try:
                    print(f"[BankAuctions] 📥 Fetching items {start} to {start + display_length} of {total_records}")
                    
                    data["iDisplayStart"] = str(start)
                    
                    response = requests.post(url, data=data, headers=headers, timeout=30)
                    response.raise_for_status()
                    
                    result = response.json()
                    items = result.get('aaData', [])
                    all_items.extend(items)
                    print(f"[BankAuctions] ✓ Successfully fetched {len(items)} items (Total collected: {len(all_items)})")
                    success = True
                    pages_fetched += 1
                    
                except Exception as e:
                    # Check if it's a connection error (including ConnectionResetError wrapped in requests exception)
                    error_str = str(e).lower()
                    is_connection_error = ('connection' in error_str or 'reset' in error_str or 
                                         'timeout' in error_str or 'aborted' in error_str)
                    
                    if is_connection_error and retry_count < max_retries - 1:
                        retry_count += 1
                        wait_time = min(2 ** retry_count, 10)  # Exponential backoff: 2, 4, 8, 10, 10 seconds (capped at 10)
                        print(f"[BankAuctions] ⚠️  Connection error at offset {start}")
                        print(f"[BankAuctions] 🔄 Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        if retry_count >= max_retries - 1:
                            print(f"[BankAuctions] ❌ Failed after {max_retries} retries at offset {start}")
                        else:
                            print(f"[BankAuctions] ❌ Error fetching page at offset {start}")
                        print(f"[BankAuctions] ⏭️  Skipping page, continuing with remaining pages...")
                        pages_failed += 1
                        break
        
        total_items = len(all_items)
        print(f"[BankAuctions] 📦 Pagination Summary:")
        print(f"[BankAuctions]    - Expected: {total_records} items")
        print(f"[BankAuctions]    - Collected: {total_items} items")
        print(f"[BankAuctions]    - Pages fetched: {pages_fetched}")
        print(f"[BankAuctions]    - Pages failed: {pages_failed}")
        print(f"[BankAuctions]    - Missing: {total_records - total_items} items")
        
        if total_items == 0:
            print(f"[BankAuctions] ⚠️  No items collected, skipping property scraping")
            return properties
        
        print(f"[BankAuctions] 🏠 Starting detailed property scraping with {min(15, total_items)} parallel threads...")
        properties_scraped = 0
        properties_failed = 0
        
        # Scrape all properties in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(scrape_single_property_bankauctions, item, state, idx, total_items): idx 
                      for idx, item in enumerate(all_items)}
            
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                completed += 1
                result = future.result()
                
                if progress_callback:
                    progress_callback(f"[BankAuctions] Scraping {completed}/{total_items}")
                
                if result:
                    properties.append(result)
                    properties_scraped += 1
                    if completed % 10 == 0 or completed == 1:
                        print(f"[BankAuctions] ✓ Scraped {completed}/{total_items} properties (Successful: {properties_scraped})")
                else:
                    properties_failed += 1
        
        # Final summary
        print(f"[BankAuctions] 📊 Property Scraping Summary:")
        print(f"[BankAuctions]    - Items to scrape: {total_items}")
        print(f"[BankAuctions]    - Successfully scraped: {properties_scraped}")
        print(f"[BankAuctions]    - Failed: {properties_failed}")
        print(f"[BankAuctions]    - Success rate: {(properties_scraped/total_items*100) if total_items > 0 else 0:.1f}%")
        
    except Exception as e:
        print(f"[BankAuctions] ❌ Error scraping state {state}: {e}")
    
    print(f"[BankAuctions] ✅ Completed scraping {state}. Total properties scraped: {len(properties)}")
    return properties
