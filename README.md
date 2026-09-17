# Raahi Property Scraper

A Python desktop application for collecting bank auction property listings from multiple Indian auction platforms. It uses a graphical interface to run scrapers, deduplicates listings, and exports results to Excel.

## What it includes

- A CustomTkinter GUI for running and monitoring scraping tasks.
- Platform-specific scrapers under `scrapers/`.
- Listing deduplication and a local JSON record of previously seen properties.
- Excel export for reviewing collected listings.

## Local setup

Use Python 3.8 or newer:

```bash
python -m venv .venv
# Activate the virtual environment for your operating system.
pip install -r requirements.txt
python gui.py
```

Scraping requires an internet connection. Source websites can change or restrict automated access, so results and availability may vary.

## Documentation

See [Technical Documentation](TECHNICAL_DOCUMENTATION.md) for the architecture, modules, configuration, build notes, and troubleshooting.

Do not commit downloaded property data or private credentials to the repository.