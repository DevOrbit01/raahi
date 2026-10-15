"""Crash-safe local progress for a browser scrape; stores public listing data only."""
import json
import sqlite3
import time


class ScrapeProgress:
    def __init__(self, path, state, first_url, max_age=21600):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        self.db.execute("CREATE TABLE IF NOT EXISTS items (url TEXT PRIMARY KEY, payload TEXT)")
        previous = self.get("state")
        started = self.get("started", 0)
        self.resumed = bool(previous == state and not self.get("complete", False) and time.time() - started < max_age)
        if not self.resumed:
            with self.db:
                self.db.execute("DELETE FROM meta")
                self.db.execute("DELETE FROM items")
                self._set("state", state)
                self._set("started", time.time())
                self._set("complete", False)
                self._set("page_url", first_url)
                self._set("links", [])
                self._set("pages_done", 0)

    def get(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def _set(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, json.dumps(value)))

    def set_page(self, url, links, next_url):
        with self.db:
            self._set("page_url", url)
            self._set("links", links)
            self._set("next_url", next_url)

    def set_roots(self, roots):
        with self.db:
            self._set("remaining_roots", roots)

    def contains(self, url):
        return self.db.execute("SELECT 1 FROM items WHERE url = ?", (url,)).fetchone() is not None

    def add(self, url, item):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO items VALUES (?, ?)", (url, json.dumps(item)))

    def skip_detail(self, url, reason):
        """Retain a warning for this run without treating the listing as exported."""
        with self.db:
            skipped = self.skipped_details()
            skipped[url] = reason
            self._set("skipped_details", skipped)

    def skipped_details(self):
        return self.get("skipped_details", {})

    def advance(self, next_url):
        with self.db:
            roots = self.get("remaining_roots", [])
            if not next_url and roots:
                next_url = roots.pop(0)
                self._set("remaining_roots", roots)
            self._set("page_url", next_url)
            self._set("links", [])
            self._set("pages_done", self.get("pages_done", 0) + 1)
            if not next_url:
                self._set("complete", True)

    def items(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT payload FROM items ORDER BY rowid")]

    def close(self):
        self.db.close()
