from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scrapers import local_browser as browser


class ExistingChromeTests(unittest.TestCase):
    def test_attachment_access_is_scoped_and_preserves_binary_data(self):
        session = Mock()
        session.invoke.side_effect = [None, {'status': 200, 'type': 'image/webp', 'data': 'AP9iaW5hcnk='}]
        with patch.object(browser, '_session', session):
            for url in ['https://example.com/storage/a.jpg', 'https://www.eauctionsindia.com/account', 'http://www.eauctionsindia.com/storage/a.jpg']:
                with self.assertRaises(ValueError):
                    browser.fetch_chrome_attachment(url)
            session.invoke.assert_not_called()
            url = 'https://www.eauctionsindia.com/storage/images/a.webp'
            response = browser.fetch_chrome_attachment(url)
            self.assertEqual(response.content, b'\x00\xffbinary')
            self.assertEqual(response.headers['Content-Type'], 'image/webp')
            session.invoke.assert_any_call('fetch_asset', url)

    def test_opt_in_endpoint_is_loopback_and_validated(self):
        with TemporaryDirectory() as folder, patch.dict('os.environ', {'EAUCTIONSINDIA_CHROME_DATA_DIR': folder}):
            file = Path(folder)/'DevToolsActivePort'
            file.write_text('61545\n/devtools/browser/abcd-1234\n')
            self.assertEqual(browser.chrome_endpoint(), 'ws://127.0.0.1:61545/devtools/browser/abcd-1234')
            for invalid in ['0\n/devtools/browser/a', '9222\nhttps://example.com', '65536\n/devtools/browser/a']:
                file.write_text(invalid)
                with self.assertRaises(RuntimeError):
                    browser.chrome_endpoint()

    def test_missing_permission_never_launches_another_browser(self):
        with TemporaryDirectory() as folder, patch.dict('os.environ', {'EAUCTIONSINDIA_CHROME_DATA_DIR': folder}), patch.object(browser.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(RuntimeError, 'Browser Connector Setup'):
                with browser.desktop_browser(None, 'https://www.eauctionsindia.com'):
                    pass
            launch.assert_not_called()

    def test_session_reuses_connection_and_disconnect_preserves_chrome(self):
        page = Mock()
        page.is_closed.return_value = False
        page.goto.return_value = SimpleNamespace(status=200)
        chrome = Mock()
        chrome.version = '154.0.0.0'
        chrome.is_connected.return_value = True
        context = Mock()
        context.pages = []
        context.new_page.return_value = page
        chrome.contexts = [context]
        driver = Mock()
        driver.chromium.connect_over_cdp.return_value = chrome
        with patch('playwright.sync_api.sync_playwright', return_value=SimpleNamespace(start=lambda: driver)), patch.object(browser, 'chrome_endpoint', return_value='ws://127.0.0.1:61545/devtools/browser/abcd'):
            session = browser._ChromeSession()
            try:
                session.invoke('ensure')
                session.invoke('ensure')
                self.assertEqual(session.invoke('goto', 'https://www.eauctionsindia.com').status, 200)
                driver.chromium.connect_over_cdp.assert_called_once()
                driver.chromium.launch.assert_not_called()
                context.new_page.assert_called_once()
                session.disconnect()
                driver.stop.assert_called_once()
                chrome.close.assert_not_called()
                context.close.assert_not_called()
                page.close.assert_not_called()
            finally:
                session.stop()

    def test_reconnect_reuses_only_raahi_tab_in_same_chrome_profile(self):
        page = Mock()
        page.url = 'https://www.eauctionsindia.com/properties/703774'
        page.is_closed.return_value = False
        page.goto.return_value = SimpleNamespace(status=200)
        marker = [False]
        def evaluate(script, key):
            self.assertEqual(key, browser.MANAGED_TAB_KEY)
            if 'setItem' in script:
                marker[0] = True
            return marker[0]
        page.evaluate.side_effect = evaluate
        personal = Mock(url='https://mail.example.com')
        personal.is_closed.return_value = False
        unmarked_auction = Mock(url='https://www.eauctionsindia.com/properties/123')
        unmarked_auction.is_closed.return_value = False
        unmarked_auction.evaluate.return_value = False
        context = Mock()
        context.pages = [personal, unmarked_auction, page]
        context.new_page.return_value = page
        chrome = Mock(version='154.0.0.0', contexts=[context])
        chrome.is_connected.return_value = True
        driver = Mock()
        driver.chromium.connect_over_cdp.return_value = chrome
        with patch('playwright.sync_api.sync_playwright', return_value=SimpleNamespace(start=lambda: driver)), patch.object(browser, 'chrome_endpoint', return_value='ws://127.0.0.1:61545/devtools/browser/abcd'):
            for run in range(2):
                session = browser._ChromeSession()
                try:
                    session.invoke('ensure')
                    self.assertIs(session.page, page)
                    session.invoke('goto', page.url)
                    session.disconnect()
                finally:
                    session.stop()
            context.new_page.assert_called_once()
            personal.evaluate.assert_not_called()
            personal.goto.assert_not_called()
            unmarked_auction.goto.assert_not_called()
            chrome.close.assert_not_called()

    def test_navigation_is_limited_to_auction_site(self):
        session = Mock()
        page = browser.ChromePage(session)
        for url in ['https://example.com', 'https://eauctionsindia.com.evil.example', 'file:///tmp/private', 'http://www.eauctionsindia.com']:
            with self.assertRaises(ValueError):
                page.goto(url)
        session.invoke.assert_not_called()


if __name__ == '__main__':
    unittest.main()
