# Raahi Scraper: project status and handoff

Last updated: 16 October 2026 (Asia/Kolkata).

This is the consolidated handoff for work discussed in the Raahi chat. Read this
before changing the application. Some sections of older setup documents describe
the previous Chrome connector; the CloakBrowser behavior below is current.

## Locations and Git state

- Local source: `/Users/devil/Desktop/Python-Scrapers/raahi-scraper-software`.
- Working artifacts and test reports: `/Users/devil/Documents/Codex/2026-10-11/mere-system-mein-ek-project-hai/outputs`.
- Project locator: `/Users/devil/Documents/Codex/projects/registry.json`, entry `raahi-scraper`.
- Local remote is `https://github.com/Gabbar0546/raahi.git`; the connected GitHub repository used for builds is `DevOrbit01/raahi`.
- The current application and handoff notes are published on the GitHub `main` branch. The local working branch is also `main`; inspect its current status before editing or syncing. The named build branches retain the corresponding release snapshots.
- The shared credentials vault is for secrets, not project history. No Raahi-specific secret was supplied in this chat. GitHub builds used the existing connected GitHub app.

## Current application

Python CustomTkinter desktop GUI with seven scraper choices: BaankNet, BaankNet
IBC, BaankNet Vehicle, BaankNet Property, eAuctionsIndia, BankEAuctions and
BankAuction.in. Current work focused on eAuctionsIndia, export behavior,
download history and Windows packaging. Do not assume every source/state has
been fully retested merely because the app builds.

### eAuctionsIndia browser

- The packaged Windows app defaults to local CloakBrowser. Source checkouts default to the legacy Chrome connector unless `EAUCTIONSINDIA_BROWSER_BACKEND=cloak` is set.
- CloakBrowser starts headless with a dedicated persistent profile. If site verification does not finish, the application can open a visible auction browser for the user to complete verification.
- The current Windows flow requires no Chrome extension, remote-debugging setup or Python installation. Earlier Chrome/extension approaches were explored and superseded for the default packaged flow.
- The browser binary is downloaded directly from CloakHQ on first use; it is not bundled in the EXE. The wrapper and binary have different licenses; the binary's customer workflow terms have not been commercially cleared in this chat.
- No paid scraping service or subscription was used. Automatic access in every situation is not guaranteed. Cloudflare can require fresh human verification.
- Catalogue/detail data comes from `www.eauctionsindia.com`. Some notices come from `www.eauctionsindia.org/storage/`; `.org` was not verified as a complete alternative catalogue.
- The relevant implementations are `scrapers/eauctionsindia.py`, `scrapers/cloak_browser.py`, `scrapers/local_browser.py` and `scrapers/scrape_progress.py`.

### Data, Excel, images and notices

- Scraping collects image URLs; local attachment files are downloaded only on export when **Download Images and Notices with Excel** is checked.
- Unchecked export creates Excel with URLs and performs no new attachment download. Previously downloaded files remain in the output folder.
- Excel fields include `propertyImageUrls` (photos), `noticeImageUrls` (image notices), `images` (combined image URLs), `imageKinds` and `pdfLinks` (documents/notices, including some image-format notices).
- Files go beside Excel under `images/<listingId>/media_N.ext` and `documents/<listingId>/document_N.ext`.
- A notice included in both image and document URLs is fetched once and copied to both destinations. Some source listings have no property photos.
- Blocked eAuctionsIndia attachments use the selected browser backend as a fallback. Failed attachments are reported and those properties remain retryable.
- Default Windows export directory: `%LOCALAPPDATA%\RaahiScraper\Exports`.
- Default Mac directory: `/Users/devil/Library/Application Support/RaahiScraper/Exports`.
- **Watermark removal is not integrated.** The user explicitly cancelled using external watermark-removal services. Original source image bytes/URLs are preserved. Local threshold/inpaint trials affected text. One watermarkremover.io test cleaned a notice visually, but its guest flow required browser challenges and was not an unrestricted production API. Do not resume this integration without a new request.

### Download history: intended behavior confirmed by user

- Identity is the fingerprint of `source + listingId`, with a fallback for missing identifiers and compatibility checks for the older fingerprint format.
- Successfully exported property fingerprints are saved to `seen_properties.json` under the per-user RaahiScraper application-data directory.
- History filtering happens on a **new Start Scraping run**. Downloaded properties are omitted from its returned list.
- Repeated **Download Selected** from the current displayed selection is deliberately allowed. The user explicitly confirmed this is correct. Do not add export-time duplicate blocking or remove successfully exported rows from the current list.
- Deleting Excel/images does not delete fingerprint history. There is no history expiration. Clear Database or deleting/corrupting the history can allow old rows again. Each Windows user/PC has separate history.
- Source names are distinct: BaankNet and BaankNet Property do not share an identity namespace. Changed price/date under the same source/listing ID remains previously downloaded; a new listing ID is treated as new.
- History is marked after export; if requested attachments fail, affected rows are not marked complete and can reappear for retry.
- Old release history was tested on Windows using modules extracted from the exact delivered EXE, real Tk GUI/export code, simulated Assam data and separate processes. Two exported rows were skipped after restarting even after Excel deletion; an unexported third row remained. Native EXE self-test also passed. The client's physical PC was not tested.
- Evidence: `outputs/windows-history-audit-20261015/windows-history-audit.json`; workflow https://github.com/DevOrbit01/raahi/actions/runs/38785917487.

