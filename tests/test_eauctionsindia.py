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

    def test_cloak_challenge_opens_visible_browser_once(self):
        class ChallengePage(BrowserPage):
            def __init__(self):
                super().__init__(["<title>Just a moment...</title>", DETAIL_HTML], status=403)
                self.verification_urls = []

            def show_for_verification(self, url):
                self.verification_urls.append(url)
                return True

        page = ChallengePage()
        with patch.dict('os.environ', {'EAUCTIONSINDIA_BROWSER_BACKEND': 'cloak', 'EAUCTIONSINDIA_HEADLESS_CHALLENGE_GRACE': '0'}):
            self.assertEqual(e._read_page(page, DETAIL_URL, expected='detail'), DETAIL_HTML)
        self.assertEqual(page.verification_urls, [DETAIL_URL])

    def test_unknown_http_status_waits_for_dom_and_detects_404(self):
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

    def test_missing_date_skips_listing_continues_pagination_and_rechecks_next_run(self):
        missing_url = e.BASE_URL + '/properties/896731'
        second_detail = e.BASE_URL + '/properties/891315'
        first_page = e._listing_urls('Delhi', 1)[0]
        second_page = e._listing_urls('Delhi', 2)[0]
        listing = (f'<a href="{DETAIL_URL}">One</a><a href="{missing_url}">Missing date</a>'
                   f'<ul class="pagination"><a rel="next" href="{second_page}">Next</a></ul>')
        missing_html = '<h1>Car Auction</h1><p>Auction ID: 896731</p>'
        corrected = [False]
        calls = []

        def read(page, url, callback=None, expected='listing'):
            calls.append(url)
            if url == first_page:
                return listing
            if url == second_page:
                return f'<a href="{second_detail}">Two</a>'
            if url == missing_url and not corrected[0]:
                return missing_html
            return DETAIL_HTML.replace('891314', url.rsplit('/', 1)[-1])

        @contextlib.contextmanager
        def browser(*args):
            yield BrowserPage([])

        with TemporaryDirectory() as folder, patch.dict('os.environ', {
            'EAUCTIONSINDIA_BROWSER_PROFILE': folder + '/browser',
            'EAUCTIONSINDIA_BROWSER_BACKEND': 'cloak',
        }), patch.object(e, 'desktop_browser', browser), patch.object(e, '_read_page', read), \
                patch.object(scraper_runner, 'seen_db', SeenDatabase(str(Path(folder) / 'seen.json'))):
            details = {}
            items = scraper_runner.collect_new_items(['Delhi'], ['eauctionsindia'], run_details=details)
            self.assertEqual({item['listingId'] for item in items}, {'891314', '891315'})
            self.assertIn(second_page, calls)
            self.assertEqual(details['failed_tasks'], 0)
            self.assertEqual(details['skipped_properties'], 1)
            self.assertEqual(len(details['warnings']), 1)
            self.assertIn(missing_url, details['warnings'][0])
            self.assertIn('missing auction date', details['warnings'][0])
            self.assertFalse((Path(folder) / 'seen.json').exists())
            corrected[0] = True
            items = e.scrape('Delhi')
            self.assertEqual({item['listingId'] for item in items}, {'891314', '891315', '896731'})
            self.assertEqual(items.warnings, [])
            self.assertEqual(calls.count(missing_url), 2)

    def test_skipped_listing_warning_survives_later_page_failure_and_resume(self):
        missing_url = e.BASE_URL + '/properties/896731'
        second_detail = e.BASE_URL + '/properties/891315'
        first_page = e._listing_urls('Delhi', 1)[0]
        second_page = e._listing_urls('Delhi', 2)[0]
        calls = []
        fail_second_page = [True]

        def read(page, url, callback=None, expected='listing'):
            calls.append(url)
            if url == first_page:
                return (f'<a href="{missing_url}">Missing date</a><a href="{DETAIL_URL}">One</a>'
                        f'<ul class="pagination"><a rel="next" href="{second_page}">Next</a></ul>')
            if url == second_page:
                if fail_second_page[0]:
                    raise RuntimeError('temporary network failure')
                return f'<a href="{second_detail}">Two</a>'
            if url == missing_url:
                return '<h1>Car Auction</h1><p>Auction ID: 896731</p>'
            return DETAIL_HTML.replace('891314', url.rsplit('/', 1)[-1])

        @contextlib.contextmanager
        def browser(*args):
            yield BrowserPage([])

        with TemporaryDirectory() as folder, patch.dict('os.environ', {
            'EAUCTIONSINDIA_BROWSER_PROFILE': folder + '/browser',
            'EAUCTIONSINDIA_BROWSER_BACKEND': 'cloak',
        }), patch.object(e, 'desktop_browser', browser), patch.object(e, '_read_page', read):
            with self.assertRaises(e.IncompleteScrapeError) as failed:
                e.scrape('Delhi')
            self.assertEqual(len(failed.exception.items), 1)
            self.assertEqual(len(failed.exception.warnings), 1)
            fail_second_page[0] = False
            items = e.scrape('Delhi')
            self.assertEqual({item['listingId'] for item in items}, {'891314', '891315'})
            self.assertEqual(len(items.warnings), 1)
            self.assertEqual(calls.count(missing_url), 1)
            self.assertEqual(calls.count(DETAIL_URL), 1)

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
