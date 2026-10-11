"""Offline checks of the distributed executable; no browser or live scrape."""
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
import traceback


def run_packaging_check(report_path):
    report = {
        'passed': False,
        'platform': sys.platform,
        'architecture': platform.machine(),
        'python': platform.python_version(),
        'frozen': bool(getattr(sys, 'frozen', False)),
        'tested_at_utc': datetime.now(timezone.utc).isoformat(),
        'checks': {},
        'live_cloudflare_tested': False,
    }
    app = None
    try:
        from app_paths import application_data_dir, default_output_folder
        from gui import ScraperGUI
        from openpyxl import load_workbook
        from playwright.sync_api import sync_playwright
        from scraper_runner import save_items_to_excel
        from scrapers.local_browser import _profile_lock
        report['checks']['per_user_paths'] = {
            'app_data': application_data_dir(), 'exports': default_output_folder(),
        }
        with sync_playwright() as driver:
            assert driver.chromium.name == 'chromium'
            report['checks']['bundled_playwright_driver'] = True
        app = ScraperGUI()
        app.root.withdraw()
        app.root.update_idletasks()
        assert len(app.site_vars) == 7 and len(app.state_vars) == 36
        assert app.output_folder == default_output_folder()
        assert app.eauctions_access_btn.winfo_exists()
        report['checks']['gui_initialized'] = True
        with TemporaryDirectory() as folder:
            with _profile_lock(Path(folder)/'test-profile'):
                report['checks']['platform_file_lock'] = True
            file = save_items_to_excel([
                {'listingId': 'build-check', 'name': 'Build validation',
                 'images': 'https://www.eauctionsindia.com/storage/images/example.webp'}
            ], output_folder=folder)
            workbook = load_workbook(file)
            assert workbook.active.max_row == 2
            assert 'listingId' in [cell.value for cell in workbook.active[1]]
            workbook.close()
            report['checks']['excel_roundtrip'] = True
        report['passed'] = True
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if app is not None:
            app.root.destroy()
        file = Path(report_path)
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report['passed']
