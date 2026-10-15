"""Attach to the user's running Chrome after Chrome's own permission prompt.

Raahi accepts any Chrome version exposing a compatible, approved CDP endpoint.
The normal-profile opt-in interface is available in Chrome 144+. Raahi never
launches a second browser, exports cookies, or closes
Chrome. Browser operations run on one thread so approval/session can be reused
across states and GUI workers.
"""
import atexit
import base64
from concurrent.futures import Future
from contextlib import contextmanager
from importlib.util import find_spec
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
from types import SimpleNamespace
from urllib.parse import urlparse
from app_paths import application_data_dir


AUCTION_HOSTS = ('eauctionsindia.com', 'www.eauctionsindia.com')
MANAGED_TAB_KEY = 'raahi.eauctionsindia.managed-tab.v1'


def browser_backend():
    # Packaged client builds use CloakBrowser; source runs retain the legacy
    # Chrome mode unless explicitly switched while developing or testing.
    default = 'cloak' if getattr(sys, 'frozen', False) else 'chrome'
    value = os.environ.get('EAUCTIONSINDIA_BROWSER_BACKEND', default).lower()
    return 'cloak' if value in ('cloak', 'cloakbrowser') else 'chrome'


def _is_auction_page(page):
    parsed = urlparse(page.url)
    return parsed.scheme == 'https' and parsed.hostname in AUCTION_HOSTS


def _existing_auction_tab(context):
    """Reuse only a tab previously marked by Raahi; leave other tabs alone."""
    for page in context.pages:
        try:
            if not page.is_closed() and _is_auction_page(page) and page.evaluate(
                '(key) => sessionStorage.getItem(key) === "1"', MANAGED_TAB_KEY
            ):
                return page
        except Exception:
            # A loading/closed tab cannot be reused safely.
            continue
    return None


def app_data_dir():
    return Path(application_data_dir())


def browser_profile():
    # This directory contains public scrape progress/locks, not browser cookies.
    override = os.environ.get("EAUCTIONSINDIA_BROWSER_PROFILE")
    return Path(override).expanduser().resolve() if override else app_data_dir() / "eauctions-browser"


