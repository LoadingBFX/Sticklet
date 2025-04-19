#!/usr/bin/env python
"""
Script to convert purchase data from JSON to SQLite database.
"""

import json
import sqlite3
import os
import uuid
import datetime
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent / 'data'
JSON_PATH = DATA_DIR / 'purchases_fixed.json'
DB_PATH = os.environ.get('DB_PATH') or (DATA_DIR / 'purchases.db')

def setup_database(db_path):
    """Set up SQLite database with necessary tables."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create purchases table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS purchases (
        id TEXT PRIMARY KEY,
        merchant_name TEXT NOT NULL,
        transaction_date TEXT NOT NULL,
        total_amount REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        payment_method TEXT
    )
    ''')
    
    # Create items table with foreign key to purchases
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id TEXT NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER DEFAULT 1,
        category TEXT DEFAULT 'Other',
        FOREIGN KEY (purchase_id) REFERENCES purchases (id)
    )
    ''')
    
    conn.commit()
    return conn

def reset_database(conn):
    """Reset the database by dropping all tables and recreating them."""
    cursor = conn.cursor()
    
    # Drop tables in reverse order to avoid foreign key constraints
    cursor.execute("DROP TABLE IF EXISTS items")
    cursor.execute("DROP TABLE IF EXISTS purchases")
    
    # Recreate tables
    cursor.execute('''
    CREATE TABLE purchases (
        id TEXT PRIMARY KEY,
        merchant_name TEXT NOT NULL,
        transaction_date TEXT NOT NULL,
        total_amount REAL NOT NULL,
        currency TEXT DEFAULT 'USD',
        payment_method TEXT
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id TEXT NOT NULL,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER DEFAULT 1,
        category TEXT DEFAULT 'Other',
        FOREIGN KEY (purchase_id) REFERENCES purchases (id)
    )
    ''')
    
    conn.commit()
    print("Database reset complete. All tables were dropped and recreated.")

def import_from_json(json_path, conn, force_reset=False):
    """Import data from JSON file to SQLite database."""
    try:
        # Read JSON data
        with open(json_path, 'r') as f:
            purchases = json.load(f)
        
        if not purchases:
            print("No purchase data found in JSON file")
            return 0
            
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM purchases")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            if force_reset:
                reset_database(conn)
            else:
                # Ask for confirmation before proceeding
                print(f"Database already contains {existing_count} purchase records.")
                print("Do you want to reset the database and reimport all data? (y/n)")
                response = input().lower()
                if response == 'y':
                    reset_database(conn)
                else:
                    print("Import cancelled. Keeping existing data.")
                    return 0
        
        # Import each purchase and its items
        imported_count = 0
        
        # Create a dict to track merchant-date combinations to ensure unique IDs
        merchant_date_ids = {}
        
        for purchase in purchases:
            try:
                # Generate a unique ID based on merchant and date if needed
                if 'id' not in purchase or purchase['id'] in merchant_date_ids:
                    merchant_key = f"{purchase['merchant_name']}_{purchase['transaction_date']}"
                    
                    if merchant_key in merchant_date_ids:
                        # If this merchant-date combination already exists, append a counter
                        merchant_date_ids[merchant_key] += 1
                        unique_id = f"{merchant_key}_{merchant_date_ids[merchant_key]}"
                    else:
                        merchant_date_ids[merchant_key] = 1
                        unique_id = merchant_key
                        
                    # Convert to a valid ID format
                    purchase_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, unique_id))
                else:
                    purchase_id = purchase['id']
                    
                # Insert purchase
                cursor.execute(
                    """
                    INSERT INTO purchases 
                    (id, merchant_name, transaction_date, total_amount, currency, payment_method) 
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        purchase_id,
                        purchase['merchant_name'],
                        purchase['transaction_date'],
                        purchase['total_amount'],
                        purchase.get('currency', 'USD'),
                        purchase.get('payment_method')
                    )
                )
                
                # Insert items
                for item in purchase.get('items', []):
                    cursor.execute(
                        """
                        INSERT INTO items 
                        (purchase_id, name, price, quantity, category) 
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            purchase_id,
                            item['name'],
                            item['price'],
                            item.get('quantity', 1),
                            item.get('category', 'Other')
                        )
                    )
                
                imported_count += 1
                
            except Exception as e:
                print(f"Error importing purchase {purchase.get('id', 'unknown')}: {e}")
                continue
        
        conn.commit()
        return imported_count
        
    except Exception as e:
        print(f"Error importing JSON data: {e}")
        return 0

def verify_import(conn):
    """Verify imported data and print summary."""
    cursor = conn.cursor()
    
    # Get purchases count
    cursor.execute("SELECT COUNT(*) FROM purchases")
    purchases_count = cursor.fetchone()[0]
    
    # Get items count
    cursor.execute("SELECT COUNT(*) FROM items")
    items_count = cursor.fetchone()[0]
    
    # Get total amount
    cursor.execute("SELECT SUM(total_amount) FROM purchases")
    total_amount = cursor.fetchone()[0] or 0
    
    # Get unique merchants
    cursor.execute("SELECT COUNT(DISTINCT merchant_name) FROM purchases")
    merchants_count = cursor.fetchone()[0]
    
    # Get unique categories
    cursor.execute("SELECT COUNT(DISTINCT category) FROM items")
    categories_count = cursor.fetchone()[0]
    
    print("\n--- Database Summary ---")
    print(f"Purchases: {purchases_count}")
    print(f"Items: {items_count}")
    print(f"Total Amount: ${total_amount:.2f}")
    print(f"Unique Merchants: {merchants_count}")
    print(f"Unique Categories: {categories_count}")
    
    # Print merchants and purchase counts
    cursor.execute("""
    SELECT merchant_name, COUNT(*) as purchase_count, SUM(total_amount) as total
    FROM purchases 
    GROUP BY merchant_name 
    ORDER BY total DESC
    """)
    merchants = cursor.fetchall()
    
    print("\n--- Merchants Summary ---")
    for merchant, count, total in merchants:
        print(f"{merchant}: {count} purchases, ${total:.2f}")
    
    return purchases_count, items_count

def query_sample_data(conn):
    """Run some sample queries to demonstrate SQL functionality."""
    cursor = conn.cursor()
    
    print("\n--- Sample Queries ---")
    
    # Total spent by category
    print("\nTotal spent by category:")
    cursor.execute("""
    SELECT i.category, SUM(i.price * i.quantity) as total 
    FROM items i 
    GROUP BY i.category 
    ORDER BY total DESC
    """)
    for category, total in cursor.fetchall():
        print(f"{category}: ${total:.2f}")
    
    # Top items by price
    print("\nTop 5 most expensive items:")
    cursor.execute("""
    SELECT i.name, i.price, i.category, p.merchant_name
    FROM items i
    JOIN purchases p ON i.purchase_id = p.id
    ORDER BY i.price DESC
    LIMIT 5
    """)
    for name, price, category, merchant in cursor.fetchall():
        print(f"{name} (${price:.2f}) - {category} from {merchant}")
        
    # Monthly spending
    print("\nSpending by month:")
    cursor.execute("""
    SELECT strftime('%Y-%m', transaction_date) as month, SUM(total_amount) as total
    FROM purchases
    GROUP BY month
    ORDER BY month
    """)
    for month, total in cursor.fetchall():
        print(f"{month}: ${total:.2f}")

def main():
    print(f"Converting purchase data from JSON to SQLite")
    print(f"JSON file: {JSON_PATH}")
    print(f"SQLite database: {DB_PATH}")
    
    if not JSON_PATH.exists():
        print(f"ERROR: JSON file not found at {JSON_PATH}")
        return
    
    db_path_str = str(DB_PATH)
    conn = setup_database(db_path_str)
    
    print("\nImporting data...")
    # Force reset on import
    imported_count = import_from_json(JSON_PATH, conn, force_reset=True)
    print(f"Successfully imported {imported_count} purchases")
    
    if imported_count > 0:
        purchases_count, items_count = verify_import(conn)
        print(f"\nDatabase now contains {purchases_count} purchases with {items_count} items")
        
        # Run sample queries
        query_sample_data(conn)
    
    conn.close()
    print("\nConversion complete!")

if __name__ == "__main__":
    main()