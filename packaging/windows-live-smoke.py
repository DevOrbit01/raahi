"""Windows runner: launch official Cloak binary and probe packaged eAuctions access."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import traceback

from cloakbrowser import binary_info, launch_persistent_context


release = Path('release')
release.mkdir(exist_ok=True)
report_path = release / 'windows-live-smoke.json'
result = {'platform': sys.platform, 'browser_launch_passed': False,
          'packaged_site_check_passed': False, 'site_check_is_client_acceptance': False}

try:
    with TemporaryDirectory() as folder:
        context = launch_persistent_context(str(Path(folder) / 'profile'), headless=True)
        try:
            page = context.new_page()
            page.goto('data:text/html,<title>Raahi Windows browser smoke</title>')
            assert page.title() == 'Raahi Windows browser smoke'
            result['browser_launch_passed'] = True
            result['browser_version'] = binary_info()['version']
        finally:
            context.close()

        env = os.environ.copy()
        env.update({
            'EAUCTIONSINDIA_BROWSER_BACKEND': 'cloak',
            'EAUCTIONSINDIA_CLOAK_PROFILE': str(Path(folder) / 'auction-profile'),
            'EAUCTIONSINDIA_BROWSER_PROFILE': str(Path(folder) / 'progress'),
            'EAUCTIONSINDIA_VERIFICATION_TIMEOUT': '30',
            'EAUCTIONSINDIA_HEADLESS_CHALLENGE_GRACE': '60',
        })
        packaged_report = Path(folder) / 'packaged-site-check.json'
        completed = subprocess.run(
            [str(release / 'RaahiScraper.exe'), '--check-eauctionsindia', '--report', str(packaged_report)],
            env=env, timeout=90, check=False,
        )
        result['packaged_site_check_exit_code'] = completed.returncode
        if packaged_report.exists():
            site = json.loads(packaged_report.read_text(encoding='utf-8'))
            result['packaged_site_check_passed'] = bool(site.get('passed'))
            result['listing_links'] = site.get('listing_links')
            result['site_error'] = site.get('error')
        elif completed.returncode:
            result['site_error'] = 'Packaged app exited without a site report.'
except Exception:
    result['error'] = traceback.format_exc()
finally:
    report_path.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)

raise SystemExit(0 if result['browser_launch_passed'] else 1)
