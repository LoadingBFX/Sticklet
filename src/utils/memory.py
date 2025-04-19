"""
Memory module for the application - SQLite Implementation.
Provides classes for representing purchase data and storing it in a SQLite database.
"""
from typing import Dict, List, Any, Optional
import json
import os
import sqlite3
import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field


@dataclass
class PurchaseItem:
    """Data class for representing items in a purchase."""
    name: str
    price: float
    quantity: int = 1
    category: str = "Other"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return asdict(self)


@dataclass
class Purchase:
    """Data class for representing a purchase transaction."""
    merchant_name: str
    transaction_date: str
    total_amount: float
    items: List[PurchaseItem]
    currency: str = "USD"
    payment_method: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = asdict(self)
        # Convert PurchaseItem objects to dictionaries
        result["items"] = [item.to_dict() for item in self.items]
        return result


class PurchaseMemory:
    """
    Memory component for storing purchase history in a SQLite database.
    Implements the Memory Pattern by persisting purchase data and providing retrieval capabilities.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the purchase memory with SQLite.
        
        Args:
            db_path: Optional path to the SQLite database file.
                     If None, a default database path will be used.
        """
        if db_path is None:
            # Create a default storage directory in the project root
            storage_dir = Path(__file__).parent.parent.parent / "data"
            os.makedirs(storage_dir, exist_ok=True)
            db_path = str(storage_dir / "purchases.db")
        
        self.db_path = db_path
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create purchases table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS purchases (
            id TEXT PRIMARY KEY,
            merchant_name TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            total_amount REAL NOT NULL,
            currency TEXT DEFAULT 'USD',
            payment_method TEXT,
            notes TEXT
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
        conn.close()
    
    def add_purchase(self, purchase: Purchase) -> str:
        """
        Add a new purchase to the database.
        
        Args:
            purchase: Purchase object to add
            
        Returns:
            ID of the added purchase
        """
        print(f"Adding purchase to database: {purchase.merchant_name}, {purchase.transaction_date}, ${purchase.total_amount}")
        print(f"Database path: {self.db_path}")
        print(f"Purchase items: {len(purchase.items)} items")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if purchase with this ID already exists
            cursor.execute("SELECT id FROM purchases WHERE id = ?", (purchase.id,))
            existing = cursor.fetchone()
            
            if existing:
                print(f"Purchase with ID {purchase.id} already exists, updating instead of inserting")
                # Update the existing purchase
                # Convert notes list to JSON string
                notes_json = json.dumps(purchase.notes) if purchase.notes else None
                
                cursor.execute(
                    """
                    UPDATE purchases 
                    SET merchant_name = ?, transaction_date = ?, total_amount = ?, 
                        currency = ?, payment_method = ?, notes = ?
                    WHERE id = ?
                    """,
                    (
                        purchase.merchant_name,
                        purchase.transaction_date,
                        purchase.total_amount,
                        purchase.currency,
                        purchase.payment_method,
                        notes_json,
                        purchase.id
                    )
                )
                
                # Delete existing items for this purchase
                cursor.execute("DELETE FROM items WHERE purchase_id = ?", (purchase.id,))
            else:
                # Insert new purchase
                print(f"Inserting new purchase with ID: {purchase.id}")
                # Convert notes list to JSON string
                notes_json = json.dumps(purchase.notes) if purchase.notes else None
                
                cursor.execute(
                    """
                    INSERT INTO purchases 
                    (id, merchant_name, transaction_date, total_amount, currency, payment_method, notes) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        purchase.id,
                        purchase.merchant_name,
                        purchase.transaction_date,
                        purchase.total_amount,
                        purchase.currency,
                        purchase.payment_method,
                        notes_json
                    )
                )
            
            # Insert items
            for i, item in enumerate(purchase.items):
                print(f"Inserting item {i+1}: {item.name}, ${item.price}, qty={item.quantity}, category={item.category}")
                cursor.execute(
                    """
                    INSERT INTO items 
                    (purchase_id, name, price, quantity, category) 
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        purchase.id,
                        item.name,
                        item.price,
                        item.quantity,
                        item.category
                    )
                )
            
            conn.commit()
            print(f"Successfully added/updated purchase {purchase.id} to database")
            
            # Verify the data was stored
            cursor.execute("SELECT * FROM purchases WHERE id = ?", (purchase.id,))
            stored_purchase = cursor.fetchone()
            if stored_purchase:
                print(f"Verified purchase in database: {stored_purchase}")
            else:
                print(f"WARNING: Failed to verify purchase {purchase.id} in database")
                
            return purchase.id
            
        except Exception as e:
            conn.rollback()
            print(f"Error adding purchase to database: {e}")
            raise e
        finally:
            conn.close()

    def delete_purchase(self, purchase_id: str) -> None:
        """
        Delete a purchase and its items by purchase_id.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            # delete items first (FK constraint)
            cursor.execute(
                "DELETE FROM items WHERE purchase_id = ?",
                (purchase_id,)
            )
            # delete the purchase record
            cursor.execute(
                "DELETE FROM purchases WHERE id = ?",
                (purchase_id,)
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error deleting purchase {purchase_id}: {e}")
            raise
        finally:
            conn.close()
    
    def get_all_purchases(self) -> List[Purchase]:
        """
        Retrieve all purchases from the database.
        
        Returns:
            List of Purchase objects
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        purchases = []
        
        try:
            # Get all purchases
            cursor.execute("SELECT * FROM purchases")
            purchase_rows = cursor.fetchall()
            
            for row in purchase_rows:
                # Extract purchase data
                purchase_id, merchant_name, transaction_date, total_amount, currency, payment_method, notes_json = row
                
                # Get items for this purchase
                cursor.execute("SELECT name, price, quantity, category FROM items WHERE purchase_id = ?", (purchase_id,))
                item_rows = cursor.fetchall()
                
                # Create PurchaseItem objects
                items = [
                    PurchaseItem(
                        name=item[0],
                        price=item[1],
                        quantity=item[2],
                        category=item[3]
                    )
                    for item in item_rows
                ]
                
                # Parse notes JSON if present
                notes = []
                if notes_json:
                    try:
                        notes = json.loads(notes_json)
                    except json.JSONDecodeError:
                        print(f"Error parsing notes JSON for purchase {purchase_id}")
                        
                # Create Purchase object
                purchase = Purchase(
                    id=purchase_id,
                    merchant_name=merchant_name,
                    transaction_date=transaction_date,
                    total_amount=total_amount,
                    currency=currency,
                    payment_method=payment_method,
                    notes=notes,
                    items=items
                )
                
                purchases.append(purchase)
                
            return purchases
            
        except Exception as e:
            print(f"Error getting purchases: {e}")
            return []
        finally:
            conn.close()
    
    def get_purchases_by_merchant(self, merchant_name: str) -> List[Purchase]:
        """
        Retrieve all purchases from a specific merchant.
        
        Args:
            merchant_name: Name of the merchant to filter by
            
        Returns:
            List of Purchase objects matching the merchant name
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        purchases = []
        
        try:
            # Find purchases with the given merchant name (case-insensitive)
            cursor.execute(
                "SELECT * FROM purchases WHERE LOWER(merchant_name) LIKE ?", 
                (f"%{merchant_name.lower()}%",)
            )
            purchase_rows = cursor.fetchall()
            
            for row in purchase_rows:
                # Extract purchase data
                purchase_id, merchant_name, transaction_date, total_amount, currency, payment_method, notes_json = row
                
                # Get items for this purchase
                cursor.execute("SELECT name, price, quantity, category FROM items WHERE purchase_id = ?", (purchase_id,))
                item_rows = cursor.fetchall()
                
                # Create PurchaseItem objects
                items = [
                    PurchaseItem(
                        name=item[0],
                        price=item[1],
                        quantity=item[2],
                        category=item[3]
                    )
                    for item in item_rows
                ]
                
                # Parse notes JSON if present
                notes = []
                if notes_json:
                    try:
                        notes = json.loads(notes_json)
                    except json.JSONDecodeError:
                        print(f"Error parsing notes JSON for purchase {purchase_id}")
                        
                # Create Purchase object
                purchase = Purchase(
                    id=purchase_id,
                    merchant_name=merchant_name,
                    transaction_date=transaction_date,
                    total_amount=total_amount,
                    currency=currency,
                    payment_method=payment_method,
                    notes=notes,
                    items=items
                )
                
                purchases.append(purchase)
                
            return purchases
            
        except Exception as e:
            print(f"Error getting purchases by merchant: {e}")
            return []
        finally:
            conn.close()
    
    def get_purchases_by_date_range(self, start_date: str, end_date: str) -> List[Purchase]:
        """
        Retrieve all purchases within a date range.
        
        Args:
            start_date: Start date in format YYYY-MM-DD
            end_date: End date in format YYYY-MM-DD
            
        Returns:
            List of Purchase objects within the date range
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        purchases = []
        
        try:
            # Find purchases within the date range
            cursor.execute(
                "SELECT * FROM purchases WHERE transaction_date BETWEEN ? AND ?", 
                (start_date, end_date)
            )
            purchase_rows = cursor.fetchall()
            
            for row in purchase_rows:
                # Extract purchase data
                purchase_id, merchant_name, transaction_date, total_amount, currency, payment_method, notes_json = row
                
                # Get items for this purchase
                cursor.execute("SELECT name, price, quantity, category FROM items WHERE purchase_id = ?", (purchase_id,))
                item_rows = cursor.fetchall()
                
                # Create PurchaseItem objects
                items = [
                    PurchaseItem(
                        name=item[0],
                        price=item[1],
                        quantity=item[2],
                        category=item[3]
                    )
                    for item in item_rows
                ]
                
                # Parse notes JSON if present
                notes = []
                if notes_json:
                    try:
                        notes = json.loads(notes_json)
                    except json.JSONDecodeError:
                        print(f"Error parsing notes JSON for purchase {purchase_id}")
                        
                # Create Purchase object
                purchase = Purchase(
                    id=purchase_id,
                    merchant_name=merchant_name,
                    transaction_date=transaction_date,
                    total_amount=total_amount,
                    currency=currency,
                    payment_method=payment_method,
                    notes=notes,
                    items=items
                )
                
                purchases.append(purchase)
                
            return purchases
            
        except Exception as e:
            print(f"Error getting purchases by date range: {e}")
            return []
        finally:
            conn.close()
    
    def get_purchases_by_category(self, category: str) -> List[Purchase]:
        """
        Retrieve all purchases containing items in a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of Purchase objects containing items in the category
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        purchases = []
        
        try:
            # Find purchases with items in the given category (case-insensitive)
            cursor.execute(
                """
                SELECT DISTINCT p.* FROM purchases p
                JOIN items i ON p.id = i.purchase_id
                WHERE LOWER(i.category) LIKE ?
                """, 
                (f"%{category.lower()}%",)
            )
            purchase_rows = cursor.fetchall()
            
            for row in purchase_rows:
                # Extract purchase data
                purchase_id, merchant_name, transaction_date, total_amount, currency, payment_method, notes_json = row
                
                # Get items for this purchase
                cursor.execute("SELECT name, price, quantity, category FROM items WHERE purchase_id = ?", (purchase_id,))
                item_rows = cursor.fetchall()
                
                # Create PurchaseItem objects
                items = [
                    PurchaseItem(
                        name=item[0],
                        price=item[1],
                        quantity=item[2],
                        category=item[3]
                    )
                    for item in item_rows
                ]
                
                # Parse notes JSON if present
                notes = []
                if notes_json:
                    try:
                        notes = json.loads(notes_json)
                    except json.JSONDecodeError:
                        print(f"Error parsing notes JSON for purchase {purchase_id}")
                        
                # Create Purchase object
                purchase = Purchase(
                    id=purchase_id,
                    merchant_name=merchant_name,
                    transaction_date=transaction_date,
                    total_amount=total_amount,
                    currency=currency,
                    payment_method=payment_method,
                    notes=notes,
                    items=items
                )
                
                purchases.append(purchase)
                
            return purchases
            
        except Exception as e:
            print(f"Error getting purchases by category: {e}")
            return []
        finally:
            conn.close()
    
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a custom SQL query against the database.
        
        Args:
            query: SQL query string (must be SELECT only for safety)
            
        Returns:
            List of dictionaries with the query results
        """
        if not query.strip().lower().startswith("select"):
            raise ValueError("Only SELECT queries are allowed")
            
        conn = sqlite3.connect(self.db_path)
        # Enable column names in results
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = [dict(row) for row in rows]
            return results
            
        except Exception as e:
            print(f"Error executing query: {e}")
            raise
        finally:
            conn.close()