def chrome_data_dir():
    override = os.environ.get("EAUCTIONSINDIA_CHROME_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Google" / "Chrome" / "User Data"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "google-chrome"


SETUP_MESSAGE = (
    "Chrome has not enabled a browser connection for Raahi. Open Chrome Connection Settings, "
    "enable Allow remote debugging if the option is available, then click Check eAuctionsIndia "
    "Browser Access and approve Chrome's prompt. Keep Chrome open under the same Windows account. "
    "If Chrome has no remote-debugging permission option, update Chrome: that normal-profile "
    "connection feature was added in Chrome 144. Raahi does not reject browsers by version number."
)


def chrome_endpoint():
    try:
        lines = (chrome_data_dir() / "DevToolsActivePort").read_text().strip().splitlines()
        if len(lines) != 2 or not lines[0].isdigit():
            raise ValueError("invalid endpoint")
        port = int(lines[0])
        path = lines[1].strip()
        if not 1 <= port <= 65535 or not re.fullmatch(r"/devtools/browser/[A-Za-z0-9-]+", path):
            raise ValueError("invalid endpoint")
        return f"ws://127.0.0.1:{port}{path}"
    except FileNotFoundError as exc:
        raise RuntimeError("Chrome connection permission was not found. " + SETUP_MESSAGE) from exc
    except PermissionError as exc:
        raise RuntimeError("Chrome's connection file could not be read. Run Chrome and Raahi "
                           "under the same Windows account. " + SETUP_MESSAGE) from exc
    except (OSError, ValueError) as exc:
        raise RuntimeError("Chrome's connection file is invalid or unavailable. " + SETUP_MESSAGE) from exc


def open_chrome_setup(url='chrome://inspect/#remote-debugging'):
    """Open a setup tab in ordinary Chrome, without a new profile/debug flags."""
    if url != 'chrome://inspect/#remote-debugging':
        raise ValueError('Unsupported Chrome setup page')
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Google Chrome", url])
    elif os.name == "nt":
        for root in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            if os.environ.get(root):
                executable = Path(os.environ[root]) / "Google/Chrome/Application/chrome.exe"
                if executable.is_file():
                    subprocess.Popen([str(executable), url])
                    return
        raise RuntimeError("Google Chrome was not found. " + SETUP_MESSAGE)
    else:
        import shutil
        executable = shutil.which("google-chrome") or shutil.which("google-chrome-stable")
        if not executable:
            raise RuntimeError("Google Chrome was not found. " + SETUP_MESSAGE)
        subprocess.Popen([executable, url])


@contextmanager
def _profile_lock(profile):
    profile.parent.mkdir(parents=True, exist_ok=True)
    lock = open(profile.parent / (profile.name + ".lock"), "a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            if not lock.read(1):
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        acquired = True
        yield
    except (BlockingIOError, OSError) as exc:
        if not acquired:
            raise RuntimeError("Raahi's eAuctionsIndia browser is already in use by another app instance.") from exc
        raise
    finally:
        if acquired:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
        lock.close()


class _ChromeSession:
    def __init__(self):
        self.tasks = queue.Queue()
        self.driver = self.browser = self.page = None
        self.closed = False
        self.thread = threading.Thread(target=self._run, name="Raahi Chrome connection", daemon=True)
        self.thread.start()

    def invoke(self, method, *args, **kwargs):
        if self.closed:
            raise RuntimeError("The Chrome connection has been disconnected.")
        future = Future()
        self.tasks.put((future, method, args, kwargs))
        return future.result(timeout=240)

    def _connect(self):
        if self.browser is not None and self.browser.is_connected():
            if self.page is None or self.page.is_closed():
                context = self.browser.contexts[0]
                self.page = _existing_auction_tab(context) or context.new_page()
                self.page.set_default_timeout(60000)
            return
        if self.driver is not None:
            self.driver.stop()  # Disconnects the transport; does not close Chrome.
        from playwright.sync_api import sync_playwright
        self.driver = sync_playwright().start()
        try:
            self.browser = self.driver.chromium.connect_over_cdp(
                chrome_endpoint(), no_defaults=True, timeout=180000,
                headers={"User-Agent": "RaahiScraper"},
            )
            context = self.browser.contexts[0]
            self.page = _existing_auction_tab(context) or context.new_page()
            self.page.set_default_timeout(60000)
        except Exception as exc:
            self.driver.stop()
            self.driver = self.browser = self.page = None
            if isinstance(exc, RuntimeError) and SETUP_MESSAGE in str(exc):
                raise
            raise RuntimeError("Chrome could not establish the connection. Approve its connection prompt "
                "or re-enable its permission after restarting Chrome, then retry. " + SETUP_MESSAGE) from exc

    def _run(self):
        while True:
            future, method, args, kwargs = self.tasks.get()
            try:
                if method == "disconnect":
                    if self.driver is not None:
                        self.driver.stop()
                    self.driver = self.browser = self.page = None
                    future.set_result(None)
                    if self.closed:
                        return
                    continue
                if method == "ensure":
                    self._connect()
                    future.set_result(None)
                    continue
                if method == "connected":
                    future.set_result(self.browser is not None and self.browser.is_connected())
                    continue
                if self.page is None:
                    raise RuntimeError("Connect to Chrome first. " + SETUP_MESSAGE)
                if method == "fetch_asset":
                    value = self.page.evaluate("""async ({url, timeout}) => {
                        const controller = new AbortController();
                        const timer = setTimeout(() => controller.abort(), timeout);
                        try {
                            const response = await fetch(url, {credentials: 'include', signal: controller.signal});
                            const type = response.headers.get('content-type') || '';
                            if (!response.ok || type.toLowerCase().includes('text/html')) {
                                return {status: response.status, type, data: null};
                            }
                            const bytes = new Uint8Array(await response.arrayBuffer());
                            let binary = '';
                            for (let index = 0; index < bytes.length; index += 8192) {
                                binary += String.fromCharCode(...bytes.subarray(index, index + 8192));
                            }
                            return {status: response.status, type, data: btoa(binary)};
                        } finally {clearTimeout(timer);}
                    }""", {"url": args[0], "timeout": 30000})
                    future.set_result(value)
                    continue
                value = getattr(self.page, method)(*args, **kwargs)
                if method == "goto":
                    try:
                        if _is_auction_page(self.page):
                            self.page.evaluate('(key) => sessionStorage.setItem(key, "1")', MANAGED_TAB_KEY)
                    except Exception:
                        # Verification/navigation can replace the document mid-call.
                        pass
                    value = SimpleNamespace(status=value.status) if value else None
                future.set_result(value)
            except Exception as exc:
                future.set_exception(exc)

    def disconnect(self):
        self.invoke("disconnect")

    def stop(self):
        if self.closed:
            return
        future = Future()
        self.closed = True
        self.tasks.put((future, "disconnect", (), {}))
        try:
            future.result(timeout=3)
        except Exception:
            pass


class ChromePage:
    def __init__(self, session):
        self.session = session

    def goto(self, url, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in AUCTION_HOSTS:
            raise ValueError("Raahi only navigates its auction tab to eAuctionsIndia HTTPS URLs.")
        return self.session.invoke("goto", url, **kwargs)

    def content(self):
        return self.session.invoke("content")

    def wait_for_timeout(self, milliseconds):
        return self.session.invoke("wait_for_timeout", milliseconds)

    def bring_to_front(self):
        return self.session.invoke("bring_to_front")

    def is_closed(self):
        return self.session.invoke("is_closed")


_session = None
_session_lock = threading.Lock()


def disconnect_chrome():
    """Release Raahi's connection; leave the user's Chrome and tabs open."""
    if browser_backend() == 'cloak':
        return  # CloakBrowser closes at the end of each check/scrape/export.
    with _session_lock:
        if _session is not None:
            _session.disconnect()


def fetch_chrome_attachment(url):
    """Export-time fallback for protected public assets in the approved session."""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in (
        'www.eauctionsindia.com', 'eauctionsindia.com', 'www.eauctionsindia.org', 'eauctionsindia.org'
    ) or not parsed.path.startswith('/storage/'):
        raise ValueError('Chrome attachment access is limited to eAuctionsIndia storage URLs.')
    if browser_backend() == 'cloak':
        from scrapers.cloak_browser import fetch_cloak_attachment
        return fetch_cloak_attachment(url)
    with _session_lock:
        session = _session
    if session is None:
        raise RuntimeError('Connect to Chrome before downloading protected eAuctionsIndia images.')
    session.invoke('ensure')
    result = session.invoke('fetch_asset', url)
    return SimpleNamespace(
        status_code=result['status'],
        headers={'Content-Type': result['type']},
        content=base64.b64decode(result['data'], validate=True) if result.get('data') else b'',
    )


def _stop_session():
    if _session is not None:
        _session.stop()


atexit.register(_stop_session)


def browser_ready():
    """Check prerequisites before queuing scrape tasks or opening auction pages."""
    if browser_backend() == 'cloak':
        # The browser binary is intentionally not bundled in Raahi. CloakHQ's
        # wrapper downloads it on first use from its official distribution.
        return find_spec('cloakbrowser') is not None
    with _session_lock:
        session = _session
    if session is not None and not session.closed and session.invoke('connected'):
        return True
    try:
        chrome_endpoint()
        return True
    except RuntimeError:
        return False


@contextmanager
def desktop_browser(playwright, start_url):
    """Yield a tab in the existing Chrome; retain the approved app connection."""
    global _session
    with _profile_lock(browser_profile()):
        if browser_backend() == 'cloak':
            from scrapers.cloak_browser import cloak_desktop_browser
            with cloak_desktop_browser(playwright, start_url) as page:
                yield page
            return
        with _session_lock:
            if _session is None or _session.closed:
                chrome_endpoint()
                _session = _ChromeSession()
            session = _session
        session.invoke("ensure")
        yield ChromePage(session)
