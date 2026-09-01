"""Generate unique fingerprints for properties to detect duplicates"""
import hashlib
import json


def generate_fingerprint(item):
    """
    Generate a unique fingerprint for a property based on key attributes
    
    Args:
        item (dict): Property data
        
    Returns:
        str: MD5 hash fingerprint
    """
    # Use key fields that uniquely identify a property
    key_data = {
        'listingId': item.get('listingId', ''),
        'source': item.get('source', ''),
        'bankName': item.get('bankName', ''),
        'city': item.get('city', ''),
        'reservePrice': item.get('reservePrice', 0),
    }
    
    # Create a consistent string representation
    data_string = json.dumps(key_data, sort_keys=True)
    
    # Generate MD5 hash
    return hashlib.md5(data_string.encode()).hexdigest()
