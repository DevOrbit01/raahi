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
    source = str(item.get('source', '')).strip()
    listing_id = str(item.get('listingId', '')).strip()
    if source and listing_id:
        key_data = {'source': source, 'listingId': listing_id}
    else:
        # Fall back to stable public identifiers before using changing business fields.
        key_data = {
            'source': source,
            'url': item.get('url', ''),
            'notice': item.get('notice', ''),
            'name': item.get('name', ''),
            'city': item.get('city', ''),
        }
    
    # Create a consistent string representation
    data_string = json.dumps(key_data, sort_keys=True)
    
    # Generate MD5 hash
    return hashlib.md5(data_string.encode()).hexdigest()


def generate_legacy_fingerprint(item):
    """Fingerprint format used by older app builds."""
    key_data = {
        'listingId': item.get('listingId', ''),
        'source': item.get('source', ''),
        'bankName': item.get('bankName', ''),
        'city': item.get('city', ''),
        'reservePrice': item.get('reservePrice', 0),
    }
    data_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(data_string.encode()).hexdigest()
