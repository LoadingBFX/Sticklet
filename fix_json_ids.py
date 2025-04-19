#!/usr/bin/env python
"""
Script to fix duplicate IDs in the purchases.json file.
"""

import json
import uuid
from pathlib import Path

# Path to JSON file
JSON_PATH = Path(__file__).parent / 'data' / 'purchases.json'
OUTPUT_PATH = Path(__file__).parent / 'data' / 'purchases_fixed.json'

def fix_json_ids(json_path, output_path):
    """Fix duplicate IDs in JSON file."""
    print(f"Reading JSON file: {json_path}")
    
    # Read JSON data
    with open(json_path, 'r') as f:
        purchases = json.load(f)
    
    if not purchases:
        print("No purchase data found in JSON file")
        return
    
    print(f"Found {len(purchases)} purchases")
    
    # Check for duplicate IDs
    ids = [p.get('id') for p in purchases if 'id' in p]
    unique_ids = set(ids)
    
    if len(ids) != len(unique_ids):
        print(f"Found {len(ids) - len(unique_ids)} duplicate IDs")
    
    # Create a dict to track merchant-date combinations to ensure unique IDs
    merchant_date_ids = {}
    
    # Update each purchase with a unique ID
    for purchase in purchases:
        merchant_key = f"{purchase['merchant_name']}_{purchase['transaction_date']}"
        
        if merchant_key in merchant_date_ids:
            # If this merchant-date combination already exists, append a counter
            merchant_date_ids[merchant_key] += 1
            unique_id = f"{merchant_key}_{merchant_date_ids[merchant_key]}"
        else:
            merchant_date_ids[merchant_key] = 1
            unique_id = merchant_key
            
        # Generate a deterministic UUID for the purchase ID
        purchase['id'] = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_id))
    
    # Write updated JSON
    with open(output_path, 'w') as f:
        json.dump(purchases, f, indent=2)
    
    print(f"Fixed IDs and wrote to: {output_path}")
    print(f"Total purchases: {len(purchases)}")

if __name__ == "__main__":
    fix_json_ids(JSON_PATH, OUTPUT_PATH)
    print("Done!")