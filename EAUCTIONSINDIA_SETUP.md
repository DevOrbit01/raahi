# eAuctionsIndia: CloakBrowser Windows build and image URLs

The new Windows executable defaults to a dedicated CloakBrowser profile. It
starts headless, reuses that profile across runs, and opens a visible browser
only if the website needs human verification. No Chrome extension or normal
Chrome remote-debugging permission is needed. The browser binary is downloaded
directly from CloakHQ on first use; it is not bundled in Raahi's ZIP or EXE.
See `WINDOWS_QUICK_START.txt` for client setup and acceptance checks.

The Chrome instructions below describe the explicit fallback mode used by
older Windows builds and source checkouts. To select that mode, set
`EAUCTIONSINDIA_BROWSER_BACKEND=chrome`. For local CloakBrowser source tests,
set `EAUCTIONSINDIA_BROWSER_BACKEND=cloak`.

## Existing Chrome fallback

Raahi connects directly to your normal Google Chrome. No Chrome extension or
pairing setup is required. The app accepts any browser version exposing a
compatible approved CDP connection, and creates one auction tab in that profile.
It does not launch a separate browser, create a browser profile, copy cookies,
or shut down Chrome. The approved connection is reused across access checks,
states and scrape runs while the app remains open.

Keep Chrome and Raahi's auction tab open; Chrome may be minimized. Subsequent
scrapes use that same verified browser session without launching another
browser. Raahi marks its auction tab using site session storage, so reconnecting
or restarting the app also reuses that tab while it remains open. Unrelated
tabs are not repurposed. No cookie file is created or imported into an HTTP
scraper: Chrome sends its own existing cookies on browser requests.

If the tab is closed, a new auction tab is needed, using the same Chrome profile
and any still-valid cookies there. If Chrome is closed, open it and reconnect.
The website can require human verification after expiry or invalidate clearance
earlier; Raahi detects the challenge, brings its tab forward, waits for the user,
and then resumes. Browser connection approval and site verification are separate.

## Browser connection setup

There is no forced browser-version rejection in Raahi. Chrome itself must expose
a compatible connection. Chrome 144+ provides the normal-profile permission UI
at `chrome://inspect/#remote-debugging`. Chrome 136-143 restricts debugging the
default profile through command-line flags and lacks that later permission UI.
Removing an application version check cannot add a missing browser feature.
Older versions are accepted if a compatible CDP connection is already exposed;
live operation across every historic Chrome version has not been verified.

1. Open your usual Google Chrome and choose your normal profile.
2. Open `chrome://inspect/#remote-debugging` and enable **Allow remote debugging
   for this browser instance**.
3. Start Raahi and click **Check eAuctionsIndia Browser Access**. Approve the
   incoming connection prompt in Chrome if shown.
4. If eAuctionsIndia asks for human verification, complete it in the Chrome
   auction tab. Raahi waits up to 180 seconds and resumes when the actual page
   appears. It does not click or solve CAPTCHAs.
5. Select eAuctionsIndia and your states, then click **Start Scraping**.
6. Select the returned properties and click **Download Selected**.

The **Open Chrome Connection Settings** button opens that setup page in ordinary
Chrome, without custom browser flags or a new profile. **Disconnect Chrome**
releases the connection and leaves your browser and tabs open. Chrome may ask
for permission again after a disconnect, browser restart or app restart. Its
permission dialog cannot be guaranteed to persist forever.

Chrome's permission is broader than a single site: it grants the connected app
browser-profile access. Raahi navigates only its own eAuctionsIndia HTTPS tab,
does not export cookies, and disconnects its transport when the app exits.
Disable the setting in Chrome when you no longer need this connection.

## Images and notices: same export flow as BaankNet

Auction listings and details are read from `www.eauctionsindia.com`.
`www.eauctionsindia.org/storage/...` supplies some notice attachments. On
11 October 2026, the `.org` homepage and sampled state/detail routes returned
404; a sampled `.org` JPG notice URL returned a valid image response. `.org`
has not been verified as an alternative complete auction catalogue.

Scraping collects URLs and listing data. It does **not** save attachment files
locally. The spreadsheet includes:

