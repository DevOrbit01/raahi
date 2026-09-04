import hashlib
from datetime import datetime

import requests
import urllib3

from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://baanknet.com"
LISTING_URL = f"{BASE_URL}/vehicle-listing"
API_URL = f"{BASE_URL}/api/v1/vehicle/bidder/listing"
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


def _make_session():
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": LISTING_URL,
    })
    return session


def _unwrap_items(response_json):
    data = response_json.get("data", {}) if isinstance(response_json, dict) else {}
    items = data.get("vehicles", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    return data if isinstance(data, dict) else {}, items


def _images(source):
    urls = []
    for photo in source.get("photos") or []:
        if not isinstance(photo, dict):
            continue
        url = photo.get("url")
        if url:
            urls.append(url)
    return ",".join(urls)


def _documents(source):
    urls = []
    for document in source.get("documents") or []:
        if not isinstance(document, dict):
            continue
        url = document.get("url") or document.get("fileUrl")
        if url:
            urls.append(url)
    return ",".join(urls)


def _computed_emd(source):
    for amount_key in ("emd", "emdAmount"):
        amount = source.get(amount_key)
        if amount not in (None, ""):
            return amount

    price = source.get("auctionPrice") or source.get("price")
    percentage = source.get("emdPercentage")
    try:
        return round(float(price) * float(percentage) / 100, 2)
    except (TypeError, ValueError):
        return ""


def _map_vehicle(item, state):
    source = item.get("_source", item) if isinstance(item, dict) else {}
    if not isinstance(source, dict):
        return None

    vehicle_id = source.get("vehicleId")
    asset_id = source.get("assetId")
    if not vehicle_id and not asset_id:
        return None

    listing_id = asset_id or vehicle_id
    heading = source.get("vehicleHeading") or _join_non_empty(
        source.get("registrationYear"),
        source.get("vehicleBrandName"),
        source.get("vehicleModel"),
        "for sale in",
        source.get("repossessionCity"),
        source.get("repossessionState"),
    )
    if not heading:
        return None

    auction_id = source.get("auctionId")
    detail_url = _secure_url(f"/vehicle-detail/{vehicle_id}") if vehicle_id else LISTING_URL
    auction_url = _secure_url(f"/vehicle-auction-detail/{auction_id}") if auction_id else detail_url
    address = _join_non_empty(
        source.get("parkingYardAddress"),
        source.get("repossessionCity"),
        source.get("repossessionDistrict"),
        source.get("repossessionState"),
        source.get("repossessionPincode"),
    )
    owner_address = source.get("ownerAddress", "")
    if not address:
        address = owner_address

    description = _join_non_empty(
        source.get("description"),
        source.get("registrationNo"),
        source.get("vehicleFuelType"),
        source.get("transmissionType"),
        source.get("vehicleOdometerReading"),
        source.get("loanType"),
    )
    pdf_links = _documents(source)

    return {
        "newListingId": "",
        "schemeName": f"{heading} BANK AUCTION".upper(),
        "name": heading,
        "category": source.get("vehicleType") or "Vehicle",
        "state": source.get("repossessionState") or state,
        "city": source.get("repossessionCity", ""),
        "areaTown": source.get("repossessionDistrict", ""),
        "date": _first_date(source.get("auctionStartTime") or source.get("createdOn") or source.get("verifiedOn")),
        "reservePrice": source.get("auctionPrice") or source.get("price", ""),
        "emd": _computed_emd(source),
        "incrementBid": source.get("incrementPrice", "") or source.get("incrementPriceExtension", ""),
        "bankName": source.get("bankName", ""),
        "branchName": source.get("parkingYardName", ""),
        "contactDetails": _join_non_empty(source.get("inspectionName"), source.get("inspectionMobileNo")),
        "description": description,
        "address": address,
        "note": source.get("possessionType", ""),
        "borrowerName": source.get("borrowerName", ""),
        "publishingDate": _format_datetime(source.get("createdOn")),
        "inspectionDate": _format_datetime(source.get("inspectionStart")),
        "applicationSubmissionDate": _format_datetime(source.get("emdEndTime")),
        "auctionStartDate": _format_datetime(source.get("auctionStartTime")),
        "auctionEndTime": _format_datetime(source.get("auctionEndTime")),
        "auctionType": "Vehicle",
        "listingId": listing_id,
        "images": _images(source),
        "pdfLinks": pdf_links,
        "notice": auction_url,
        "source": "baanknet_vehicle",
        "url": detail_url,
    }


def scrape(state, progress_callback=None):
    print(f"[BaankNet Vehicle] Starting scrape for {state}")

    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet Vehicle] State {state} not supported")
        return []

    session = _make_session()
    try:
        session.get(LISTING_URL, timeout=30)
    except requests.RequestException as exc:
        print(f"[BaankNet Vehicle] Connection error: {exc}")
        return []

    state_id = int(BAANKNET_STATE_IDS[state])
    vehicles = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        payload = {
            "search": {"repossessionStateId": state_id},
            "sort": {"type": "mostrecent"},
            "range": "",
            "page": page,
        }

        print(f"[BaankNet Vehicle] Fetching page {page}...")
        if progress_callback:
            progress_callback(f"[BaankNet Vehicle] Fetching page {page}...")

        try:
            resp = session.post(API_URL, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet Vehicle] Page {page} failed with status {resp.status_code}")
                break
            page_data, items = _unwrap_items(resp.json())
        except (requests.RequestException, ValueError) as exc:
            print(f"[BaankNet Vehicle] Error fetching page {page}: {exc}")
            break

        if not items:
            print(f"[BaankNet Vehicle] No more vehicles found on page {page}")
            break

        for item in items:
            source = item.get("_source", item) if isinstance(item, dict) else {}
            listing_id = source.get("assetId") or source.get("vehicleId")
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)
            mapped = _map_vehicle(item, state)
            if mapped:
                vehicles.append(mapped)

        total_pages = page_data.get("totalPages")
        current_page = page_data.get("currentPage", page)
        print(f"[BaankNet Vehicle] Page {page}: {len(items)} items, {len(vehicles)} kept")

        if total_pages and current_page >= total_pages:
            break

    print(f"[BaankNet Vehicle] Finished. Total vehicles: {len(vehicles)}")
    return vehicles
