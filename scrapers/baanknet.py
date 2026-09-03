"""BaankNet auction scraper using the current public JSON API."""

from scrapers.baanknet_property import scrape as scrape_properties


def scrape(state, progress_callback=None):
    return scrape_properties(
        state,
        progress_callback=progress_callback,
        source_name="baanknet",
        auction_available_only=True,
    )