| Column | Meaning |
| --- | --- |
| `images` | All available image attachment URLs: property photos and image-format notices |
| `propertyImageUrls` | Property photo/gallery URLs only |
| `noticeImageUrls` | Sale notices supplied as JPG/PNG/WebP/etc. |
| `imageKinds` | `property-photo`, `sale-notice`, or both; makes the content type explicit |
| `pdfLinks` | Notice/document URLs; the original column can also contain JPG notices |

The parser handles normal/lazy image tags, source sets, image links, lightbox
links, property background images and metadata. It excludes website logos,
social icons and ads. A JPG sale notice is not represented as a property photo.
If the source publishes no property photos, `propertyImageUrls` remains blank.

With **Download Images and Notices with Excel** checked, **Download Selected**
first writes Excel, then saves files under `images/<listingId>/` and
`documents/<listingId>/`. If a JPG is both an image and a notice, it is fetched
once and placed in both folders. Uncheck the option for Excel and URLs only.

If a direct eAuctionsIndia attachment download is blocked, export retries the
storage URL through the connected, verified Chrome tab. The file is fetched
inside Chrome and saved by Raahi; cookies stay in Chrome. Keep Chrome connected
until the export finishes.

The default export folder is the current user's RaahiScraper application-data
folder under `Exports`: on Windows, `%LOCALAPPDATA%\RaahiScraper\Exports`.
It does not depend on the executable's installation/launch folder. Use the
output-folder selector to choose another writable location.

Failed downloads or HTML verification responses produce a warning. Properties
with failed attachments are not marked downloaded and can be retried.

## Run locally

From `/Users/devil/Desktop/Python-Scrapers/raahi-scraper-software`:

```sh
.venv/bin/python gui.py
```

For installation on another machine, use Python 3.10+ and a Google Chrome
installation with browser connection enabled:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

On Windows use `py -m venv .venv` and `.venv\Scripts\python.exe`.
The old `venv/` in this worktree contains Linux executables and is unusable on
macOS. No Playwright browser installation is required for existing-Chrome mode.

## Progress, concurrency and limits

Public parsed records and the next listing page are saved in SQLite under the
platform application data folder: macOS `~/Library/Application Support/RaahiScraper`,
Windows `%LOCALAPPDATA%\RaahiScraper`, Linux `$XDG_DATA_HOME/RaahiScraper` or
`~/.local/share/RaahiScraper`. Earlier browser profile files may still exist from
prior tests; the updated app does not launch or use them as a browser profile.

Incomplete checkpoints resume for up to six hours. Completed/older checkpoints
start fresh. Failed details remain pending. State scrapes use one browser
connection sequentially; other source scrapers can run in parallel. A file lock
prevents another app instance from simultaneously running eAuctionsIndia.

Pagination follows actual next links. The 10,000-page safety limit reports a
partial run and retains progress. The merged Dadra/Nagar Haveli and Daman/Diu
selection visits both catalogues. Chandigarh and Ladakh state URLs currently
return 404 and are absent from the website's state dropdown; they are reported
as unavailable. Valid zero-auction pages return zero rows.

Closed auctions remain included, matching the catalogue and previous behavior.
Website outages, mandatory verification, IP restrictions and missing photos are
source conditions; no tool can guarantee access or produce unpublished photos.
Windows/Linux path support requires testing on those operating systems.

## Advanced setting

`EAUCTIONSINDIA_CHROME_DATA_DIR` optionally points to the root user-data directory
of an already running Chrome channel, if it differs from Chrome Stable's default.
Raahi reads only `DevToolsActivePort` there to discover the opt-in loopback
WebSocket endpoint. Do not manually enable debugger command-line flags for your
daily profile.

`EAUCTIONSINDIA_BROWSER_PROFILE` is retained as a legacy setting for the public
checkpoint/lock location. It no longer launches that browser profile.
`EAUCTIONSINDIA_VERIFICATION_TIMEOUT` changes the 180-second site verification
wait. Cookies remain in Chrome and are never entered in the app.

## Validation and primary sources

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python gui.py --check-eauctionsindia
.venv/bin/python -m PyInstaller --noconfirm build.spec
```

Chrome's [existing-session connection documentation](https://developer.chrome.com/docs/devtools/agents/use-cases/auto-connect)
and the official [Chrome DevTools MCP implementation](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/src/BrowserManager.ts)
document the user-approved connection and endpoint discovery. Raahi uses its
existing [Playwright CDP dependency](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp)
without adding an MCP server or remote scraping service. No new extension is
required.