### Missing-date fix: 16 October 2026

- Maharashtra listing https://www.eauctionsindia.com/properties/896731 has a title/ID but no auction date in the checked live page or structured data. Previously this stopped the state after ten valid rows on page 1.
- Loaded listings missing required fields are now skipped with a warning; other listings and later pages continue.
- Skipped URLs/reasons are retained in the current SQLite checkpoint separately from valid rows and exported fingerprints. Resume preserves warnings. A fresh completed/expired run checks those listings again, allowing corrected source data to appear.
- The GUI reports the number of incomplete listings skipped and logs their URLs/reasons. Incomplete listings are not exported or marked downloaded.
- Network errors, unresolved verification and wrong-state results retain error handling rather than being silently skipped.
- 32 regression tests passed. A live bounded Maharashtra probe using a copy of the user's checkpoint completed two pages, retained 23 valid rows, skipped 896731, and found page 3. The entire Maharashtra catalogue was not scraped in this test.
- Native Windows packaged checks verified both pagination past missing data and GUI warning display. The Windows browser launched, but the CI live site probe still required human verification.
- Detailed evidence: `outputs/maharashtra-investigation-20261016/fix-report.md`, `live-two-pages.json`, `local-packaging-check.json`; native Windows evidence is in `outputs/windows-missing-date-release/`.

## Windows releases

### Latest fixed build, ready locally

- Desktop ZIP: `/Users/devil/Desktop/RaahiScraper-Windows-MissingDateFix.zip`.
- Saved copy: `outputs/RaahiScraper-Windows-MissingDateFix.zip`.
- Extracted EXE/evidence: `outputs/windows-missing-date-release/`.
- Branch: `build/windows-missing-date-2026-10-16`.
- Commit: `025b37bc4a762052b57ed37f69255ef132de96aa`.
- Workflow: https://github.com/DevOrbit01/raahi/actions/runs/38787639618.
- ZIP SHA256: `f4a2d9efa5403f5607bffddc0687eb3a593ba3aa62eaa9d5f869f6bb69148c38`.
- EXE SHA256: `0182171af547ec3c725b2190e8d2672d538355e1784bbca6ae004db2a49d70c0`.
- Unsigned Windows x64 build; ZIP integrity, source commit and executable hash verified. Native packaging tests passed. Physical client Windows acceptance remains outstanding. Do not claim the Windows CI live Cloudflare probe passed.

### Previous build confirmed sent to client

- Name: `RaahiScraper-Windows-CloakBrowser.zip`.
- Commit: `4f9bf4e166fc9671b13cd038f58543ecd6d86122`.
- Workflow: https://github.com/DevOrbit01/raahi/actions/runs/38170653391.
- ZIP SHA256: `3553db59ecbf7bf89ec397e9ef1c4199372e888e4c28b395511cb4312dae5b7e`.
- EXE SHA256: `48234cba84608196377f9ab825599e921e80d86e6f176bf091f93b2647d499c0`.
- It has download history, but predates the missing-date continuation fix. User has not yet confirmed sending the newer MissingDateFix ZIP to the client.

## Backups

Under the shared `outputs` folder:

- `raahi-code-backup-20261012-010658.zip`: before CloakBrowser work.
- `raahi-before-watermark-integration-20261014.zip`: source backup before the subsequently cancelled external watermark integration.
- `raahi-before-missing-date-fix-20261016.zip`: five touched source/test files before the missing-date fix; this is not a full repository archive.

## Local run and checks

From the source directory:

```sh
env EAUCTIONSINDIA_BROWSER_BACKEND=cloak ./.venv/bin/python gui.py
./.venv/bin/python -m unittest discover -s tests -q
```

The latest GUI was reloaded with only eAuctionsIndia and Maharashtra selected,
without automatically starting the full scrape. A future session should inspect
the current process/window rather than assume it remains open.

## Remaining client follow-up

Confirm the latest fixed ZIP on the client's Windows PC. If fingerprint filtering
fails there after a fresh scrape, inspect the exact EXE hash, selected source,
successful export/attachment status and that Windows user's saved history file.
Do not diagnose repeated export from the same current list as a history defect.
