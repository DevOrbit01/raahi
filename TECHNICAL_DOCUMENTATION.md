# Raahi Property Scraper - Technical Documentation

## Project Overview

**Project Name:** Raahi Property Scraper  
**Version:** 1.0.0  
**Language:** Python 3.x  
**Type:** Desktop Application with GUI  
**Purpose:** Automated web scraping tool for bank auction properties across multiple Indian auction platforms

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [System Requirements](#system-requirements)
3. [Project Structure](#project-structure)
4. [Core Components](#core-components)
5. [Data Flow](#data-flow)
6. [Scraper Implementations](#scraper-implementations)
7. [Database & Deduplication](#database--deduplication)
8. [GUI Implementation](#gui-implementation)
9. [Build & Deployment](#build--deployment)
10. [API Specifications](#api-specifications)
11. [Configuration](#configuration)
12. [Error Handling](#error-handling)
13. [Performance Optimization](#performance-optimization)
14. [Security Considerations](#security-considerations)
15. [Maintenance & Troubleshooting](#maintenance--troubleshooting)

---

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (GUI)                     │
│                    CustomTkinter (gui.py)                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Scraper Runner (scraper_runner.py)         │
│                  - Task Management                           │
│                  - Parallel Execution (ThreadPoolExecutor)   │
│                  - Progress Tracking                         │
│                  - Data Sanitization                         │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│              Scraper Modules (scrapers/)                      │
│  ┌──────────────┬──────────────┬──────────────┬───────────┐ │
│  │ baanknet.py  │ bankauctions │ eauctionsindia│ bankauction│ │
│  │              │     .py      │      .py      │   .py     │ │
│  └──────────────┴──────────────┴──────────────┴───────────┘ │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│           Support Modules                                     │
│  ┌────────────────┬─────────────────┬──────────────────────┐ │
│  │ fingerprint.py │ seen_db.py      │ config.py            │ │
│  │ (Deduplication)│ (JSON Database) │ (State/Type Mapping) │ │
│  └────────────────┴─────────────────┴──────────────────────┘ │
└──────────────┬──────────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────────────────────┐
│                    Output Layer                               │
│             Excel Files (openpyxl) + JSON DB                  │
└──────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| **Language** | Python | 3.8+ |
| **GUI Framework** | CustomTkinter | Latest |
| **HTTP Client** | Requests | Latest |
| **HTML Parser** | BeautifulSoup4 | Latest |
| **Excel Generation** | OpenPyXL | Latest |
| **Image Support** | Pillow | Latest |
| **Concurrency** | concurrent.futures | Built-in |
| **Build Tool** | PyInstaller | Latest |

---

## System Requirements

### Development Environment

- **Operating System:** Windows 10/11, macOS 10.14+, Linux
- **Python:** 3.8 or higher
- **RAM:** Minimum 4GB (8GB recommended)
- **Disk Space:** 500MB for application + storage for scraped data
- **Internet:** Stable broadband connection (required for scraping)

### Runtime Dependencies

```plaintext
requests>=2.31.0
beautifulsoup4>=4.12.0
openpyxl>=3.1.0
customtkinter>=5.2.0
Pillow>=10.0.0
urllib3>=2.0.0
```

---

## Project Structure

```
raahi-scraper-software/
│
├── gui.py                      # Main GUI application entry point
├── scraper_runner.py           # Orchestrates parallel scraping execution
├── config.py                   # Configuration constants (states, IDs, types)
├── fingerprint.py              # Property deduplication logic
├── seen_db.py                  # JSON-based persistence layer
├── requirements.txt            # Python dependencies
├── build.spec                  # PyInstaller build specification
├── seen_properties.json        # Runtime database (auto-generated)
│
├── scrapers/                   # Scraper module package
│   ├── __init__.py            # Package initialization
│   ├── baanknet.py            # BaankNet scraper implementation
│   ├── bankauctions.py        # BankEAuctions scraper implementation
│   ├── eauctionsindia.py      # eAuctionsIndia scraper implementation
│   └── bankauction.py         # BankAuction.in scraper implementation
│
├── output/                     # Generated Excel files (auto-created)
│   └── auctions_YYYY-MM-DD_HH-MM-SS_mmm.xlsx
│
└── build/                      # PyInstaller build artifacts
    ├── build/                  # Intermediate build files
    └── main/                   # Compiled executable
```

---

## Core Components

### 1. Configuration Module (`config.py`)

**Purpose:** Centralized configuration management for states, property types, and API parameters.

#### Key Constants:

```python
# Supported states
STATES = ["Delhi", "Gujarat", "Maharashtra", "Rajasthan"]

# BaankNet state ID mapping
BAANKNET_STATE_IDS = {
    "Delhi": "9",
    "Gujarat": "11",
    "Maharashtra": "21",
    "Rajasthan": "29"
}

# BankAuctions state ID mapping
BANKAUCTIONS_STATE_IDS = {
    "Delhi": "29",
    "Gujarat": "7",
    "Maharashtra": "15",
    "Rajasthan": "22"
}

# Supported property types
PROPERTY_TYPES = [
    "Flat",
    "Commercial Property",
    "Land and Building",
    "Land",
    "Commercial Shop"
]
```

**Usage:** Import and reference constants across all modules for consistency.

---

### 2. Scraper Runner (`scraper_runner.py`)

**Purpose:** Orchestrates all scraping operations, manages parallel execution, and generates output files.

#### Key Functions:

##### `run_scrapers(selected_states, selected_sites, output_folder, progress_callback, status_callback)`

**Parameters:**
- `selected_states` (list): States to scrape (e.g., `["Delhi", "Gujarat"]`)
- `selected_sites` (list): Site keys to scrape (e.g., `["baanknet", "eauctionsindia"]`)
- `output_folder` (str): Output directory path
- `progress_callback` (callable): Function for progress updates (0-100)
- `status_callback` (callable): Function for status messages

**Returns:** `str` - Path to generated Excel file

**Execution Flow:**
1. Initialize scraper functions based on site selection
2. Create task matrix (scrapers × states)
3. Execute tasks in parallel using `ThreadPoolExecutor` (20 workers)
4. Collect and sanitize results
5. Filter duplicates using fingerprinting
6. Validate and clean date formats
7. Generate timestamped Excel file

##### `sanitize_text_for_excel(text, max_length=32767)`

**Purpose:** Ensures text compatibility with Excel cell limitations.

**Sanitization Steps:**
- Removes control characters (except `\t`, `\n`, `\r`)
- Truncates text to 32,767 characters (Excel limit)
- Returns sanitized string

##### `clean_date_to_standard_format(date_str)`

**Purpose:** Normalizes various date formats to `DD-MM-YYYY`.

**Supported Input Formats:**
- `"21 Nov 2025 11:00"` → `"21-11-2025"`
- `"03-12-2025 11:00 AM"` → `"03-12-2025"`
- `"15/11/2025 14:30"` → `"15-11-2025"`

**Returns:** `None` if date is invalid (row will be excluded)

##### `run_single_scraper(scraper_func, state, scraper_name)`

**Purpose:** Wraps individual scraper execution with error handling and timing.

**Returns:** Dictionary with:
```python
{
    'state': str,
    'scraperName': str,
    'items': list,
    'error': str or None
}
```

---

### 3. Fingerprinting Module (`fingerprint.py`)

**Purpose:** Generate unique hashes for properties to detect duplicates.

#### Function: `generate_fingerprint(item)`

**Algorithm:**
1. Extract key identifying fields:
   - `listingId`
   - `source`
   - `bankName`
   - `city`
   - `reservePrice`
2. Create JSON string with sorted keys
3. Generate MD5 hash
4. Return 32-character hexadecimal string

**Example:**
```python
item = {
    'listingId': 'PROP12345',
    'source': 'baanknet',
    'bankName': 'SBI',
    'city': 'Mumbai',
    'reservePrice': 5000000
}
fingerprint = generate_fingerprint(item)
# Output: "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
```

---

### 4. Database Module (`seen_db.py`)

**Purpose:** Persistent storage for seen property fingerprints using JSON.

#### Class: `SeenDatabase`

**File:** `seen_properties.json`

**Methods:**

```python
class SeenDatabase:
    def __init__(self, db_file='seen_properties.json'):
        """Initialize database and load existing fingerprints"""
        
    def exists(self, fingerprint: str) -> bool:
        """Check if fingerprint already exists"""
        
    def save(self, fingerprint: str):
        """Add new fingerprint to database and persist"""
        
    def clear(self):
        """Remove all fingerprints from database"""
```

**Storage Format:**
```json
[
    "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
    "b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7",
    "c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8"
]
```

**Usage:**
```python
from seen_db import seen_db

# Check if property was already scraped
if not seen_db.exists(fingerprint):
    seen_db.save(fingerprint)
    # Process new property
```

---

## Data Flow

### End-to-End Scraping Process

```
1. USER INTERACTION
   └─> GUI: Select states, sites, output folder
   
2. INITIALIZATION
   └─> Create task matrix (4 scrapers × N states)
   
3. PARALLEL EXECUTION (20 workers)
   ├─> Task 1: BaankNet - Delhi
   ├─> Task 2: BaankNet - Gujarat
   ├─> Task 3: BankAuctions - Delhi
   └─> Task N: eAuctionsIndia - Rajasthan
   
4. PER-TASK EXECUTION
   ├─> HTTP Request to target site
   ├─> Parse HTML/JSON response
   ├─> Extract property details
   ├─> Normalize data format
   └─> Return property list
   
5. DATA PROCESSING
   ├─> Sanitize text fields (Excel compatibility)
   ├─> Clean date formats (DD-MM-YYYY)
   ├─> Generate fingerprint (MD5)
   ├─> Check against seen_db
   └─> Filter duplicates
   
6. OUTPUT GENERATION
   ├─> Create Excel workbook
   ├─> Write headers
   ├─> Write property rows
   └─> Save to output folder
   
7. PERSISTENCE
   └─> Update seen_properties.json
```

---

## Scraper Implementations

### Common Property Schema

All scrapers return properties in this standardized format:

```python
{
    'listingId': str,              # Unique identifier from source
    'name': str,                   # Property title/name
    'category': str,               # Property type
    'city': str,                   # City name
    'date': str,                   # Auction date (DD-MM-YYYY)
    'bankName': str,               # Bank/financial institution
    'reservePrice': float,         # Reserve price in INR
    'emd': float,                  # Earnest Money Deposit in INR
    'branchName': str,             # Bank branch name
    'serviceProvider': str,        # Auction service provider
    'contactDetails': str,         # Contact information
    'description': str,            # Property description
    'state': str,                  # State name
    'areaTown': str,               # Area/district
    'borrowerName': str,           # Original borrower
    'propertyType': str,           # Detailed property type
    'auctionStartDate': str,       # Auction start date
    'auctionEndTime': str,         # Auction end date/time
    'auctionType': str,            # Type of auction
    'applicationSubmissionDate': str,  # Last date for submission
    'images': str,                 # Image URL
    'notice': str,                 # Notice document URL
    'source': str,                 # Scraper source identifier
    'url': str,                    # Property detail page URL
    'fingerprint': str             # MD5 hash (added during processing)
}
```

---

### 1. BaankNet Scraper (`scrapers/baanknet.py`)

**Target Site:** https://baanknet.com/eauction-psb/

#### Technical Approach:

**Challenge:** Site uses CSRF token protection and session management.

**Solution:**
1. Create persistent `requests.Session()`
2. Load home page to obtain `JSESSIONID` and `XSRF-TOKEN`
3. Extract CSRF token from `<meta name="_csrf">` tag
4. Add token to request headers: `X-CSRF-TOKEN`
5. Send AJAX POST requests to filter API

#### API Endpoints:

**1. Search API (POST):**
```
URL: https://baanknet.com/eauction-psb/ajax/search-auction
Content-Type: application/json
```

**Request Payload:**
```json
{
    "currentPage": "1",
    "perPage": "200",
    "aucXstatus": "1",
    "searchType": "1",
    "stateId": "9",  // From BAANKNET_STATE_IDS
    "_csrf": "token_value"
}
```

**Response:** HTML fragment with property cards + pagination info

**2. Property Details API (GET):**
```
URL: https://baanknet.com/eauction-psb/api/view-property-detail/{propertyId}/1
```

**Response:** JSON with complete property details

#### Pagination Handling:

1. Parse `#pageTot` element from first response to get total pages
2. Iterate through all pages (currentPage: 1 to N)
3. Collect all property cards
4. Scrape details in parallel (10 workers)

#### Key Code Flow:

```python
def scrape(state, progress_callback=None):
    # 1. Create session
    session = requests.Session()
    session.verify = False
    
    # 2. Get CSRF token
    home = session.get("https://baanknet.com/eauction-psb/home")
    csrf_token = extract_csrf(home.text)
    session.headers["X-CSRF-TOKEN"] = csrf_token
    
    # 3. Get total pages
    response = session.post(search_url, json={"currentPage": "1", ...})
    total_pages = parse_total_pages(response.text)
    
    # 4. Collect all cards
    all_cards = []
    for page in range(1, total_pages + 1):
        response = session.post(search_url, json={"currentPage": str(page), ...})
        cards = extract_cards(response.text)
        all_cards.extend(cards)
    
    # 5. Parallel scraping
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(scrape_single_property, card, ...) 
                   for card in all_cards]
        properties = [f.result() for f in as_completed(futures) if f.result()]
    
    return properties
```

---

### 2. BankEAuctions Scraper (`scrapers/bankauctions.py`)

**Target Site:** https://www.bankeauctions.com/

#### Technical Approach:

**Challenge:** DataTables AJAX pagination with specific parameter format.

**Solution:**
1. Initial POST request to get total record count
2. Paginate through results with `iDisplayStart` parameter
3. Extract property URLs from JSON response
4. Scrape individual property pages

#### API Endpoint:

**DataTables API (POST):**
```
URL: https://www.bankeauctions.com/home/liveAuctionDatatable/
Content-Type: application/x-www-form-urlencoded
```

**Request Parameters:**
```python
data = {
    "sEcho": "1",
    "iColumns": "15",
    "iDisplayStart": "0",      # Pagination offset
    "iDisplayLength": "10",    # Items per page
    "iSortCol_0": "0",
    "sSortDir_0": "asc",
    # ... plus column-specific parameters
}
```

**Response:**
```json
{
    "iTotalRecords": 150,
    "aaData": [
        [col0, col1, col2, ..., col14],  // Row 1
        [col0, col1, col2, ..., col14]   // Row 2
    ]
}
```

#### Property URL Construction:

From row data: `[col0, col1, ..., col4=city, ..., col10=id, col12=type, col13=subtype]`

```python
uri = f"https://www.bankeauctions.com/{item[12]}-{item[13]}-{item[4].replace(' ', '-')}-{item[10]}".lower()
# Example: "https://www.bankeauctions.com/residential-flat-mumbai-12345"
```

#### Retry Logic:

**Connection Error Handling:**
```python
max_retries = 5
retry_count = 0

while retry_count < max_retries:
    try:
        response = requests.post(url, ...)
        break  # Success
    except ConnectionError:
        retry_count += 1
        wait_time = min(2 ** retry_count, 10)  # Exponential backoff
        time.sleep(wait_time)
```

**Features:**
- Exponential backoff: 2, 4, 8, 10, 10 seconds
- Page-level retry (skip failed pages, continue with rest)
- Property-level retry (skip individual property, continue with rest)

---

### 3. eAuctionsIndia Scraper (`scrapers/eauctionsindia.py`)

**Target Site:** https://www.eauctionsindia.com/

#### Technical Approach:

**Challenge:** Server-side pagination with page numbers in URLs.

**Solution:**
1. Detect total pages from pagination HTML
2. Iterate through pages: `/properties-in-{state}/{page_number}`
3. Extract property URLs from listing cards
4. Scrape individual property pages in parallel

#### URL Structure:

**Listing Pages:**
```
https://www.eauctionsindia.com/properties-in-delhi/1
https://www.eauctionsindia.com/properties-in-delhi/2
...
```

**Property Pages:**
```
https://www.eauctionsindia.com/property/{listing-id}
```

#### Pagination Detection:

```python
# Find pagination elements
pagination_items = soup.select('.pagination > li')

# Get second-to-last element (before "Next" button)
if len(pagination_items) >= 2:
    second_last = pagination_items[-2]
    link = second_last.select_one('a')
    max_pages = int(link.text.strip())
```

#### Property Type Filtering:

Only scrapes properties matching `PROPERTY_TYPES` from `config.py`:

```python
type_elem = card.select_one("ul > li > p")
prop_type = type_elem.text.strip()

if prop_type not in PROPERTY_TYPES:
    continue  # Skip this property
```

#### Parallel Scraping:

```python
# Collect URLs first
property_urls = []
for page in range(1, max_pages + 1):
    cards = get_cards_from_page(page)
    urls = extract_urls_from_cards(cards)
    property_urls.extend(urls)

# Scrape all in parallel
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = [executor.submit(scrape_single_property, url, state) 
               for url in property_urls]
    properties = [f.result() for f in as_completed(futures) if f.result()]
```

---

### 4. BankAuction.in Scraper (`scrapers/bankauction.py`)

**Target Site:** https://bankauctions.in/

#### Technical Approach:

**Challenge:** JSON API without pagination, city-based filtering.

**Solution:**
1. Single API call returns all properties
2. Filter by predefined cities
3. Scrape individual property pages

#### API Endpoint:

**Properties API (POST):**
```
URL: https://bankauctions.in/wp-json/eauc-table/v1/home_page
```

**Response:**
```json
{
    "data": [
        {
            "city": "Mumbai",
            "url": "https://bankauctions.in/property/...",
            // ... other fields
        }
    ]
}
```

#### City Filtering:

```python
CITIES = ["Ahemdabad", "Delhi", "Mumbai", "Pune", "Jaipur", "Surat", "Vadodara"]

for item in items:
    if item.get('city') not in CITIES:
        continue  # Skip properties outside target cities
```

#### Sequential Scraping:

This scraper uses sequential (non-parallel) execution due to smaller dataset:

```python
for item in filtered_items:
    property_url = item.get('url')
    property_data = scrape_single_property(property_url)
    properties.append(property_data)
```

---

## Database & Deduplication

### Fingerprinting Strategy

**Purpose:** Prevent duplicate properties across multiple scraping sessions.

**Key Fields Used:**
- `listingId`: Unique ID from source site
- `source`: Scraper identifier (e.g., "baanknet")
- `bankName`: Bank name
- `city`: City name
- `reservePrice`: Reserve price

**Rationale:**
- `listingId` + `source` combination is unique per property
- Additional fields provide collision resistance
- Price changes should NOT create duplicates (same property)

### Database Operations

**Write Operation:**
```python
# After scraping new property
fingerprint = generate_fingerprint(property)
if not seen_db.exists(fingerprint):
    seen_db.save(fingerprint)
    # Add to output
```

**Read Operation:**
```python
# Check if property already scraped
if seen_db.exists(fingerprint):
    # Skip (duplicate)
    pass
else:
    # New property
    pass
```

**Clear Operation:**
```python
# User clicks "Clear Database" button
seen_db.clear()
# All properties will be re-scraped next time
```

### Database File Location

**File:** `seen_properties.json` (root directory)

**Size Growth:** ~50 bytes per property × number of scraped properties

**Example:** 1,000 properties ≈ 50KB

---

## GUI Implementation

### Framework: CustomTkinter

**Advantages:**
- Modern, native-looking widgets
- Cross-platform (Windows, macOS, Linux)
- Customizable themes and colors
- Drop-in replacement for tkinter

### Main Window (`gui.py`)

**Class:** `ScraperGUI`

**Dimensions:** 950×750 pixels

**Theme:** Light mode with blue accent color

### UI Components

#### 1. Site Selection Panel

**Purpose:** Choose which auction sites to scrape.

**Widgets:**
- 4 checkboxes (eAuctionsIndia, BaankNet, BankEAuctions, BankAuction.in)
- "Select All Sites" button
- "Deselect All Sites" button

**State Variable:**
```python
self.site_vars = {
    'eauctionsindia': BooleanVar(value=True),
    'baanknet': BooleanVar(value=True),
    'bankauctions': BooleanVar(value=True),
    'bankauction': BooleanVar(value=True)
}
```

#### 2. State Selection Panel

**Purpose:** Choose which states to scrape.

**Widgets:**
- 4 checkboxes (Delhi, Gujarat, Maharashtra, Rajasthan)
- "Select All" button
- "Deselect All" button

**State Variable:**
```python
self.state_vars = {
    'Delhi': BooleanVar(value=True),
    'Gujarat': BooleanVar(value=True),
    'Maharashtra': BooleanVar(value=True),
    'Rajasthan': BooleanVar(value=True)
}
```

#### 3. Output Folder Panel

**Purpose:** Specify where to save Excel files.

**Widgets:**
- Entry field (read-only, shows current path)
- "Browse" button (opens folder picker dialog)

**Default:** `./output` (auto-created if doesn't exist)

#### 4. Progress Panel

**Purpose:** Display scraping progress and logs.

**Widgets:**
- Progress bar (0-100%)
- Status label (current operation)
- Log textbox (scrollable, read-only)

**Updates:**
```python
self.update_progress(50)  # 50% complete
self.update_status("Scraping BaankNet - Delhi...")
self.log("✓ Found 25 properties")
```

#### 5. Control Buttons

**Buttons:**

1. **Start Scraping** (Green)
   - Validates selections
   - Starts scraping thread
   - Disables itself during scraping
   
2. **Open Output File** (Blue)
   - Opens last generated Excel file
   - Initially disabled (enabled after scraping)
   
3. **Clear Database** (Red)
   - Confirms with user dialog
   - Clears `seen_properties.json`

### Threading Architecture

**Main Thread:** GUI event loop

**Scraping Thread:** Background worker (daemon=True)

```python
def start_scraping(self):
    # Validation
    if not selected_sites or not selected_states:
        messagebox.showwarning(...)
        return
    
    # Start background thread
    thread = threading.Thread(
        target=self.run_scraping_thread,
        args=(selected_states, selected_sites),
        daemon=True
    )
    thread.start()

def run_scraping_thread(self, states, sites):
    try:
        # Run scraper (blocks thread)
        output_file = run_scrapers(
            selected_states=states,
            selected_sites=sites,
            progress_callback=self.update_progress,
            status_callback=self.update_status
        )
        
        # Update GUI from main thread
        self.root.after(0, lambda: messagebox.showinfo("Success", ...))
    except Exception as e:
        self.root.after(0, lambda: messagebox.showerror("Error", ...))
```

**Callback Pattern:**
- Background thread calls `progress_callback(50)`
- Callback updates GUI widget: `self.progress_bar.set(0.5)`
- `self.root.update_idletasks()` ensures UI refresh

---

## Build & Deployment

### PyInstaller Configuration

**File:** `build.spec`

**Build Command:**
```bash
pyinstaller build.spec
```

### Spec File Configuration

```python
# Analysis phase
a = Analysis(
    ['gui.py'],                  # Entry point
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'PIL._tkinter_finder',
        'openpyxl',
        'requests',
        'bs4',
        'urllib3',
        'scrapers.baanknet',
        'scrapers.bankauctions',
        'scrapers.eauctionsindia',
        'scrapers.bankauction'    # Added explicitly
    ],
    # ... other options
)

# Executable configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RaahiScraper',         # Output filename
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,                    # Enable UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,               # No console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None                    # Add icon file if available
)
```

### Build Output

**Location:** `build/main/RaahiScraper.exe` (Windows)

**Size:** ~50-80MB (includes Python interpreter + dependencies)

**Distribution:**
- Single executable file
- No installation required
- Can be run from any location
- Creates `output/` folder and `seen_properties.json` in working directory

### Platform-Specific Builds

**Windows:**
```bash
pyinstaller build.spec
# Output: RaahiScraper.exe
```

**macOS:**
```bash
pyinstaller build.spec
# Output: RaahiScraper.app
```

**Linux:**
```bash
pyinstaller build.spec
# Output: RaahiScraper (binary)
```

---

## API Specifications

### Scraper Function Interface

All scrapers must implement this signature:

```python
def scrape(state: str, progress_callback: Optional[Callable] = None) -> List[Dict]:
    """
    Scrape properties for a given state.
    
    Args:
        state (str): State name (must be in config.STATES)
        progress_callback (callable, optional): Function to call with progress updates
            Signature: progress_callback(message: str) -> None
    
    Returns:
        List[Dict]: List of property dictionaries following the standard schema
        
    Raises:
        Exception: Any errors during scraping (logged, not re-raised)
    """
    pass
```

### Standard Property Dictionary

```python
{
    # Required fields
    'listingId': str,              # Must be unique per source
    'name': str,                   # Non-empty property title
    'category': str,               # Property type/category
    'city': str,                   # City name
    'date': str,                   # Auction date (any format, will be cleaned)
    'bankName': str,               # Bank/institution name
    'reservePrice': float,         # Reserve price (numeric)
    'emd': float,                  # EMD amount (numeric)
    'state': str,                  # State name (from config)
    'source': str,                 # Scraper identifier (e.g., "baanknet")
    'url': str,                    # Property detail page URL
    
    # Optional fields (can be empty string)
    'branchName': str,
    'serviceProvider': str,
    'contactDetails': str,
    'description': str,
    'areaTown': str,
    'borrowerName': str,
    'propertyType': str,
    'auctionStartDate': str,
    'auctionEndTime': str,
    'auctionType': str,
    'applicationSubmissionDate': str,
    'images': str,
    'notice': str
}
```

### Progress Callback Protocol

```python
def progress_callback(message: str) -> None:
    """
    Called periodically during scraping to report progress.
    
    Args:
        message (str): Human-readable progress message
                      Example: "[BaankNet] Scraping 15/50"
    """
    pass
```

---

## Configuration

### Adding New States

**Step 1:** Add state to `config.py`:

```python
STATES = ["Delhi", "Gujarat", "Maharashtra", "Rajasthan", "Karnataka"]
```

**Step 2:** Add state IDs for each scraper:

```python
BAANKNET_STATE_IDS = {
    # ... existing states
    "Karnataka": "15"  # Find correct ID from site
}

BANKAUCTIONS_STATE_IDS = {
    # ... existing states
    "Karnataka": "10"  # Find correct ID from site
}
```

**Step 3:** Test each scraper individually:

```python
from scrapers import baanknet
properties = baanknet.scrape("Karnataka")
print(f"Found {len(properties)} properties")
```

### Adding New Property Types

**Step 1:** Add type to `config.py`:

```python
PROPERTY_TYPES = [
    "Flat",
    "Commercial Property",
    "Land and Building",
    "Land",
    "Commercial Shop",
    "Villa"  # New type
]
```

**Step 2:** Test eAuctionsIndia scraper (only scraper that filters by type).

### Adding New Scrapers

**Step 1:** Create scraper module `scrapers/newscraper.py`:

```python
"""NewScraper scraper"""
import requests
from bs4 import BeautifulSoup

def scrape(state, progress_callback=None):
    """Scrape properties from NewScraper"""
    print(f"[NewScraper] Starting scrape for {state}")
    
    properties = []
    
    # Your scraping logic here
    # ...
    
    return properties
```

**Step 2:** Register in `scrapers/__init__.py`:

```python
from . import baanknet
from . import bankauctions
from . import eauctionsindia
from . import bankauction
from . import newscraper  # Add this

__all__ = ['baanknet', 'bankauctions', 'eauctionsindia', 'bankauction', 'newscraper']
```

**Step 3:** Add to `scraper_runner.py`:

```python
from scrapers import baanknet, bankauctions, eauctionsindia, bankauction, newscraper

all_scrapers = {
    'eauctionsindia': (eauctionsindia.scrape, 'eAuctionsIndia'),
    'baanknet': (baanknet.scrape, 'BaankNet'),
    'bankauctions': (bankauctions.scrape, 'BankEAuctions'),
    'bankauction': (bankauction.scrape, 'BankAuction.in'),
    'newscraper': (newscraper.scrape, 'NewScraper')  # Add this
}
```

**Step 4:** Add to GUI (`gui.py`):

```python
sites = [
    ('eAuctionsIndia', 'eauctionsindia'),
    ('BaankNet', 'baanknet'),
    ('BankEAuctions', 'bankauctions'),
    ('BankAuction.in', 'bankauction'),
    ('NewScraper', 'newscraper')  # Add this
]
```

**Step 5:** Add to build spec (`build.spec`):

```python
hiddenimports=[
    # ... existing imports
    'scrapers.newscraper'  # Add this
]
```

---

## Error Handling

### Error Handling Strategy

**Philosophy:** Fail gracefully, continue with other tasks, log errors comprehensively.

### Levels of Error Handling

#### 1. Scraper-Level Errors

**Handled by:** `run_single_scraper()` in `scraper_runner.py`

```python
try:
    items = scraper_func(state)
    return {'items': items, 'error': None}
except Exception as e:
    print(f"[{scraper_name}] ✗ Error for {state}: {e}")
    return {'items': [], 'error': str(e)}
```

**Behavior:**
- Exception logged to console
- Empty list returned
- Other scrapers continue execution

#### 2. Property-Level Errors

**Handled by:** Individual scraper functions

```python
def scrape_single_property(card, state):
    try:
        # Extract property data
        return property_dict
    except Exception as e:
        print(f"[Scraper] Error scraping property: {e}")
        return None  # Skip this property
```

**Behavior:**
- Exception logged
- Property skipped
- Other properties continue

#### 3. Network Errors

**Handled by:** Retry logic with exponential backoff

```python
max_retries = 5
for retry in range(max_retries):
    try:
        response = requests.get(url, timeout=30)
        break
    except (ConnectionError, Timeout) as e:
        if retry < max_retries - 1:
            wait = 2 ** retry
            time.sleep(wait)
        else:
            raise  # Give up after max retries
```

**Behavior:**
- Retry with increasing delays (2, 4, 8, 16, 32 seconds)
- Log each retry attempt
- Skip item after max retries

#### 4. Data Validation Errors

**Handled by:** Data sanitization functions

```python
# Invalid date format
date = clean_date_to_standard_format(raw_date)
if date is None:
    # Skip entire property
    print(f"[Warning] Invalid date: {raw_date}")
    continue

# Text too long for Excel
text = sanitize_text_for_excel(raw_text, max_length=32767)
```

**Behavior:**
- Invalid data results in property being skipped
- Warning logged
- Other properties continue

#### 5. GUI Errors

**Handled by:** `run_scraping_thread()` in `gui.py`

```python
try:
    output_file = run_scrapers(...)
    messagebox.showinfo("Success", f"Scraping completed!\n\nOutput: {output_file}")
except Exception as e:
    messagebox.showerror("Error", f"An error occurred:\n\n{str(e)}")
    self.log(f"Error details: {str(e)}")
```

**Behavior:**
- Error displayed to user in dialog box
- Error logged to activity log
- GUI remains responsive

### Common Error Scenarios

| Error Type | Cause | Handling |
|-----------|-------|----------|
| **ConnectionError** | Network unavailable | Retry with backoff |
| **Timeout** | Slow server response | Retry with backoff |
| **HTTPError (4xx)** | Invalid request/URL | Log and skip |
| **HTTPError (5xx)** | Server error | Retry with backoff |
| **JSONDecodeError** | Invalid JSON response | Log and skip |
| **AttributeError** | Missing HTML element | Log and skip |
| **KeyError** | Missing dict key | Log and skip |
| **ValueError** | Invalid data format | Sanitize or skip |
| **PermissionError** | Cannot write file | Show error dialog |

---

## Performance Optimization

### Parallel Execution

**Configuration:**

```python
# Scraper-level parallelism (scraper_runner.py)
ThreadPoolExecutor(max_workers=20)  # 20 scrapers running simultaneously

# Property-level parallelism (individual scrapers)
ThreadPoolExecutor(max_workers=10)  # BaankNet
ThreadPoolExecutor(max_workers=20)  # eAuctionsIndia
ThreadPoolExecutor(max_workers=15)  # BankAuctions
```

**Rationale:**
- I/O-bound operations (network requests)
- GIL (Global Interpreter Lock) not a bottleneck
- 20 workers × 4 scrapers = up to 80 concurrent requests

### Request Optimization

**Session Reuse:**
```python
session = requests.Session()
session.headers.update({'User-Agent': '...'})
# Session maintains connection pool for faster requests
```

**Timeout Configuration:**
```python
response = requests.get(url, timeout=30)
# Prevents hanging indefinitely on slow servers
```

**SSL Verification (Disabled for Speed):**
```python
requests.get(url, verify=False)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

### Data Processing

**Incremental Filtering:**
- Filter by property type during scraping (not after)
- Check duplicates before adding to list
- Skip invalid dates immediately

**Efficient Deduplication:**
- MD5 hashing: O(1) lookup time
- In-memory set: `fingerprint in seen_db.seen`
- File writes batched (not per property)

### Memory Management

**Streaming Processing:**
- Properties processed as they're scraped
- Not all stored in memory before filtering
- Excel file written once at end

**Generator Pattern (Potential Improvement):**
```python
# Current: Return full list
return properties

# Improved: Yield properties one by one
yield property
```

### Performance Metrics

**Typical Scraping Times (4 states, 4 scrapers):**

| Metric | Value |
|--------|-------|
| Total tasks | 16 (4 scrapers × 4 states) |
| Parallel workers | 20 |
| Properties per state | 50-200 |
| Total properties | 500-1000 |
| **Total execution time** | **2-5 minutes** |
| Properties/second | 3-8 |
| Network requests | 500-2000 |

**Bottlenecks:**
1. Network latency (largest factor)
2. Server response time (varies by site)
3. HTML parsing (minimal)
4. Excel file writing (< 1 second)

---

## Security Considerations

### Network Security

**SSL/TLS:**
- SSL verification disabled for compatibility
- **Risk:** Vulnerable to man-in-the-middle attacks
- **Mitigation:** Only scraping public data (no authentication)

**User-Agent Spoofing:**
```python
headers = {"User-Agent": "Mozilla/5.0"}
```
- **Purpose:** Avoid bot detection
- **Risk:** Violates some sites' Terms of Service
- **Mitigation:** Scraping public data, respectful rate limiting

### Data Security

**Local Storage:**
- All data stored locally (no cloud transmission)
- Database file (`seen_properties.json`) contains only fingerprints (no PII)
- Excel files contain scraped public data

**No Authentication:**
- No user credentials required
- No API keys stored
- No sensitive data processed

### Code Security

**Dependency Management:**
```plaintext
# requirements.txt specifies minimum versions
requests>=2.31.0  # Security patches included
```

**Input Validation:**
```python
# Sanitize user input from GUI
output_folder = self.output_folder_entry.get().strip()
if not output_folder:
    output_folder = "./output"

# Validate state selection
if state not in STATES:
    return []
```

**Path Safety:**
```python
# Use os.path.join for cross-platform compatibility
output_path = os.path.join(output_folder, filename)

# Avoid path traversal
output_folder = os.path.abspath(output_folder)
```

### Legal & Ethical Considerations

**Web Scraping Compliance:**
- Scraping public auction data (no authentication required)
- Respectful rate limiting (delays between requests)
- No evasion of technical protection measures
- Data used for informational purposes only

**Robots.txt:**
- Some sites may have robots.txt restrictions
- Current implementation does not check robots.txt
- **Recommendation:** Add robots.txt compliance check

**Terms of Service:**
- Review each site's ToS before scraping
- Some sites explicitly prohibit automated scraping
- Use at own risk

---

## Maintenance & Troubleshooting

### Common Issues

#### 1. Scraper Returns Empty Results

**Symptoms:**
- Scraper completes but finds 0 properties
- Log shows: "Found 0 total pages" or "No properties found"

**Possible Causes:**
1. Site HTML structure changed
2. Site blocking scrapers (user-agent, rate limiting)
3. Incorrect state ID in config
4. Network connectivity issues

**Debugging Steps:**

```python
# Add debug logging
print(f"Response status: {response.status_code}")
print(f"Response length: {len(response.text)}")
print(f"First 500 chars: {response.text[:500]}")

# Save HTML to file for inspection
with open('debug.html', 'w', encoding='utf-8') as f:
    f.write(response.text)
```

**Solution:**
1. Inspect HTML structure using browser DevTools
2. Update CSS selectors in scraper
3. Check if site changed pagination format
4. Verify network connectivity

#### 2. "Could not find CSRF meta tag" (BaankNet)

**Symptoms:**
- BaankNet scraper fails immediately
- Error: "ERROR: Could not find CSRF meta tag"

**Cause:**
- Site changed CSRF token location/name
- Home page structure changed

**Solution:**

```python
# Inspect home page HTML
home = session.get("https://baanknet.com/eauction-psb/home")
print(home.text)  # Search for token

# Update CSRF extraction
csrf_meta = soup.find("meta", {"name": "_csrf"})  # Old
csrf_meta = soup.find("meta", {"name": "csrf-token"})  # Try new name
```

#### 3. "Connection reset by peer" (BankAuctions)

**Symptoms:**
- BankAuctions scraper fails intermittently
- Error: "ConnectionResetError" or "Connection aborted"

**Cause:**
- Server rate limiting
- Server instability
- Too many concurrent requests

**Solution:**
- Already implemented: Retry logic with exponential backoff
- Reduce concurrent workers: `max_workers=15` → `max_workers=10`
- Add delays between requests: `time.sleep(1)`

#### 4. Invalid Date Formats

**Symptoms:**
- Properties removed during processing
- Log: "Invalid dates removed: X"

**Cause:**
- New date format not handled by `clean_date_to_standard_format()`

**Solution:**

```python
# Add new format to clean_date_to_standard_format()
if 'Jan' in date_str:  # Example: "Jan 15, 2025"
    # Add parsing logic
```

#### 5. Excel File Corruption

**Symptoms:**
- Excel file won't open
- Error: "File is corrupted"

**Cause:**
- Text exceeds 32,767 character limit (despite sanitization)
- Invalid characters in data

**Solution:**

```python
# More aggressive sanitization
def sanitize_text_for_excel(text, max_length=32000):  # Lower limit
    if not isinstance(text, str):
        return str(text)
    
    # Remove ALL control characters
    sanitized = ''.join(c for c in text if c.isprintable() or c in '\t\n\r')
    
    # Truncate earlier
    return sanitized[:max_length]
```

#### 6. GUI Freezes During Scraping

**Symptoms:**
- Window becomes unresponsive
- Progress bar doesn't update

**Cause:**
- Scraping running on main thread instead of background thread

**Verification:**

```python
# Check if threading.Thread is being used
thread = threading.Thread(target=self.run_scraping_thread, daemon=True)
thread.start()
```

**Solution:**
- Ensure `daemon=True` is set
- Verify callbacks use `self.root.after()` for GUI updates

### Updating Dependencies

**Check for Updates:**
```bash
pip list --outdated
```

**Update Individual Package:**
```bash
pip install --upgrade requests
```

**Update All Packages:**
```bash
pip install --upgrade -r requirements.txt
```

**Test After Updates:**
```bash
python gui.py  # Test GUI
python -c "from scrapers import baanknet; print(baanknet.scrape('Delhi'))"  # Test scraper
```

### Logging & Debugging

**Enable Debug Logging:**

```python
# Add to top of scraper_runner.py
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='scraper.log'
)
```

**Inspect Network Requests:**

```python
# Add requests logging
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1
```

**Profile Performance:**

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Run scraper
run_scrapers(...)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)  # Top 20 slowest functions
```

### Site Change Detection

**Automated Testing:**

```python
# test_scrapers.py
import unittest
from scrapers import baanknet, eauctionsindia

class TestScrapers(unittest.TestCase):
    def test_baanknet_returns_results(self):
        properties = baanknet.scrape("Delhi")
        self.assertGreater(len(properties), 0, "BaankNet returned no results")
    
    def test_eauctionsindia_returns_results(self):
        properties = eauctionsindia.scrape("Delhi")
        self.assertGreater(len(properties), 0, "eAuctionsIndia returned no results")

if __name__ == '__main__':
    unittest.main()
```

**Run Tests:**
```bash
python test_scrapers.py
```

**Schedule Regular Tests:**
- Run tests weekly to detect site changes early
- Set up notifications for test failures

---

## Appendix

### A. Excel Output Schema

**File Name Format:**
```
auctions_YYYY-MM-DD_HH-MM-SS_mmm.xlsx
Example: auctions_2025-12-03_14-30-45_123.xlsx
```

**Sheet Name:** `Auctions`

**Columns:** (29 total)

| Column Name | Data Type | Description |
|------------|-----------|-------------|
| listingId | Text | Unique property ID from source |
| name | Text | Property title/name |
| category | Text | Property category |
| city | Text | City name |
| date | Text (DD-MM-YYYY) | Auction date |
| bankName | Text | Bank/institution name |
| reservePrice | Number | Reserve price in INR |
| emd | Number | EMD amount in INR |
| branchName | Text | Bank branch name |
| serviceProvider | Text | Auction service provider |
| contactDetails | Text | Contact information |
| description | Text | Property description |
| state | Text | State name |
| areaTown | Text | Area/district |
| borrowerName | Text | Original borrower |
| propertyType | Text | Detailed property type |
| auctionStartDate | Text | Auction start date |
| auctionEndTime | Text | Auction end date/time |
| auctionType | Text | Type of auction |
| applicationSubmissionDate | Text | Last date for submission |
| images | Text (URL) | Image URL |
| notice | Text (URL) | Notice document URL |
| source | Text | Scraper identifier |
| url | Text (URL) | Property detail page URL |
| fingerprint | Text | MD5 hash for deduplication |

### B. State & City Mappings

**Supported States:**
- Delhi
- Gujarat (Cities: Ahmedabad, Surat, Vadodara)
- Maharashtra (Cities: Mumbai, Pune)
- Rajasthan (City: Jaipur)

**BaankNet State IDs:**
```python
{
    "Delhi": "9",
    "Gujarat": "11",
    "Maharashtra": "21",
    "Rajasthan": "29"
}
```

**BankAuctions State IDs:**
```python
{
    "Delhi": "29",
    "Gujarat": "7",
    "Maharashtra": "15",
    "Rajasthan": "22"
}
```

### C. Date Format Examples

**Supported Input Formats:**

| Input Format | Example | Output Format |
|-------------|---------|---------------|
| DD MMM YYYY HH:MM | 21 Nov 2025 11:00 | 21-11-2025 |
| DD-MM-YYYY HH:MM AM/PM | 03-12-2025 11:00 AM | 03-12-2025 |
| DD/MM/YYYY HH:MM | 15/11/2025 14:30 | 15-11-2025 |
| DD MMM YYYY | 18 Nov 2025 | 18-11-2025 |
| DD-MM-YYYY | 25-12-2025 | 25-12-2025 |

**Invalid Formats:**
- Empty string → Removed
- "N/A" → Removed
- "TBD" → Removed
- Unparseable formats → Removed

### D. Glossary

| Term | Definition |
|------|------------|
| **EMD** | Earnest Money Deposit - Security deposit for auction participation |
| **Reserve Price** | Minimum price for property sale |
| **CSRF Token** | Cross-Site Request Forgery token for security |
| **Fingerprint** | MD5 hash used for duplicate detection |
| **ThreadPoolExecutor** | Python's built-in parallel execution framework |
| **PyInstaller** | Tool for creating standalone executables from Python scripts |
| **CustomTkinter** | Modern GUI framework for Python |
| **BeautifulSoup** | HTML/XML parsing library |
| **OpenPyXL** | Library for reading/writing Excel files |

### E. Contact & Support

**For Technical Issues:**
- Check logs in application directory
- Review error messages in GUI log panel
- Refer to troubleshooting section above

**For Site Changes:**
- Inspect HTML structure using browser DevTools
- Update CSS selectors in respective scraper module
- Test changes with small dataset before full scrape

**For Feature Requests:**
- Add new scrapers following the pattern in existing modules
- Register new scrapers in `scraper_runner.py` and `gui.py`
- Update `build.spec` with new hidden imports

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-03 | Initial release with 4 scrapers, parallel execution, GUI |

---

**END OF TECHNICAL DOCUMENTATION**

---

*This documentation is intended for software development AI agents and human developers who need to understand, maintain, or extend the Raahi Property Scraper application.*
