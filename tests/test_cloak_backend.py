import os
import sys
import unittest
from unittest.mock import patch

from scrapers import local_browser


class CloakBackendTests(unittest.TestCase):
    def test_frozen_app_defaults_to_cloak_without_preinstalled_binary(self):
        env = dict(os.environ)
        env.pop('EAUCTIONSINDIA_BROWSER_BACKEND', None)
        with patch.dict(os.environ, env, clear=True), patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(local_browser.browser_backend(), 'cloak')
            with patch.object(local_browser, 'find_spec', return_value=object()):
                self.assertTrue(local_browser.browser_ready())

    def test_legacy_chrome_remains_explicit_fallback(self):
        with patch.dict(os.environ, {'EAUCTIONSINDIA_BROWSER_BACKEND': 'chrome'}), patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(local_browser.browser_backend(), 'chrome')


if __name__ == '__main__':
    unittest.main()
