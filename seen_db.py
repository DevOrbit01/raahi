"""Simple file-based database to track seen properties"""
import json
import os
import sys


APP_NAME = "RaahiScraper"


def _default_db_file():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME, "seen_properties.json")


class SeenDatabase:
    def __init__(self, db_file=None):
        db_file = db_file or _default_db_file()
        if not os.path.isabs(db_file):
            db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_file)
        self.db_file = db_file
        self.seen = self._load()
    
    def _load(self):
        """Load seen fingerprints from file"""
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, OSError, TypeError):
                return set()
        return set()
    
    def _save_to_disk(self):
        """Save seen fingerprints to file"""
        try:
            os.makedirs(os.path.dirname(self.db_file), exist_ok=True)
            with open(self.db_file, 'w') as f:
                json.dump(list(self.seen), f)
        except Exception as e:
            print(f"Error saving seen database: {e}")

    def reload(self):
        """Reload fingerprints from disk."""
        self.seen = self._load()
    
    def exists(self, fingerprint):
        """Check if fingerprint exists in database"""
        return fingerprint in self.seen
    
    def save(self, fingerprint):
        """Add fingerprint to database"""
        if not fingerprint:
            return
        self.seen.add(fingerprint)
        self._save_to_disk()

    def save_many(self, fingerprints):
        """Add multiple fingerprints and write once."""
        changed = False
        for fingerprint in fingerprints:
            if fingerprint and fingerprint not in self.seen:
                self.seen.add(fingerprint)
                changed = True
        if changed:
            self._save_to_disk()
    
    def clear(self):
        """Clear all seen fingerprints"""
        self.seen = set()
        self._save_to_disk()


# Global instance
seen_db = SeenDatabase()
