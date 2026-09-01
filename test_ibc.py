
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from scrapers import baanknet_ibc
from config import BAANKNET_STATE_IDS

def test_scrape():
    state = "Delhi"
    print(f"Testing BaankNet IBC scrape for {state}...")
    results = baanknet_ibc.scrape(state)
    print(f"Found {len(results)} items")
    if results:
        print("First item sample:")
        print(results[0])
        print("Images:", results[0].get('images'))

if __name__ == "__main__":
    test_scrape()
