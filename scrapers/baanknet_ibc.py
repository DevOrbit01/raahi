import hashlib
from datetime import datetime

import requests
import urllib3

from config import BAANKNET_STATE_IDS

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://ibbi.baanknet.com"
LISTING_URL = f"{BASE_URL}/asset-listing"
API_URL = f"{BASE_URL}/api/v1/asset/bidder/listing"
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
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
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


def _location(source):
    locations = source.get("location") or source.get("companyAddress") or []
    if isinstance(locations, list) and locations:
        first = locations[0]
        if isinstance(first, dict):
            return first
    return {}


def _images(source):
    media = source.get("media") or []
    urls = []
    for item in media:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url and item.get("filetype", 1) == 1:
            urls.append(url)
    main_image = source.get("mainImage")
    if not urls and main_image:
        if str(main_image).startswith(("http://", "https://")):
            urls.append(str(main_image))
        else:
            urls.append(f"https://dtra8ij9rfx2n.cloudfront.net/{str(main_image).lstrip('/')}")
    return ",".join(urls)


def _documents(source):
    docs = []
    for item in source.get("document") or []:
        if isinstance(item, dict) and item.get("url"):
            docs.append(item["url"])
    return ",".join(docs)


def _map_asset(item, state):
    source = item.get("_source", item) if isinstance(item, dict) else {}
    if not isinstance(source, dict):
        return None

    asset_id = source.get("assetId")
    if not asset_id:
        return None

    loc = _location(source)
    asset_name = source.get("assetName") or ""
    company_name = source.get("companyName") or ""
    detail_url = _secure_url(f"/bidder/asset-detail/{asset_id}")
    auction_id = source.get("auctionId")
    auction_url = _secure_url(f"/auction-detail/{auction_id}") if auction_id else detail_url
    contact = _join_non_empty(source.get("ipName"), source.get("ipMobileNo"), source.get("ipEmail"))
    description = source.get("assetSummary") or loc.get("address") or source.get("otherDetail") or ""
    reserve_price = source.get("auctionReservePrice")
    if reserve_price in (None, ""):
        reserve_price = "0"

    return {
        "newListingId": "",
        "schemeName": f"{asset_name} - {company_name}".upper(),
        "name": asset_name,
        "category": source.get("assetClassificationSubtype") or source.get("assetClassification") or source.get("assetType") or "IBC Asset",
        "state": loc.get("state") or state,
        "city": loc.get("city", ""),
        "areaTown": loc.get("district", ""),
        "date": _first_date(source.get("auctionStartTime") or source.get("createdOn")),
        "reservePrice": reserve_price,
        "emd": "",
        "incrementBid": "",
        "bankName": company_name,
        "branchName": "IBC",
        "contactDetails": contact,
        "description": description,
        "address": _join_non_empty(loc.get("address"), loc.get("city"), loc.get("district"), loc.get("state"), loc.get("pincode")),
        "note": _documents(source),
        "borrowerName": company_name,
        "publishingDate": _format_datetime(source.get("createdOn")),
        "inspectionDate": "",
        "applicationSubmissionDate": _format_datetime(source.get("emdEndTime")),
        "auctionStartDate": _format_datetime(source.get("auctionStartTime")),
        "auctionEndTime": _format_datetime(source.get("auctionEndTime")),
        "auctionType": "IBC",
        "listingId": asset_id,
        "images": _images(source),
        "pdfLinks": _documents(source),
        "notice": auction_url,
        "source": "baanknet_ibc",
        "url": detail_url,
    }


def scrape(state, progress_callback=None):
    print(f"[BaankNet IBC] Starting scrape for {state}")

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
    properties = []
    seen_ids = set()

    for page in range(1, MAX_PAGES + 1):
        payload = {
            "search": {"stateId": state_id},
            "sort": "mostrecent",
            "page": page,
        }

        print(f"[BaankNet IBC] Fetching page {page}...")
        if progress_callback:
            progress_callback(f"[BaankNet IBC] Fetching page {page}...")

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
            print(f"[BaankNet IBC] No more items found on page {page}")
            break

        for item in items:
            source = item.get("_source", item) if isinstance(item, dict) else {}
            asset_id = source.get("assetId")
            if asset_id in seen_ids:
                continue
            seen_ids.add(asset_id)
            mapped = _map_asset(item, state)
            if mapped:
                properties.append(mapped)

        total_pages = page_data.get("totalPages")
        current_page = page_data.get("currentPage", page)
        print(f"[BaankNet IBC] Page {page}: {len(items)} items, {len(properties)} kept")

        if total_pages and current_page >= total_pages:
            break

    print(f"[BaankNet IBC] Finished. Total properties: {len(properties)}")
    return properties
