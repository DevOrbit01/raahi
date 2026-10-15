"""Experimental local CloakBrowser backend for eAuctionsIndia.

The browser binary is obtained from CloakHQ by the local user. Raahi stores a
dedicated persistent profile under its per-user application data directory.
No Chrome extension, Chrome debugging permission, or cookie export is needed.
"""
from contextlib import contextmanager
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

from app_paths import application_data_dir


AUCTION_HOSTS = {'eauctionsindia.com', 'www.eauctionsindia.com'}
ASSET_HOSTS = AUCTION_HOSTS | {'eauctionsindia.org', 'www.eauctionsindia.org'}


def cloak_profile_dir():
    override = os.environ.get('EAUCTIONSINDIA_CLOAK_PROFILE')
    return Path(override).expanduser().resolve() if override else Path(application_data_dir()) / 'eauctions-cloak-profile'


def cloak_headless():
    return os.environ.get('EAUCTIONSINDIA_CLOAK_HEADLESS', '1').lower() not in ('0', 'false', 'no')


class CloakPage:
    def __init__(self, profile, headless):
        self.profile = str(profile)
        self.headless = headless
        self.context = self.page = None
        self._open()

    def _open(self):
        try:
            from cloakbrowser import launch_persistent_context
        except ImportError as exc:
            raise RuntimeError('CloakBrowser is not installed. Install the Raahi project requirements first.') from exc
        self.context = launch_persistent_context(self.profile, headless=self.headless)
        self.page = self.context.new_page()
        self.page.set_default_timeout(60000)

    def goto(self, url, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in AUCTION_HOSTS:
            raise ValueError('Raahi only navigates to eAuctionsIndia HTTPS auction pages.')
        return self.page.goto(url, **kwargs)

    def content(self):
        return self.page.content()

    def wait_for_timeout(self, milliseconds):
        return self.page.wait_for_timeout(milliseconds)

    def bring_to_front(self):
        if not self.headless:
            self.page.bring_to_front()

    def is_closed(self):
        return self.page is None or self.page.is_closed()

    def show_for_verification(self, url):
        """Switch to a visible browser only when a challenge needs a person."""
        if not self.headless:
            return False
        self.close()
        self.headless = False
        self._open()
        self.goto(url, wait_until='domcontentloaded', timeout=60000)
        self.bring_to_front()
        return True

    def close(self):
        if self.context is not None:
            try:
                self.context.close()
            finally:
                self.context = self.page = None


@contextmanager
def cloak_desktop_browser(_playwright, _start_url):
    page = CloakPage(cloak_profile_dir(), cloak_headless())
    try:
        yield page
    finally:
        page.close()


def fetch_cloak_attachment(url):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ASSET_HOSTS or not parsed.path.startswith('/storage/'):
        raise ValueError('Browser attachment access is limited to eAuctionsIndia storage URLs.')
    from cloakbrowser import launch_persistent_context
    context = launch_persistent_context(str(cloak_profile_dir()), headless=True)
    try:
        response = context.request.get(url, timeout=30000)
        return SimpleNamespace(
            status_code=response.status,
            headers=dict(response.headers),
            content=response.body(),
        )
    finally:
        context.close()
