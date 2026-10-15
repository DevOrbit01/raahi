# Raahi Property Scraper

A Python desktop application for collecting bank auction property listings from multiple Indian auction platforms. It uses a graphical interface to run scrapers, deduplicates listings, and exports results to Excel.

## What it includes

- A CustomTkinter GUI for running and monitoring scraping tasks.
- Platform-specific scrapers under `scrapers/`.
- Listing deduplication and a local JSON record of previously seen properties.
- Excel export for reviewing collected listings.
- eAuctionsIndia through a local CloakBrowser session, with visible human verification when the website requests it.
- Property-photo and notice URLs in Excel, with optional attachment downloads during export.
- Persistent download history: a fresh scrape skips previously exported listings; repeat export from the current displayed list remains allowed.
- Continued eAuctionsIndia pagination when a listing is missing required data, with skipped-listing warnings in the GUI.
- Windows x64 build workflow and packaged application checks.

## Local setup

The current Windows build and regression suite are tested with Python 3.13.

```bash
python -m venv .venv
# Activate the virtual environment for your operating system.
pip install -r requirements.txt
# Use the CloakBrowser backend when running from source.
# macOS/Linux:
EAUCTIONSINDIA_BROWSER_BACKEND=cloak python gui.py
# Windows PowerShell:
# $env:EAUCTIONSINDIA_BROWSER_BACKEND = 'cloak'
# python gui.py
```

Scraping requires an internet connection. Source websites can change or restrict automated access, so results and availability may vary.

The packaged Windows app selects CloakBrowser automatically. The browser binary
is downloaded from CloakHQ on first use; it is not bundled in the application.
The current default flow needs no Chrome extension or Chrome debugging setting.

## Export and history

Choose an output folder, scrape the selected sites/states, select listings and
click **Download Selected**. With **Download Images and Notices with Excel**
checked, attachments are saved under `images/<listingId>/` and
`documents/<listingId>/` beside Excel. Unchecked export saves Excel and source
URLs without downloading new attachments.

History is stored separately from Excel in the current user's RaahiScraper app
data directory as `seen_properties.json`. Deleting Excel does not clear that
history. Failed requested attachments leave the affected listing retryable.

## Windows build and tests

The workflow under `.github/workflows/build-windows.yml` builds and validates the
desktop EXE on Windows. Release snapshots are retained on the `build/windows-*`
branches. The latest missing-data fix is on
`build/windows-missing-date-2026-10-16`.

```bash
python -m unittest discover -s tests -q
```

The latest suite has 32 tests. Native packaged checks cover GUI initialization,
Excel export, file locking, continuing pagination past a missing auction date,
and displaying its warning. These checks do not establish successful live
scraping on every client PC; site verification may still be required.

## Documentation

See [Project Status and Handoff](PROJECT_STATUS.md) for the current implementation,
release hashes, backups, test evidence and pending client follow-up.
See [eAuctionsIndia Setup](EAUCTIONSINDIA_SETUP.md) and
[Windows Quick Start](WINDOWS_QUICK_START.txt) for setup details.
[Technical Documentation](TECHNICAL_DOCUMENTATION.md) contains the older general
architecture and configuration reference.

Do not commit downloaded property data or private credentials to the repository.