def create_purchase_from_receipt_data(receipt_data: Dict[str, Any]) -> Optional[Purchase]:
    """
    Create a Purchase object from receipt data extracted from an image.
    
    Args:
        receipt_data: Dictionary containing structured receipt data
        
    Returns:
        Purchase object created from the data, or None if creation fails
    """
    try:
        print(f"Creating purchase from receipt data: {json.dumps(receipt_data, indent=2)}")
        
        if not isinstance(receipt_data, dict):
            print(f"Error: receipt_data is not a dictionary, got {type(receipt_data)}")
            return None
            
        # Extract required fields
        merchant_name = receipt_data.get("merchant_name")
        transaction_date = receipt_data.get("transaction_date")
        total_amount = receipt_data.get("total_amount")
        
        print(f"Extracted fields - merchant: {merchant_name}, date: {transaction_date}, amount: {total_amount}")
        
        # Validate required fields
        missing_fields = []
        if not merchant_name:
            missing_fields.append("merchant_name")
        if not transaction_date:
            missing_fields.append("transaction_date")
        if total_amount is None:
            missing_fields.append("total_amount")
            
        if missing_fields:
            print(f"Missing required receipt data: {', '.join(missing_fields)}")
            
            # Try alternative field names
            if "store" in receipt_data and not merchant_name:
                merchant_name = receipt_data.get("store")
                print(f"Using 'store' field as merchant_name: {merchant_name}")
                
            if "date" in receipt_data and not transaction_date:
                transaction_date = receipt_data.get("date")
                print(f"Using 'date' field as transaction_date: {transaction_date}")
                
            if "total" in receipt_data and total_amount is None:
                total_amount = receipt_data.get("total")
                print(f"Using 'total' field as total_amount: {total_amount}")
                
            # Check for missing fields after trying alternatives
        missing_after_check = []
        if not merchant_name:
            missing_after_check.append("merchant_name")
        if not transaction_date:
            missing_after_check.append("transaction_date")
            # Use today's date as fallback
            import datetime
            today = datetime.date.today().strftime("%Y-%m-%d")
            transaction_date = today
            print(f"FALLBACK: Setting missing transaction date to today: {today}")
        if total_amount is None:
            missing_after_check.append("total_amount")
            
        # Only merchant and amount are truly required
        if not merchant_name or total_amount is None:
            print(f"Still missing critical fields: {', '.join(missing_after_check)}")
            return None
            
        # Add note about fallback if date was missing
        notes = []
        if "transaction_date" in missing_after_check:
            notes.append("Date could not be read from receipt; using today's date as fallback.")
        
        # Normalize transaction date format if needed
        if transaction_date:
            try:
                import datetime
                # Handle various date formats
                date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%B %d, %Y", "%d %B %Y"]
                parsed_date = None
                
                for fmt in date_formats:
                    try:
                        parsed_date = datetime.datetime.strptime(transaction_date, fmt).date()
                        break
                    except ValueError:
                        continue
                
                if parsed_date:
                    transaction_date = parsed_date.strftime("%Y-%m-%d")
                    print(f"Normalized transaction date to: {transaction_date}")
            except Exception as e:
                print(f"Error parsing date '{transaction_date}': {e}")
        
        # Extract items
        item_list = receipt_data.get("items", [])
        items = []
        
        if not item_list:
            print("Warning: No items found in receipt data")
            # Create at least one dummy item if none exist
            items = [PurchaseItem(
                name="Receipt total",
                price=float(total_amount),
                quantity=1,
                category="Other"
            )]
        else:
            print(f"Processing {len(item_list)} items")
            for i, item_data in enumerate(item_list):
                # Extract item fields
                name = item_data.get("name")
                price = item_data.get("price")
                
                if not name:
                    print(f"Item {i} missing name, skipping")
                    continue
                    
                if price is None:
                    print(f"Item {i} ({name}) missing price, skipping")
                    continue
                    
                try:
                    # Convert price to float
                    price_float = float(price)
                    
                    # Create PurchaseItem
                    item = PurchaseItem(
                        name=name,
                        price=price_float,
                        quantity=int(item_data.get("quantity", 1)),
                        category=item_data.get("category", "Other")
                    )
                    items.append(item)
                except Exception as e:
                    print(f"Error creating item {i} ({name}): {e}")
        
        # Ensure we have at least one item
        if not items:
            print("Warning: No valid items could be created, using dummy item")
            items = [PurchaseItem(
                name="Receipt total",
                price=float(total_amount),
                quantity=1,
                category="Other"
            )]
        
        # Create and return the Purchase object
        purchase = Purchase(
            merchant_name=merchant_name,
            transaction_date=transaction_date,
            total_amount=float(total_amount),
            items=items,
            currency=receipt_data.get("currency", "USD"),
            payment_method=receipt_data.get("payment_method"),
            notes=notes
        )
        
        print(f"Successfully created purchase: {purchase.merchant_name}, {purchase.transaction_date}, ${purchase.total_amount}")
        return purchase
        
    except Exception as e:
        print(f"Error creating purchase from receipt data: {e}")
        print(f"Receipt data: {receipt_data}")
        return None