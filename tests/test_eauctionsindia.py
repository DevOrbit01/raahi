import contextlib
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from scrapers import eauctionsindia as e
from scrapers.scrape_progress import ScrapeProgress
from scrapers.local_browser import _profile_lock
from seen_db import SeenDatabase
import scraper_runner


DETAIL_URL = e.BASE_URL + "/properties/891314"
DETAIL_HTML = (Path(__file__).parent / "fixtures/eauctionsindia_detail.html").read_text(encoding='utf-8')


class BrowserPage:
    def __init__(self, documents, status=200):
        self.documents = iter(documents)
        self.last = ""
        self.status = status
        self.waits = []

    def goto(self, *args, **kwargs):
        return SimpleNamespace(status=self.status)

    def content(self):
        self.last = next(self.documents, self.last)
        return self.last

    def wait_for_timeout(self, delay):
        self.waits.append(delay)

    def bring_to_front(self):
        pass

    def is_closed(self):
        return False


class EAuctionsTests(unittest.TestCase):
    def test_current_live_html_fields_and_notice(self):
        item = e._parse_detail_html(DETAIL_HTML, DETAIL_URL, "Delhi")
        e._validate_item(item, "Delhi")
        self.assertEqual(item["listingId"], "891314")
        self.assertEqual(item["category"], "Flat")
        self.assertEqual(item["city"], "New Delhi")
        self.assertEqual(item["reservePrice"], 22200000)
        self.assertEqual(item["emd"], 2220000)
        self.assertEqual(item["date"], "20-11-2026 12:00 PM")
        self.assertEqual(item["applicationSubmissionDate"], "18-11-2026 05:00 PM")
        self.assertIn("eauctionsindia.org/storage/properties/", item["pdfLinks"])
        self.assertEqual(item["images"], item['noticeImageUrls'])
        self.assertEqual(item["propertyImageUrls"], "")
        self.assertEqual(item["imageKinds"], "sale-notice")

    def test_gallery_images_and_notice_urls_without_downloading(self):
        html = '''<img src="/storage/website/logo.jpg">
        <img src="/storage/icons/whatsapp.png">
        <div class="property-gallery"><img src="/placeholder.png" data-src="https://cdn.example.com/house.jpg">
        <a data-fancybox="property" href="https://cdn.example.com/full-house.jpg">Photo</a></div>
        <div style="background-image: url('/storage/properties/plot.webp')"></div>
        <meta property="og:image" content="/storage/properties/plot.webp">
        <div class="card"><h5>Downloads</h5>
        <a href="https://www.eauctionsindia.org/storage/properties/notice.jpg?download=1">Sale Notice</a>
        <a href="/storage/properties/document.pdf">Terms</a></div>'''
        with patch('requests.get', side_effect=AssertionError('Scraping must not download images')):
            info = e._image_details(BeautifulSoup(html, 'html.parser'))
        self.assertEqual(info['propertyImageUrls'].split(','), [
            'https://cdn.example.com/house.jpg', 'https://cdn.example.com/full-house.jpg',
            e.BASE_URL+'/storage/properties/plot.webp',
        ])
        self.assertIn('notice.jpg?download=1', info['noticeImageUrls'])
        self.assertEqual(info['imageKinds'], 'property-photo,sale-notice')
        self.assertNotIn('logo', info['images'])
        self.assertNotIn('whatsapp', info['images'])
        self.assertNotIn('.pdf', info['images'])

    def test_pagination_ignores_other_hosts(self):
        soup = BeautifulSoup('<ul class="pagination"><a href="https://evil.example/properties-in-delhi/2">2</a><a href="/properties-in-delhi/2">2</a></ul>', "html.parser")
        self.assertEqual(e._next_listing_url(soup, e._listing_urls("Delhi", 1)[0]), e._listing_urls("Delhi", 2)[0])
        self.assertEqual(len(e._listing_urls("Dadra and Nagar Haveli and Daman and Diu", 1)), 2)

    def test_browser_challenge_waits_for_real_content(self):
        page = BrowserPage(["<title>Just a moment...</title>", DETAIL_HTML], status=403)
        messages = []
        self.assertEqual(e._read_page(page, DETAIL_URL, messages.append, "detail"), DETAIL_HTML)
        self.assertIn(1000, page.waits)
        self.assertTrue(any("verification" in message for message in messages))

    def test_extension_unknown_http_status_waits_for_dom_and_detects_404(self):
        page = BrowserPage(['<h1>Loading</h1>', DETAIL_HTML], status=None)
        self.assertEqual(e._read_page(page, DETAIL_URL, expected='detail'), DETAIL_HTML)
        self.assertIn(500, page.waits)
        page = BrowserPage(['<title>404 | Not Found</title>'], status=None)
        with self.assertRaises(e.CatalogueUnavailable):
            e._read_page(page, e.BASE_URL + '/properties-in-ladakh')

    def test_normal_page_with_cloudflare_scripts_is_not_a_challenge(self):
        self.assertFalse(e._looks_blocked(DETAIL_HTML + '<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script>'))

    def test_unavailable_catalogue_is_reported_as_skipped(self):
        page = BrowserPage(['<h1>404</h1>'], status=404)
        with self.assertRaises(e.CatalogueUnavailable):
            e._read_page(page, e.BASE_URL + '/properties-in-ladakh')
        with patch.object(e, "scrape", side_effect=e.CatalogueUnavailable("No catalogue for Ladakh")):
            details = {}
            items = scraper_runner.collect_new_items(["Ladakh"], ["eauctionsindia"], run_details=details)
            self.assertEqual(items, [])
            self.assertEqual(details['skipped_tasks'], 1)
            self.assertEqual(details['failed_tasks'], 0)

    def test_unresolved_verification_is_not_empty_success(self):
        page = BrowserPage(["<title>Just a moment...</title>"])
        with patch.dict("os.environ", {"EAUCTIONSINDIA_VERIFICATION_TIMEOUT": "1"}), patch.object(e.time, "monotonic", side_effect=[0, 2]):
            with self.assertRaises(e.VerificationRequired):
                e._read_page(page, DETAIL_URL, expected="detail")

    def test_wrong_state_rejected_and_merged_union_accepted(self):
        item = e._parse_detail_html(DETAIL_HTML, DETAIL_URL, "Delhi")
        with self.assertRaises(RuntimeError):
            e._validate_item(item, "Gujarat")
        for state in ("Daman and Diu", "Dadra and Nagar Haveli"):
            item["state"] = state
            e._validate_item(item, "Dadra and Nagar Haveli and Daman and Diu")

    def test_profile_lock_rejects_second_app(self):
        with TemporaryDirectory() as folder:
            profile = Path(folder) / "profile"
            with _profile_lock(profile):
                with self.assertRaises(RuntimeError):
                    with _profile_lock(profile):
                        pass

    def test_checkpoint_survives_failure_and_resumes_only_missing_details(self):
        second_url = e.BASE_URL + "/properties/891315"
        listing_url = e._listing_urls("Delhi", 1)[0]
        listing = f'<a href="{DETAIL_URL}">One</a><a href="{second_url}">Two</a>'
        failed_once = [True]
        detail_calls = []

        def read(page, url, callback=None, expected="listing"):
            if url == listing_url:
                return listing
            detail_calls.append(url)
            if url == second_url and failed_once[0]:
                raise RuntimeError("temporary network failure")
            return DETAIL_HTML if url == DETAIL_URL else DETAIL_HTML.replace("891314", "891315")

        @contextlib.contextmanager
        def browser(*args):
            yield BrowserPage([])

        with TemporaryDirectory() as folder, patch.dict("os.environ", {"EAUCTIONSINDIA_BROWSER_PROFILE": folder + "/browser"}), patch.object(e, "sync_playwright", return_value=contextlib.nullcontext(None)), patch.object(e, "desktop_browser", browser), patch.object(e, "_read_page", read):
            with self.assertRaises(e.IncompleteScrapeError) as failed:
                e.scrape("Delhi")
            self.assertEqual(len(failed.exception.items), 1)
            failed_once[0] = False
            items = e.scrape("Delhi")
            self.assertEqual(len(items), 2)
            self.assertEqual(detail_calls.count(DETAIL_URL), 1)
            self.assertEqual(detail_calls.count(second_url), 2)

    def test_completed_checkpoint_starts_a_fresh_run(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "progress.sqlite3"
            progress = ScrapeProgress(path, "Delhi", "first")
            progress.add("detail", {"listingId": "1"})
            progress.advance(None)
            progress.close()
            progress = ScrapeProgress(path, "Delhi", "first")
            self.assertFalse(progress.resumed)
            self.assertEqual(progress.items(), [])
            progress.close()

    def test_partial_rows_reach_runner_with_failure_details(self):
        item = e._parse_detail_html(DETAIL_HTML, DETAIL_URL, "Delhi")
        with TemporaryDirectory() as folder, patch.object(scraper_runner, "seen_db", SeenDatabase(str(Path(folder) / "seen.json"))), patch.object(e, "scrape", side_effect=e.IncompleteScrapeError("one detail failed", [item])):
            details = {}
            items = scraper_runner.collect_new_items(["Delhi"], ["eauctionsindia"], run_details=details)
            self.assertEqual(len(items), 1)
            self.assertEqual(details["failed_tasks"], 1)
            self.assertIn("one detail failed", details["errors"][0])


if __name__ == "__main__":
    unittest.main()
