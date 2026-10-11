"""eAuctionsIndia scraper."""
import re
import os
import time
import threading
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from config import STATES
from scrapers.local_browser import desktop_browser, browser_profile
from scrapers.scrape_progress import ScrapeProgress

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


BASE_URL = "https://www.eauctionsindia.com"
MAX_PAGES = 10000
REQUEST_DELAY = 0.4

STATE_URL_SLUGS = {
    "Andaman and Nicobar Islands": "andaman-and-nicobar-islands",
    "Dadra and Nagar Haveli and Daman and Diu": "dadra-and-nagar-haveli",
}


def _slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def _text_lines(soup):
    return [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]


def _clean_money(value):
    if value in (None, ""):
        return ""
    value = str(value)
    value = value.replace("₹", "").replace(",", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", value)
    if not match:
        return value
    number = float(match.group(1))
    lower = value.lower()
    if "cr" in lower:
        number *= 10000000
    elif "lac" in lower or "lakh" in lower:
        number *= 100000
    return int(number) if number.is_integer() else number


def _normalize_label(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _line_value(lines, labels):
    normalized_labels = [_normalize_label(label) for label in labels]
    for index, line in enumerate(lines):
        normalized_line = _normalize_label(line)
        for label, normalized_label in zip(labels, normalized_labels):
            if normalized_line == normalized_label and index + 1 < len(lines):
                return lines[index + 1]
            if normalized_line.startswith(normalized_label):
                value = re.sub(re.escape(label), "", line, flags=re.I).strip(" :-#")
                if value:
                    return value
    return ""


def _field_value(soup, labels):
    normalized_labels = {_normalize_label(label) for label in labels}
    for strong in soup.select("strong"):
        label_text = strong.get_text(" ", strip=True)
        if _normalize_label(label_text) not in normalized_labels:
            continue

        parent = strong.find_parent(["div", "li", "p"])
        if not parent:
            continue

        strong.extract()
        value = parent.get_text(" ", strip=True).strip(" :-")
        if value:
            return value

        sibling = strong.find_next_sibling()
        if sibling:
            value = sibling.get_text(" ", strip=True).strip(" :-")
            if value:
                return value
    return ""


def _block_value(soup, heading_text):
    heading = soup.find(lambda tag: tag.name in ("h1", "h2", "h3", "h4", "h5") and heading_text.lower() in tag.get_text(" ", strip=True).lower())
    if not heading:
        return ""
    container = heading.find_parent()
    if not container:
        return ""
    return container.get_text(" ", strip=True)


def _regex_value(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1).strip()
    return ""


def _extract_listing_links(soup):
    links = []
    seen = set()
    for anchor in soup.select('a[href*="/properties/"]'):
        href = anchor.get("href")
        if not href:
            continue
        url = urljoin(BASE_URL, href.split("#")[0])
        if url in seen:
            continue
        seen.add(url)
        links.append(url)
    return links


def _listing_urls(state, page):
    if state == "Dadra and Nagar Haveli and Daman and Diu":
        suffix = "" if page == 1 else f"/{page}"
        return [f"{BASE_URL}/properties-in-{slug}{suffix}" for slug in ("dadra-and-nagar-haveli", "daman-and-diu")]
    slug = STATE_URL_SLUGS.get(state, _slug(state))
    page_suffix = "" if page == 1 else f"/{page}"
    return [f"{BASE_URL}/properties-in-{slug}{page_suffix}"]


def _extract_links(soup, keywords):
    urls = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        text = anchor.get_text(" ", strip=True)
        haystack = f"{href} {text}".lower()
        if any(keyword in haystack for keyword in keywords):
            urls.append(urljoin(BASE_URL, href))
    return ",".join(dict.fromkeys(urls))


def _download_links(soup):
    heading = soup.find(lambda tag: tag.name in ("h4", "h5", "h6") and "download" in tag.get_text(" ", strip=True).lower())
    if not heading:
        return ""
    card = heading.find_parent(lambda tag: tag.has_attr("class") and "card" in tag.get("class", []))
    if not card:
        card = heading.find_parent()
    urls = []
    for anchor in card.select("a[href]") if card else []:
        href = anchor.get("href")
        if href and not href.startswith("javascript:"):
            urls.append(urljoin(BASE_URL, href))
    return ",".join(dict.fromkeys(urls))


IMAGE_EXTENSIONS = re.compile(r"\.(?:jpe?g|png|webp|avif|gif|bmp)$", re.I)


def _image_url(value):
    url = urljoin(BASE_URL, str(value or "").strip())
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or not IMAGE_EXTENSIONS.search(parsed.path):
        return None
    if re.search(r"/(?:website|icons?|logos?)/|(?:placeholder|no[-_]image|default[-_]image)", parsed.path, re.I):
        return None
    return url


def _image_details(soup, notice_links=None):
    """Collect URLs only. Notice images are explicitly identified as notices."""
    notice_links = _download_links(soup) if notice_links is None else notice_links
    notices = list(dict.fromkeys(url for value in notice_links.split(",") if (url := _image_url(value))))
    photos = []

    def add(value, in_gallery=False):
        url = _image_url(value)
        if not url or url in notices:
            return
        # Positive property/gallery context keeps bank logos, ads and social icons out.
        if in_gallery or re.search(r"/(?:properties|property[-_]images|property[-_]photos|auction[-_]images)/", urlparse(url).path, re.I):
            photos.append(url)

    for image in soup.select('img, source[srcset], source[data-srcset]'):
        in_gallery = bool(image.find_parent(lambda tag: tag.get('id') == 'propertyGallery' or any(
            cls in ('gallery', 'property-images', 'property-photos', 'property-gallery', 'carousel')
            for cls in tag.get('class', [])
        )))
        # Prefer the full-resolution lazy-loaded image to a small placeholder.
        src = next((image.get(key) for key in ('data-full', 'data-original', 'data-src', 'src') if _image_url(image.get(key))), None)
        if src:
            add(src, in_gallery)
        srcset = image.get('data-srcset') or image.get('srcset', '')
        if srcset:
            candidates = [part.strip().split()[0] for part in srcset.split(',') if part.strip()]
            if candidates:
                add(candidates[-1], in_gallery)
    for anchor in soup.select('a[href]'):
        add(anchor['href'], bool(anchor.has_attr('data-fancybox') or anchor.has_attr('data-lightbox') or anchor.find_parent(lambda tag: any(
            cls in ('gallery', 'property-images', 'property-photos', 'property-gallery', 'carousel')
            for cls in tag.get('class', [])
        ))))
    for element in soup.select('[style], [data-background], [data-bg]'):
        for value in re.findall(r'url\([\s\"\x27]*([^\)\"\x27]+)', element.get('style', '')):
            add(value.strip())
        add(element.get('data-background') or element.get('data-bg'))
    for meta in soup.select('meta[property="og:image"], meta[name="twitter:image"]'):
        add(meta.get('content'))
    photos = list(dict.fromkeys(photos))
    return {
        'images': ','.join(dict.fromkeys(photos + notices)),
        'propertyImageUrls': ','.join(photos),
        'noticeImageUrls': ','.join(notices),
        'imageKinds': ','.join(kind for kind, urls in (('property-photo', photos), ('sale-notice', notices)) if urls),
    }


def _extract_images(soup):
    return _image_details(soup)['images']


def _parse_detail_html(html, url, state):
    soup = BeautifulSoup(html, "html.parser")
    lines = _text_lines(soup)
    text = "\n".join(lines)

    name = ""
    heading = soup.select_one(".item-det h1, h1")
    if heading:
        name = heading.get_text(" ", strip=True)
    if not name:
        name = _regex_value(text, [r"(?:Upcoming|Auction Closed|Live|Verified)?\s*([^\n]+for sale[^\n]*)"])

    auction_id = _regex_value(text, [r"Auction\s*ID\s*:?\s*#?\s*([A-Za-z0-9-]+)"])
    if not auction_id:
        match = re.search(r"/properties/(\d+)", url)
        auction_id = match.group(1) if match else url.rstrip("/").split("/")[-1]

    category = _field_value(soup, ["Property Type", "Category"])
    if not category:
        category = _line_value(lines, ["Category", "Property Type"])
    if not category:
        category = _regex_value(text, [r"(Residential|Commercial|Industrial|Plot|Vehicle|Car|Bike|Gold)(?:\s*-\s*[A-Za-z ]+)?"])
    asset_category = _field_value(soup, ["Asset Category"]) or _line_value(lines, ["Asset Category"])

    city = _field_value(soup, ["City/Town", "City", "Location"])
    if not city:
        city = _line_value(lines, ["City/Town", "City", "Location"])
    if not city:
        city = _regex_value(text, [r"📍\s*([^\n]+)"])

    bank_name = _field_value(soup, ["Bank Name", "Bank", "Institution"])
    if not bank_name:
        bank_name = _line_value(lines, ["Bank Name", "Bank", "Institution"])
    if not bank_name:
        bank_name = _regex_value(text, [r"🏦\s*([^\n]+)"])

    address = _field_value(soup, ["Property Address", "Address", "Asset Address"])
    if not address:
        address = _line_value(lines, ["Property Address", "Address", "Asset Address"])
    description = _line_value(lines, ["Description", "Property Description", "Asset Description"]) or _block_value(soup, "Description")
    borrower_name = _field_value(soup, ["Borrower Name", "Borrower"]) or _line_value(lines, ["Borrower Name", "Borrower"])
    possession = _field_value(soup, ["Possession", "Possession Type"]) or _line_value(lines, ["Possession", "Possession Type"])
    reserve_price = _field_value(soup, ["Reserve Price"]) or _line_value(lines, ["Reserve Price"])
    emd = _field_value(soup, ["EMD", "EMD Amount"]) or _line_value(lines, ["EMD", "EMD Amount"])
    increment_bid = _field_value(soup, ["Bid Increment", "Increment Bid", "Increment Price"]) or _line_value(lines, ["Bid Increment", "Increment Bid", "Increment Price"])
    branch_name = _field_value(soup, ["Branch Name", "Branch"]) or _line_value(lines, ["Branch Name", "Branch"])
    contact_details = _field_value(soup, ["Contact Details", "Contact", "Authorised Officer"]) or _line_value(lines, ["Contact Details", "Contact", "Authorised Officer"])
    state_name = _field_value(soup, ["Province/State", "State"]) or _line_value(lines, ["Province/State", "State"])
    area_town = _field_value(soup, ["Area/Town", "Area"]) or _line_value(lines, ["Area/Town", "Area"])
    inspection_start = _field_value(soup, ["Inspection Start", "Inspection Date", "Inspection Start Date"]) or _line_value(lines, ["Inspection Start", "Inspection Date", "Inspection Start Date"])
    inspection_end = _field_value(soup, ["Inspection End", "Inspection End Date"]) or _line_value(lines, ["Inspection End", "Inspection End Date"])
    emd_deadline = _field_value(soup, ["Application Subbmision Date", "Application Submission Date", "EMD Deadline", "Tender Submission Date"]) or _line_value(lines, ["Application Subbmision Date", "Application Submission Date", "EMD Deadline", "Tender Submission Date"])
    auction_date = _field_value(soup, ["Auction Start Date", "Auction Date"]) or _line_value(lines, ["Auction Date", "Auction Start Date"])
    auction_end = _field_value(soup, ["Auction End Time", "Auction End Date"]) or _line_value(lines, ["Auction End Time", "Auction End Date"])
    auction_type = _field_value(soup, ["Auction Type", "Sale Type"]) or _line_value(lines, ["Auction Type", "Sale Type"])
    service_provider = _field_value(soup, ["Service Provider"]) or _line_value(lines, ["Service Provider"])

    if not reserve_price:
        reserve_price = _regex_value(text, [r"Reserve\s*Price\s*:?\s*₹?\s*([0-9,.\s]+(?:Cr|Lac|Lakh)?)"])
    if not emd:
        emd = _regex_value(text, [r"\bEMD(?:\s*Amount)?\s*:?\s*₹?\s*([0-9,.\s]+(?:Cr|Lac|Lakh)?)"])
    if not auction_date:
        auction_date = _regex_value(text, [r"Auction\s*date\s*:?\s*([0-9A-Za-z,\-:\s]+(?:am|pm|AM|PM)?)"])
    if not emd_deadline:
        emd_deadline = _regex_value(text, [r"EMD\s*deadline\s*:?\s*([0-9A-Za-z,\-:\s]+(?:am|pm|AM|PM)?)"])

    pdf_links = _download_links(soup) or _extract_links(soup, ["pdf", "download", "sale notice", "notice"])

    return {
        "newListingId": "",
        "schemeName": f"{name} BANK AUCTION".upper() if name else "",
        "name": name,
        "category": category,
        "state": state_name or state,
        "city": city,
        "areaTown": area_town,
        "date": auction_date,
        "reservePrice": _clean_money(reserve_price),
        "emd": _clean_money(emd),
        "incrementBid": _clean_money(increment_bid),
        "bankName": bank_name,
        "branchName": branch_name,
        "contactDetails": contact_details,
        "description": description,
        "address": address,
        "note": possession,
        "borrowerName": borrower_name,
        "publishingDate": "",
        "inspectionDate": " - ".join(part for part in (inspection_start, inspection_end) if part),
        "applicationSubmissionDate": emd_deadline,
        "auctionStartDate": auction_date,
        "auctionEndTime": auction_end,
        "auctionType": auction_type,
        "listingId": auction_id,
        **_image_details(soup, pdf_links),
        "pdfLinks": pdf_links,
        "notice": pdf_links.split(",")[0] if pdf_links else url,
        "source": "eauctionsindia",
        "url": url,
        "assetCategory": asset_category,
        "serviceProvider": service_provider,
    }


def _looks_blocked(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = " ".join(tag.get_text(" ", strip=True) for tag in soup.select("h1, h2"))
    lowered = (title + " " + headings).lower()
    return any(marker in lowered for marker in (
        "just a moment", "performing security verification", "checking your browser",
        "verify you are human", "attention required", "security verification",
    ))


class VerificationRequired(RuntimeError):
    pass


class CatalogueUnavailable(RuntimeError):
    skipped = True


class IncompleteScrapeError(RuntimeError):
    def __init__(self, message, items):
        super().__init__(message)
        self.items = items


_browser_lock = threading.Lock()


def _emit(callback, message):
    print(f"[eAuctionsIndia] {message}", flush=True)
    if callback:
        callback(f"[eAuctionsIndia] {message}")


def _read_page(page, url, callback=None, expected="listing"):
    """Use the actual browser session and wait for verification or a real page.

    Interactive verification is left to the person using the visible browser.
    """
    verification_timeout = max(1, int(os.environ.get("EAUCTIONSINDIA_VERIFICATION_TIMEOUT", "180")))
    last_error = None
    for attempt in range(3):
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=60000)
            deadline = time.monotonic() + verification_timeout
            announced = False
            while True:
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                if _looks_blocked(html):
                    if not announced:
                        _emit(callback, "Waiting for browser verification. If prompted, complete it in the open browser; scraping resumes automatically.")
                        page.bring_to_front()
                        announced = True
                    if time.monotonic() >= deadline:
                        raise VerificationRequired("Browser verification is still required. Complete it in Raahi's auction tab in your Google Chrome, then retry. Saved progress is retained.")
                    page.wait_for_timeout(1000)
                    continue
                # Initial response may be 403 before the browser completes its challenge.
                # A missing HTTP status must not bypass rendered-content checks.
                status = response.status if response and response.status is not None else 200
                if response and response.status is None:
                    heading = ' '.join(node.get_text(' ', strip=True) for node in soup.select('title, h1'))
                    if re.search(r'\b404\b.*(?:not found|page)', heading, re.I):
                        status = 404
                if expected == "detail":
                    ready = bool(re.search(r"Auction\s*ID", soup.get_text(" ", strip=True), re.I) and soup.select_one("h1, .item-det"))
                elif expected == "listing":
                    ready = bool(_extract_listing_links(soup) or re.search(r"(?:0\s+Bank Auctions|no (?:properties|auctions|results)(?: found)?)", soup.get_text(" ", strip=True), re.I))
                else:
                    ready = status < 400 or announced
                if ready:
                    return html
                if status == 404 and expected == "listing":
                    raise CatalogueUnavailable(f"eAuctionsIndia has no available catalogue at {url}.")
                if not announced and status in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Website temporarily returned HTTP {status}")
                if not announced and status >= 400:
                    raise RuntimeError(f"Website returned HTTP {status} for {url}")
                # Avoid parsing a half-rendered page as a valid empty response.
                if time.monotonic() >= deadline:
                    raise RuntimeError("The website loaded without the expected auction content; it may have changed or redirected. Saved progress is retained.")
                page.wait_for_timeout(500)
        except (VerificationRequired, CatalogueUnavailable):
            raise
        except Exception as exc:
            last_error = exc
            if page.is_closed():
                raise RuntimeError("The auction tab or Chrome connection was closed. Reconnect to your Chrome and re-run scraping to resume saved progress.") from exc
            if attempt < 2:
                _emit(callback, f"Page request failed; retrying ({attempt + 1}/2).")
                page.wait_for_timeout((attempt + 1) * 2000)
    raise RuntimeError(f"Could not load {url}: {last_error}") from last_error


def _next_listing_url(soup, current_url):
    current = urlparse(current_url)
    page_match = re.search(r"/(\d+)/?$", current.path)
    number = int(page_match.group(1)) if page_match else 1
    candidates = soup.select('a[rel="next"], .pagination a[href]')
    for anchor in candidates:
        candidate = urljoin(current_url, anchor.get("href", ""))
        parsed = urlparse(candidate)
        if parsed.hostname != current.hostname:
            continue
        match = re.search(r"/(\d+)/?$", parsed.path)
        if match and int(match.group(1)) == number + 1:
            return candidate
    return None


def _validate_item(item, state):
    if not item.get("name") or not item.get("date") or not item.get("listingId"):
        raise RuntimeError("Auction detail is missing its title, ID or auction date; refusing to export an incomplete row.")
    # Never label an unfiltered search result as the requested state.
    actual = _normalize_label(item.get("state", ""))
    requested = _normalize_label(state)
    aliases = {
        "orissa": "odisha", "pondicherry": "puducherry",
        "newdelhi": "delhi", "jammukashmir": "jammuandkashmir",
        "dadraandnagarhaveli": "dadraandnagarhavelianddamananddiu",
        "damananddiu": "dadraandnagarhavelianddamananddiu",
    }
    if aliases.get(actual, actual) != aliases.get(requested, requested):
        raise RuntimeError(f"The website returned a property in {item.get('state')} while scraping {state}.")


def _scrape_with_playwright(state, progress_callback=None):
    if sync_playwright is None:
        raise RuntimeError("Install project requirements; Playwright is required for eAuctionsIndia browser access.")
    first_urls = _listing_urls(state, 1)
    first_url = first_urls[0]
    profile = browser_profile()
    checkpoint = profile.parent / (profile.name + "-progress") / f"{_slug(state)}.sqlite3"
    progress = None
    try:
        with sync_playwright() as playwright:
            _emit(progress_callback, "Connecting to your existing Google Chrome. Approve the connection prompt in Chrome if it appears.")
            with desktop_browser(playwright, first_url) as page:
                progress = ScrapeProgress(checkpoint, state, first_url)
                if not progress.resumed:
                    progress.set_roots(first_urls[1:])
                else:
                    _emit(progress_callback, f"Resuming {state}: {len(progress.items())} properties already saved locally.")
                visited_pages = set()
                pages_this_run = 0
                while progress.get("page_url"):
                    page_url = progress.get("page_url")
                    if page_url in visited_pages:
                        raise RuntimeError("The website repeated a pagination URL; stopping to avoid a loop.")
                    visited_pages.add(page_url)
                    _emit(progress_callback, f"Fetching {state} listing page {progress.get('pages_done', 0) + 1}.")
                    html = _read_page(page, page_url, progress_callback)
                    soup = BeautifulSoup(html, "html.parser")
                    links = _extract_listing_links(soup)
                    next_url = _next_listing_url(soup, page_url)
                    progress.set_page(page_url, links, next_url)
                    new_links = [url for url in links if not progress.contains(url)]
                    if links and not new_links and not progress.resumed:
                        raise RuntimeError("The website repeated the previous page's auctions; saved progress is retained.")
                    failures = []
                    for detail_url in new_links:
                        try:
                            html = _read_page(page, detail_url, progress_callback, expected="detail")
                            item = _parse_detail_html(html, detail_url, state)
                            _validate_item(item, state)
                            progress.add(detail_url, item)
                            _emit(progress_callback, f"Saved auction {item['listingId']}: {item['name']}")
                            page.wait_for_timeout(int(REQUEST_DELAY * 1000))
                        except VerificationRequired:
                            raise
                        except Exception as exc:
                            failures.append(f"{detail_url}: {exc}")
                            _emit(progress_callback, f"Detail failed: {detail_url}. It will be retried on the next run.")
                    if failures:
                        raise RuntimeError(f"{len(failures)} auction details failed. " + "; ".join(failures[:3]))
                    progress.advance(next_url)
                    pages_this_run += 1
                    if next_url and pages_this_run >= MAX_PAGES:
                        raise RuntimeError(f"Reached the configured {MAX_PAGES}-page limit. Run again to resume the remaining pages.")
        items = progress.items()
        _emit(progress_callback, f"Finished {state}: {len(items)} properties, {progress.get('pages_done')} listing pages.")
        return items
    except CatalogueUnavailable as exc:
        if progress is not None and not progress.items() and progress.get('pages_done', 0) == 0:
            _emit(progress_callback, f"{state} is unavailable on eAuctionsIndia; this selection is skipped.")
            raise
        raise IncompleteScrapeError(str(exc), progress.items() if progress is not None else []) from exc
    except Exception as exc:
        raise IncompleteScrapeError(str(exc), progress.items() if progress is not None else []) from exc
    finally:
        if progress is not None:
            progress.close()


def check_access(progress_callback=None):
    """Verify browser access without changing scrape progress or the seen database."""
    if sync_playwright is None:
        raise RuntimeError("Install requirements before checking eAuctionsIndia access.")
    with _browser_lock, sync_playwright() as playwright:
        url = _listing_urls("Delhi", 1)[0]
        _emit(progress_callback, "Connecting to your existing Google Chrome. Approve the connection prompt in Chrome if it appears.")
        with desktop_browser(playwright, url) as page:
            html = _read_page(page, url, progress_callback)
            count = len(_extract_listing_links(BeautifulSoup(html, "html.parser")))
            _emit(progress_callback, f"Browser access verified: {count} listing links found.")
            return count


def scrape(state, progress_callback=None):
    if state not in STATES:
        raise ValueError(f"Unsupported eAuctionsIndia state: {state}")
    _emit(progress_callback, f"Starting local browser scrape for {state}.")
    if _browser_lock.locked():
        _emit(progress_callback, "Waiting for the current eAuctionsIndia state to finish; browser access is processed one state at a time.")
    with _browser_lock:
        return _scrape_with_playwright(state, progress_callback)
