"""Main scraper runner with parallel execution"""
import concurrent.futures
import time
from datetime import datetime
import os
from collections import OrderedDict
from openpyxl import Workbook
from config import STATES
from scrapers import baanknet, baanknet_ibc, bankauctions, bankauction, baanknet_property
from fingerprint import generate_fingerprint
from seen_db import seen_db
import re


def sanitize_text_for_excel(text, max_length=32767):
    """
    Sanitize text for Excel compatibility
    - Limit length to Excel's cell limit (32,767 characters)
    - Remove or replace invalid control characters
    
    Args:
        text: Input text string
        max_length: Maximum allowed length (default: 32767)
    
    Returns:
        Sanitized text string
    """
    if not text or not isinstance(text, str):
        return text
    
    # Remove control characters except newline, carriage return, and tab
    # Excel doesn't support most control characters (0x00-0x1F except 0x09, 0x0A, 0x0D)
    sanitized = ''.join(char for char in text if ord(char) >= 32 or char in ['\t', '\n', '\r'])
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length-3] + "..."
        
    return sanitized


def clean_date_to_standard_format(date_str):
    """
    Clean and standardize date formats to DD-MM-YYYY (date only, no time)
    Handles formats: 
    - "21 Nov 2025 11:00" -> "21-11-2025"
    - "03-12-2025 11:00 AM" -> "03-12-2025"
    - "18 Nov 2025 10:00" -> "18-11-2025"
    - "15/11/2025 14:30" -> "15-11-2025"
    
    Returns None if date cannot be parsed (will cause row to be removed)
    """
    if not date_str or date_str == 'N/A' or date_str == '':
        return None
    
    try:
        date_str = str(date_str).strip()
        
        # Remove AM/PM first
        date_str = re.sub(r'\s*(AM|PM|am|pm)\s*', '', date_str).strip()
        
        # Month name mapping
        month_map = {
            'jan': '01', 'january': '01',
            'feb': '02', 'february': '02',
            'mar': '03', 'march': '03',
            'apr': '04', 'april': '04',
            'may': '05',
            'jun': '06', 'june': '06',
            'jul': '07', 'july': '07',
            'aug': '08', 'august': '08',
            'sep': '09', 'september': '09',
            'oct': '10', 'october': '10',
            'nov': '11', 'november': '11',
            'dec': '12', 'december': '12'
        }
        
        # Check if contains month name (DD MMM YYYY format)
        # e.g., "21 Nov 2025 11:00" or "21 Nov 2025"
        has_month_name = False
        for month_name in month_map.keys():
            if month_name in date_str.lower():
                has_month_name = True
                break
        
        if has_month_name:
            # Extract first 3 parts (day month year), ignore time
            parts = date_str.split()
            if len(parts) >= 3:
                day, month_str, year = parts[0], parts[1], parts[2]
                month_lower = month_str.lower()
                
                if month_lower in month_map:
                    day = day.zfill(2)
                    month = month_map[month_lower]
                    return f"{day}-{month}-{year}"
        
        # Try common numeric date formats after removing time.
        # Split by space first to remove time part
        if ' ' in date_str:
            date_str = date_str.split()[0]  # Take only the date part before space

        if '-' in date_str or '/' in date_str:
            separator = '-' if '-' in date_str else '/'
            parts = date_str.split(separator)
            
            if len(parts) == 3:
                first, second, third = parts
                if len(first) == 4:
                    year, month, day = first, second, third
                else:
                    day, month, year = first, second, third
                day = day.zfill(2)
                month = month.zfill(2)
                
                # Validate day and month
                if 1 <= int(day) <= 31 and 1 <= int(month) <= 12:
                    return f"{day}-{month}-{year}"
        
        # If we reach here, format is not recognized
        print(f"[Warning] Could not parse date: {date_str}")
        return None
        
    except Exception as e:
        print(f"[Error] Date parsing failed for '{date_str}': {e}")
        return None


def run_single_scraper(scraper_func, state, scraper_name):
    """Run a single scraper for a state"""
    try:
        print(f"[{scraper_name}] Starting scrape for {state}...")
        start_time = time.time()
        
        items = scraper_func(state)
        
        duration = time.time() - start_time
        print(f"[{scraper_name}] ✓ Completed {state} in {duration:.2f}s - Found {len(items)} items")
        
        return {
            'state': state,
            'scraperName': scraper_name,
            'items': items,
            'error': None
        }
    except Exception as e:
        print(f"[{scraper_name}] ✗ Error for {state}: {e}")
        return {
            'state': state,
            'scraperName': scraper_name,
            'items': [],
            'error': str(e)
        }


