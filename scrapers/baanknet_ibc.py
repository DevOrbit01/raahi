import hashlib
from datetime import datetime

import requests
import urllib3

from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://ibbi.baanknet.com"
LISTING_URL = f"{BASE_URL}/auction-listing"
API_URL = f"{BASE_URL}/api/v1/auction/bidder/listing"
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
    items = data.get("data", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        items = []
    return data if isinstance(data, dict) else {}, items


def _first_location(source):
    locations = source.get("companyLocation") or source.get("location") or []
    if isinstance(locations, list) and locations:
        first = locations[0]
        if isinstance(first, dict):
            return first
    if isinstance(locations, dict):
        return locations
    return {}


def _asset_names(source):
    names = []
    for asset in source.get("assets") or []:
        if isinstance(asset, dict):
            name = asset.get("assetName") or asset.get("assetSummary")
            if name:
                names.append(str(name).strip())
    return names


def _asset_categories(source):
    categories = []
    for asset in source.get("assets") or []:
        if not isinstance(asset, dict):
            continue
        for key in ("assetSubType", "assetClassification", "assetClass", "assetType"):
            value = asset.get(key)
            if value and value not in categories:
                categories.append(str(value).strip())
                break
    return categories


def _images(source):
    urls = []
    for item in source.get("media") or []:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url and item.get("filetype", 1) == 1:
            urls.append(url)
    return ",".join(urls)


def _documents(source):
    urls = []
    for item in source.get("documents") or source.get("document") or []:
        if not isinstance(item, dict):
            continue
        url = item.get("fileUrl") or item.get("url")
        if url:
            urls.append(url)
    return ",".join(urls)


def _status_text(status):
    labels = {
        1: "Upcoming",
        2: "Live",
        3: "Closed",
        4: "Cancelled",
        "1": "Upcoming",
        "2": "Live",
        "3": "Closed",
        "4": "Cancelled",
    }
    return labels.get(status, str(status) if status not in (None, "") else "IBC eAuction")


def _map_auction(item, state):
    source = item.get("_source", item) if isinstance(item, dict) else {}
    if not isinstance(source, dict):
        return None

    auction_id = source.get("auctionId")
    if not auction_id:
        return None

    loc = _first_location(source)
    names = _asset_names(source)
    categories = _asset_categories(source)
    company_name = source.get("companyName") or ""
    title = source.get("auctionBrief") or (names[0] if names else company_name)
    if not title:
        return None

    detail_url = _secure_url(f"/auction-detail/{auction_id}")
    contact = _join_non_empty(
        source.get("authorizationOfficer"),
        source.get("authorizationPhone"),
        source.get("emailId"),
        source.get("inspectionOfficer"),
        source.get("inspectionPhone"),
    )
    address = _join_non_empty(
        loc.get("address"),
        loc.get("city"),
        loc.get("district"),
        loc.get("state"),
        loc.get("pincode"),
    )
    asset_summary = "; ".join(names)
    pdf_links = _documents(source)

    return {
        "newListingId": "",
        "schemeName": f"{title} - {company_name}".upper(),
        "name": title,
        "category": ", ".join(categories) or source.get("mannerOfSale") or "IBC eAuction",
        "state": loc.get("state") or state,
        "city": loc.get("city", ""),
        "areaTown": loc.get("district", ""),
        "date": _first_date(source.get("startDateTime") or source.get("createdOn")),
        "reservePrice": source.get("reservePrice", ""),
        "emd": source.get("emd", ""),
        "incrementBid": source.get("incrementPrice", "") or source.get("incrementPriceExtension", ""),
        "bankName": company_name,
        "branchName": source.get("mannerOfSale") or "IBC",
        "contactDetails": contact,
        "description": _join_non_empty(source.get("auctionBrief"), asset_summary),
        "address": address,
        "note": _status_text(source.get("status")),
        "borrowerName": company_name,
        "publishingDate": _format_datetime(source.get("createdOn")),
        "inspectionDate": _format_datetime(source.get("inspectionStart")),
        "applicationSubmissionDate": _format_datetime(source.get("lastPaymentDate")),
        "auctionStartDate": _format_datetime(source.get("startDateTime")),
        "auctionEndTime": _format_datetime(source.get("endDateTime")),
        "auctionType": "IBC eAuction",
        "listingId": auction_id,
        "images": _images(source),
        "pdfLinks": pdf_links,
        "notice": detail_url,
        "source": "baanknet_ibc",
        "url": detail_url,
    }


def scrape(state, progress_callback=None):
    print(f"[BaankNet IBC] Starting IBC eAuction scrape for {state}")

    if state not in BAANKNET_STATE_IDS:
        print(f"[BaankNet IBC] State {state} not supported")
        return []

    session = _make_session()
    try:
        session.get(LISTING_URL, timeout=30)
    except requests.RequestException as exc:
        print(f"[BaankNet IBC] Connection error: {exc}")
        return []

    state_id = int(BAANKNET_STATE_IDS[state])
    auctions = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        payload = {
            "search": {"stateId": state_id},
            "sort": "mostrecent",
            "page": page,
            "auctionStatus": "all",
        }

        print(f"[BaankNet IBC] Fetching eAuction page {page}...")
        if progress_callback:
            progress_callback(f"[BaankNet IBC] Fetching eAuction page {page}...")

        try:
            resp = session.post(API_URL, json=payload, timeout=30)
            if resp.status_code != 200:
                print(f"[BaankNet IBC] Page {page} failed with status {resp.status_code}")
                break
            page_data, items = _unwrap_items(resp.json())
        except (requests.RequestException, ValueError) as exc:
            print(f"[BaankNet IBC] Error fetching page {page}: {exc}")
            break

        if not items:
            print(f"[BaankNet IBC] No more auctions found on page {page}")
            break

        for item in items:
            source = item.get("_source", item) if isinstance(item, dict) else {}
            auction_id = source.get("auctionId")
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)
            mapped = _map_auction(item, state)
            if mapped:
                auctions.append(mapped)

        total_pages = page_data.get("totalPages")
        current_page = page_data.get("currentPage", page)
        print(f"[BaankNet IBC] Page {page}: {len(items)} items, {len(auctions)} kept")

        if total_pages and current_page >= total_pages:
            break

    print(f"[BaankNet IBC] Finished. Total IBC auctions: {len(auctions)}")
    return auctions
