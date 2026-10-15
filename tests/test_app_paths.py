import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import app_paths
import scraper_runner


class AppPathTests(unittest.TestCase):
    def test_windows_export_defaults_to_user_appdata(self):
        with TemporaryDirectory() as folder, patch.dict(os.environ, {'LOCALAPPDATA': folder}), patch.object(app_paths.os, 'name', 'nt'):
            self.assertEqual(app_paths.default_output_folder(), os.path.join(folder, 'RaahiScraper', 'Exports'))

    def test_excel_without_explicit_folder_uses_writable_default(self):
        with TemporaryDirectory() as folder, patch.object(scraper_runner, 'default_output_folder', return_value=folder):
            file = scraper_runner.save_items_to_excel([{'listingId': 'test'}])
            self.assertEqual(os.path.dirname(file), folder)
            self.assertTrue(os.path.isfile(file))
