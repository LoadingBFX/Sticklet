from typing import Dict, List, Any, Optional
import json
import os
from pathlib import Path
import datetime
from dataclasses import dataclass, asdict, field

from langchain.memory import ReadOnlySharedMemory, SimpleMemory

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
    id: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        result = asdict(self)
        # Convert PurchaseItem objects to dictionaries
        result["items"] = [item.to_dict() for item in self.items]
        return result


class PurchaseMemory:
    """
    Memory component for storing purchase history.
    Implements the Memory Pattern by persisting purchase data and providing retrieval capabilities.
    Uses LangChain's SimpleMemory for storing data in a format compatible with LangChain agents.
    """
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize the purchase memory.
        
        Args:
            storage_dir: Optional directory path where purchase data will be stored.
                         If None, a default directory will be used.
        """
        if storage_dir is None:
            # Create a default storage directory in the project root
            storage_dir = Path(__file__).parent.parent.parent / "data"
        
        self.storage_dir = Path(storage_dir)
        self.storage_path = self.storage_dir / "purchases.json"
        
        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize LangChain memory
        self._init_langchain_memory()
        
        # Initialize with dummy data if the file doesn't exist
        if not self.storage_path.exists():
            self._initialize_with_dummy_data()
    
    def _init_langchain_memory(self):
        """Initialize LangChain memory with our purchase data."""
        # Create SimpleMemory instance
        self.lc_memory = SimpleMemory()
        
        # Create ReadOnlySharedMemory wrapper for tools to access
        self.lc_shared_memory = ReadOnlySharedMemory(memory=self.lc_memory)
        
        # Load existing purchases
        self._refresh_langchain_memory()
    
    def _refresh_langchain_memory(self):
        """Refresh the LangChain memory with latest purchase data."""
        # Get all purchases
        purchases = self.get_all_purchases()
        purchase_dicts = [p.to_dict() for p in purchases]
        
        # Update memory
        self.lc_memory.memories["purchases"] = purchase_dicts
        
        # Update additional statistics and metadata for easy access
        merchants = list(set(p.merchant_name for p in purchases))
        categories = list(set(item.category for p in purchases for item in p.items))
        total_spent = sum(p.total_amount for p in purchases)
        
        self.lc_memory.memories["merchant_list"] = merchants
        self.lc_memory.memories["category_list"] = categories
        self.lc_memory.memories["total_spent"] = total_spent
    
    def _initialize_with_dummy_data(self):
        """Initialize the storage with dummy purchase data."""
        dummy_purchases = [
            Purchase(
                merchant_name="Whole Foods Market",
                transaction_date="2024-04-12",
                total_amount=78.45,
                currency="USD",
                payment_method="VISA",
                items=[
                    PurchaseItem(name="Organic Bananas", price=3.99, quantity=1, category="Grocery"),
                    PurchaseItem(name="Greek Yogurt", price=5.49, quantity=2, category="Grocery"),
                    PurchaseItem(name="Avocado", price=1.99, quantity=3, category="Grocery"),
                    PurchaseItem(name="Chicken Breast", price=12.99, quantity=1, category="Grocery"),
                    PurchaseItem(name="Sparkling Water", price=4.99, quantity=2, category="Grocery")
                ]
            ),
            Purchase(
                merchant_name="Target",
                transaction_date="2024-04-10",
                total_amount=152.67,
                currency="USD",
                payment_method="MASTERCARD",
                items=[
                    PurchaseItem(name="T-Shirt", price=19.99, quantity=2, category="Clothing"),
                    PurchaseItem(name="Household Cleaner", price=4.99, quantity=1, category="Household"),
                    PurchaseItem(name="Paper Towels", price=9.99, quantity=1, category="Household"),
                    PurchaseItem(name="USB Cable", price=12.99, quantity=1, category="Electronics"),
                    PurchaseItem(name="Snack Bars", price=4.99, quantity=3, category="Grocery")
                ]
            ),
            Purchase(
                merchant_name="Home Depot",
                transaction_date="2024-04-05",
                total_amount=87.32,
                currency="USD",
                payment_method="AMEX",
                items=[
                    PurchaseItem(name="Plant Pot", price=12.99, quantity=2, category="Household"),
                    PurchaseItem(name="Potting Soil", price=7.99, quantity=1, category="Household"),
                    PurchaseItem(name="Light Bulbs", price=15.99, quantity=1, category="Household"),
                    PurchaseItem(name="Tool Set", price=29.99, quantity=1, category="Household")
                ]
            ),
            Purchase(
                merchant_name="Chipotle",
                transaction_date="2024-04-02",
                total_amount=22.45,
                currency="USD",
                payment_method="VISA",
                items=[
                    PurchaseItem(name="Burrito Bowl", price=11.95, quantity=1, category="Restaurant"),
                    PurchaseItem(name="Chips & Guacamole", price=4.75, quantity=1, category="Restaurant"),
                    PurchaseItem(name="Soft Drink", price=2.95, quantity=1, category="Restaurant")
                ]
            ),
            Purchase(
                merchant_name="Amazon",
                transaction_date="2024-03-28",
                total_amount=67.94,
                currency="USD",
                payment_method="VISA",
                items=[
                    PurchaseItem(name="Wireless Earbuds", price=49.99, quantity=1, category="Electronics"),
                    PurchaseItem(name="Phone Case", price=17.95, quantity=1, category="Electronics")
                ]
            )
        ]
        
        # Save dummy data
        self.save_purchases(dummy_purchases)
    
    def save_purchases(self, purchases: List[Purchase]):
        """
        Save the list of purchases to storage.
        
        Args:
            purchases: List of Purchase objects to save
        """
        # Convert Purchase objects to dictionaries
        purchase_dicts = [purchase.to_dict() for purchase in purchases]
        
        # Write to file
        with open(self.storage_path, 'w') as f:
            json.dump(purchase_dicts, f, indent=2)
        
        # Update LangChain memory
        self._refresh_langchain_memory()
    
    def add_purchase(self, purchase: Purchase):
        """
        Add a new purchase to the memory.
        
        Args:
            purchase: Purchase object to add
        """
        # Load existing purchases
        purchases = self.get_all_purchases()
        
        # Add new purchase
        purchases.append(purchase)
        
        # Save updated list
        self.save_purchases(purchases)
        
        return purchase.id
    
    def get_all_purchases(self) -> List[Purchase]:
        """
        Retrieve all purchases from memory.
        
        Returns:
            List of Purchase objects
        """
        if not self.storage_path.exists():
            return []
        
        try:
            with open(self.storage_path, 'r') as f:
                purchase_dicts = json.load(f)
                
            # Convert dictionaries back to Purchase objects
            purchases = []
            for p_dict in purchase_dicts:
                # Convert item dictionaries to PurchaseItem objects
                items = [
                    PurchaseItem(
                        name=item["name"],
                        price=item["price"],
                        quantity=item["quantity"],
                        category=item["category"]
                    )
                    for item in p_dict["items"]
                ]
                
                purchase = Purchase(
                    merchant_name=p_dict["merchant_name"],
                    transaction_date=p_dict["transaction_date"],
                    total_amount=p_dict["total_amount"],
                    currency=p_dict["currency"],
                    payment_method=p_dict.get("payment_method"),
                    items=items,
                    id=p_dict.get("id", datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
                )
                purchases.append(purchase)
                
            return purchases
        except Exception as e:
            print(f"Error loading purchases: {e}")
            return []
    
    def get_purchases_by_merchant(self, merchant_name: str) -> List[Purchase]:
        """
        Retrieve all purchases from a specific merchant.
        
        Args:
            merchant_name: Name of the merchant to filter by
            
        Returns:
            List of Purchase objects matching the merchant name
        """
        all_purchases = self.get_all_purchases()
        return [p for p in all_purchases if p.merchant_name.lower() == merchant_name.lower()]
    
    def get_purchases_by_date_range(self, start_date: str, end_date: str) -> List[Purchase]:
        """
        Retrieve all purchases within a date range.
        
        Args:
            start_date: Start date in format YYYY-MM-DD
            end_date: End date in format YYYY-MM-DD
            
        Returns:
            List of Purchase objects within the date range
        """
        all_purchases = self.get_all_purchases()
        return [p for p in all_purchases if start_date <= p.transaction_date <= end_date]
    
    def get_purchases_by_category(self, category: str) -> List[Purchase]:
        """
        Retrieve all purchases containing items in a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of Purchase objects containing items in the category
        """
        all_purchases = self.get_all_purchases()
        result = []
        
        for purchase in all_purchases:
            # Check if any item in the purchase matches the category
            if any(item.category.lower() == category.lower() for item in purchase.items):
                result.append(purchase)
                
        return result