def collect_all_items(selected_states=None, selected_sites=None, progress_callback=None, status_callback=None):
    all_scrapers = {
        'baanknet': (baanknet.scrape, 'BaankNet'),
        'baanknet_ibc': (baanknet_ibc.scrape, 'BaankNet IBC'),
        'baanknet_property': (baanknet_property.scrape, 'BaankNet Property'),
        'bankauctions': (bankauctions.scrape, 'BankEAuctions'),
        'bankauction': (bankauction.scrape, 'BankAuction.in')
    }
    
    if selected_sites:
        scrapers = [all_scrapers[site] for site in selected_sites if site in all_scrapers]
    else:
        scrapers = list(all_scrapers.values())
    
    states = selected_states or STATES
    all_items = []
    
    print(f"\n🚀 Starting parallel scraping for {len(states)} states with {len(scrapers)} scrapers...")
    print(f"Total tasks: {len(scrapers) * len(states)}\n")
    
    if status_callback:
        status_callback(f"Starting scraping for {len(states)} states with {len(scrapers)} scrapers...")
    
    tasks = []
    for scraper_func, scraper_name in scrapers:
        for state in states:
            tasks.append((scraper_func, state, scraper_name))
    
    start_time = time.time()
    results = []
    
    if not tasks:
        if status_callback:
            status_callback("No scraper tasks selected.")
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(run_single_scraper, func, state, name): (func, state, name)
            for func, state, name in tasks
        }
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            results.append(result)
            
            if progress_callback:
                progress = (completed / len(tasks)) * 100
                progress_callback(progress)
            
            if status_callback:
                status_callback(f"Completed {completed}/{len(tasks)} tasks")
    
    total_duration = time.time() - start_time
    
    success_count = 0
    fail_count = 0
    invalid_dates_removed = 0
    
    for result in results:
        if result['error']:
            fail_count += 1
        else:
            success_count += 1
        
        for item in result['items']:
            text_fields = ['name', 'description', 'borrowerName', 'branchName', 'city', 
                          'areaTown', 'serviceProvider', 'contactDetails', 'notice', 'url']
            for field in text_fields:
                if field in item and isinstance(item[field], str):
                    item[field] = sanitize_text_for_excel(item[field])
            
            date_fields = ['date']
            has_invalid_date = False
            
            for field in date_fields:
                if field in item:
                    cleaned_date = clean_date_to_standard_format(item[field])
                    
                    if field in ['date'] and cleaned_date is None:
                        has_invalid_date = True
                        break
                    
                    item[field] = cleaned_date if cleaned_date else ''
            
            if has_invalid_date:
                invalid_dates_removed += 1
                listing_id = item.get('listingId', 'Unknown')
                print(f"[Warning] Removed property {listing_id} due to invalid date format")
                continue
            
            all_items.append(item)
    
    summary = f"""
📊 Scraping Summary:
   Total time: {total_duration:.2f}s
   ✓ Successful: {success_count}/{len(tasks)}
   ✗ Failed: {fail_count}/{len(tasks)}
   📦 Properties collected: {len(all_items)}
   ❌ Invalid dates removed: {invalid_dates_removed}
"""
    
    print(summary)
    if status_callback:
        status_callback(summary)
    
    return all_items


