import hashlib
from datetime import datetime

import requests
import urllib3

from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://baanknet.com"
LISTING_URL = f"{BASE_URL}/property-listing"
API_URL = f"{BASE_URL}/api/v1/property/detail/property-filter"
AUCTION_DETAIL_API_URL = f"{BASE_URL}/api/v1/auction/detail"
MAX_PAGES = 100


def _secure_url(path):
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()
    return f"{BASE_URL}{path}/{digest}"


def _format_datetime(value):
    if not value:
        return ""
    if not isinstance(value, str):
        return str(value)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return value


def _first_date(value):
    formatted = _format_datetime(value)
    return formatted.split(" ")[0] if formatted else ""


def _join_non_empty(*parts):
    return " ".join(str(part).strip() for part in parts if part not in (None, ""))


def _unwrap_items(response_json):
    data = response_json.get("data", {}) if isinstance(response_json, dict) else {}
    items = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    return data if isinstance(data, dict) else {}, items


def _make_session():
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": LISTING_URL,
    })
    return session


def _images(source):
    photos = source.get("photos") or []
    urls = [photo for photo in photos if isinstance(photo, str) and photo.startswith(("http://", "https://"))]
    display_image = source.get("displayImage")
    if not urls and display_image:
        if str(display_image).startswith(("http://", "https://")):
            urls.append(str(display_image))
        else:
            urls.append(f"https://cdn.baanknet.com/{str(display_image).lstrip('/')}")
    return ",".join(urls)


def _document_links(documents):
    urls = []
    for document in documents or []:
        if isinstance(document, dict) and document.get("url"):
            urls.append(document["url"])
    return ",".join(urls)


def _fetch_auction_details(session, auction_id):
    if not auction_id:
        return {}
    try:
        resp = session.get(f"{AUCTION_DETAIL_API_URL}/{auction_id}", timeout=30)
        if resp.status_code != 200:
            return {}
        data = resp.json()
    except (requests.RequestException, ValueError):
        return {}
    details = data.get("data", data) if isinstance(data, dict) else {}
    return details if isinstance(details, dict) else {}


def _map_property(item, state, source_name):
    source = item.get("_source", item) if isinstance(item, dict) else {}
    if not isinstance(source, dict):
        return None

    property_id = source.get("propertyDetailId") or source.get("propertyUniqueId")
    if not property_id:
        return None

    property_type = source.get("propertyType") or ""
    property_sub_type = source.get("propertySubType") or source.get("specificPropSubType") or ""
    city = source.get("cityName") or ""
    locality = source.get("locality") or ""
    heading = source.get("propertyHeading") or _join_non_empty(property_sub_type, "for sale in", locality, city)
    if not heading.strip():
        return None

    contact = _join_non_empty(
        source.get("departmentName"),
        source.get("inspectionName"),
        source.get("inspectionMobileNo"),
    )
    auction_id = source.get("auctionId")
    auction_details = _fetch_auction_details(item.get("_session"), auction_id) if item.get("_session") else {}

    notice = _secure_url(f"/property-detail/{property_id}")
    auction_notice = _secure_url(f"/auction-detail/{auction_id}") if auction_id else notice
    reserve_price = auction_details.get("reservePrice", source.get("auctionPrice"))
    if reserve_price in (None, ""):
        reserve_price = source.get("propertyPrice", 0)
    full_address = auction_details.get("address") or source.get("address")
    if not full_address:
        full_address = _join_non_empty(source.get("locality"), source.get("cityName"), source.get("districtName"), source.get("stateName"), source.get("pincode"))
    pdf_links = _document_links(auction_details.get("auctionDocuments"))

    return {
        "newListingId": "",
        "schemeName": f"{heading} BANK AUCTION".upper(),
        "name": heading,
        "category": property_sub_type or property_type,
        "state": source.get("stateName") or state,
        "city": city,
        "areaTown": source.get("districtName", ""),
        "date": _first_date(source.get("auctionStartTime") or source.get("createdOn")),
        "reservePrice": reserve_price,
        "emd": auction_details.get("emd", ""),
        "incrementBid": auction_details.get("incrementPrice", "") or auction_details.get("incrementPriceExtension", ""),
        "bankName": auction_details.get("propertyBankName") or source.get("bankName", ""),
        "branchName": auction_details.get("propertyBranchName") or source.get("departmentName", ""),
        "contactDetails": contact,
        "description": auction_details.get("description") or _join_non_empty(source.get("borrowerAddress"), source.get("branchAddress")),
        "address": full_address,
        "note": pdf_links,
        "borrowerName": auction_details.get("borrowerName") or source.get("borrowerName", ""),
        "publishingDate": _format_datetime(source.get("createdOn")),
        "inspectionDate": _format_datetime(auction_details.get("inspectionStart") or source.get("inspectionStart")),
        "applicationSubmissionDate": _format_datetime(auction_details.get("emdEnd") or source.get("emdEndTime")),
        "auctionStartDate": _format_datetime(auction_details.get("auctionFrom") or source.get("auctionStartTime")),
        "auctionEndTime": _format_datetime(auction_details.get("auctionTo") or source.get("auctionEndTime")),
        "auctionType": auction_details.get("typeOfAction") or source.get("propTypeOfAction", ""),
        "listingId": source.get("propertyUniqueId") or property_id,
        "images": _images(source),
        "pdfLinks": pdf_links,
        "notice": auction_notice,
        "source": source_name,
        "url": notice,
    }


def scrape(state, progress_callback=None, source_name="baanknet_property", auction_available_only=False):
    print(f"[BaankNet Property] Starting scrape for {state}")

    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet Property] State {state} not supported")
        return []

    session = _make_session()
    try:
        session.get(LISTING_URL, timeout=30)
    except requests.RequestException as exc:
        print(f"[BaankNet Property] Connection error: {exc}")
        return []

    state_id = int(BAANKNET_STATE_IDS[state])
    properties = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        payload = {
            "search": {"stateId": state_id},
            "sort": {"type": "mostrecent"},
            "range": "",
            "page": page,
        }

        print(f"[BaankNet Property] Fetching page {page}...")
        if progress_callback:
            progress_callback(f"[BaankNet Property] Fetching page {page}...")

        try:
            resp = session.post(API_URL, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet Property] Page {page} failed with status {resp.status_code}")
                break
            page_data, items = _unwrap_items(resp.json())
        except (requests.RequestException, ValueError) as exc:
            print(f"[BaankNet Property] Error fetching page {page}: {exc}")
            break

        if not items:
            print(f"[BaankNet Property] No more items found on page {page}")
            break

        for item in items:
            source = item.get("_source", item) if isinstance(item, dict) else {}
            if auction_available_only and not source.get("isAuctionAvailable"):
                continue
            property_id = source.get("propertyDetailId")
            if property_id in seen_ids:
                continue
            seen_ids.add(property_id)
            if isinstance(item, dict):
                item["_session"] = session
            mapped = _map_property(item, state, source_name)
            if mapped:
                properties.append(mapped)

        total_pages = page_data.get("totalPages")
        current_page = page_data.get("currentPage", page)
        print(f"[BaankNet Property] Page {page}: {len(items)} items, {len(properties)} kept")

        if total_pages and current_page >= total_pages:
            break

    print(f"[BaankNet Property] Finished. Total properties: {len(properties)}")
    return properties