def collect_new_items(selected_states=None, selected_sites=None, progress_callback=None, status_callback=None):
    all_scrapers = {
        'baanknet': (baanknet.scrape, 'BaankNet'),
        'baanknet_ibc': (baanknet_ibc.scrape, 'BaankNet IBC'),
        'baanknet_property': (baanknet_property.scrape, 'BaankNet Property'),
        'bankauctions': (bankauctions.scrape, 'BankEAuctions'),
        'bankauction': (bankauction.scrape, 'BankAuction.in')
    }
    
    if selected_sites:
        scrapers = [all_scrapers[site] for site in selected_sites if site in all_scrapers]
    else:
        scrapers = list(all_scrapers.values())
    
    states = selected_states or STATES
    new_items = []
    
    print(f"\n🚀 Starting parallel scraping for {len(states)} states with {len(scrapers)} scrapers...")
    print(f"Total tasks: {len(scrapers) * len(states)}\n")
    
    if status_callback:
        status_callback(f"Starting scraping for {len(states)} states with {len(scrapers)} scrapers...")
    
    tasks = []
    for scraper_func, scraper_name in scrapers:
        for state in states:
            tasks.append((scraper_func, state, scraper_name))
    
    start_time = time.time()
    results = []
    
    if not tasks:
        if status_callback:
            status_callback("No scraper tasks selected.")
        return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(run_single_scraper, func, state, name): (func, state, name)
            for func, state, name in tasks
        }
        
        completed = 0
        for future in concurrent.futures.as_completed(futures):
            completed += 1
            result = future.result()
            results.append(result)
            
            if progress_callback:
                progress = (completed / len(tasks)) * 100
                progress_callback(progress)
            
            if status_callback:
                status_callback(f"Completed {completed}/{len(tasks)} tasks")
    
    total_duration = time.time() - start_time
    
    success_count = 0
    fail_count = 0
    duplicates = 0
    invalid_dates_removed = 0
    
    for result in results:
        if result['error']:
            fail_count += 1
        else:
            success_count += 1
        
        for item in result['items']:
            text_fields = ['name', 'description', 'borrowerName', 'branchName', 'city', 
                          'areaTown', 'serviceProvider', 'contactDetails', 'notice', 'url']
            for field in text_fields:
                if field in item and isinstance(item[field], str):
                    item[field] = sanitize_text_for_excel(item[field])
            
            date_fields = ['date']
            has_invalid_date = False
            
            for field in date_fields:
                if field in item:
                    cleaned_date = clean_date_to_standard_format(item[field])
                    
                    if field in ['date'] and cleaned_date is None:
                        has_invalid_date = True
                        break
                    
                    item[field] = cleaned_date if cleaned_date else ''
            
            if has_invalid_date:
                invalid_dates_removed += 1
                listing_id = item.get('listingId', 'Unknown')
                print(f"[Warning] Removed property {listing_id} due to invalid date format")
                continue
            
            fp = generate_fingerprint(item)
            
            if not seen_db.exists(fp):
                item['fingerprint'] = fp
                new_items.append(item)
            else:
                duplicates += 1
    
    summary = f"""
📊 Scraping Summary:
   Total time: {total_duration:.2f}s
   ✓ Successful: {success_count}/{len(tasks)}
   ✗ Failed: {fail_count}/{len(tasks)}
   📦 New items: {len(new_items)}
   🔄 Duplicates filtered: {duplicates}
   ❌ Invalid dates removed: {invalid_dates_removed}
"""
    
    print(summary)
    if status_callback:
        status_callback(summary)
    
    return new_items


def mark_items_seen(items):
    """Mark exported items as seen after a successful save/download flow."""
    fingerprints = []
    for item in items:
        fp = item.get('fingerprint') or generate_fingerprint(item)
        item['fingerprint'] = fp
        fingerprints.append(fp)
    seen_db.save_many(fingerprints)


def get_excel_headers(items):
    """Build stable headers without dropping fields that appear after row one."""
    headers = OrderedDict()
    preferred = [
        "newListingId", "schemeName", "name", "category", "state", "city", "areaTown",
        "date", "reservePrice", "emd", "incrementBid", "bankName", "branchName",
        "contactDetails", "description", "address", "note", "borrowerName",
        "publishingDate", "inspectionDate", "applicationSubmissionDate",
        "auctionStartDate", "auctionEndTime", "auctionType", "listingId",
        "images", "notice", "source", "url", "fingerprint",
    ]
    for header in preferred:
        headers[header] = None
    for item in items:
        for key in item.keys():
            headers[key] = None
    return [header for header in headers if any(header in item for item in items)]


def save_items_to_excel(items, output_folder=None, status_callback=None):
    if not output_folder:
        output_folder = "output"
    os.makedirs(output_folder, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    microseconds = datetime.now().strftime('%f')[:3]
    file_name = f"auctions_{timestamp}_{microseconds}.xlsx"
    file_path = os.path.join(output_folder, file_name)
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Auctions"
    
    if items:
        headers = get_excel_headers(items)
        ws.append(headers)
        
        for item in items:
            ws.append([sanitize_text_for_excel(item.get(h, '')) for h in headers])
    
    wb.save(file_path)
    print(f"✅ Saved results to: {file_path}")
    if status_callback:
        status_callback(f"Saved results to: {file_path}")
    return file_path


def run_scrapers(selected_states=None, selected_sites=None, output_folder=None, progress_callback=None, status_callback=None):
    new_items = collect_new_items(
        selected_states=selected_states,
        selected_sites=selected_sites,
        progress_callback=progress_callback,
        status_callback=status_callback,
    )
    file_path = save_items_to_excel(new_items, output_folder=output_folder, status_callback=status_callback)
    mark_items_seen(new_items)
    return file_path
