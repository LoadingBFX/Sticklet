"""
Tools for processing receipts and storing results in memory.
"""
from typing import Dict, Any
import datetime

from langchain.tools import BaseTool

from src.utils.memory import PurchaseMemory, Purchase, PurchaseItem


class ReceiptProcessorTool(BaseTool):
    """Tool for processing receipts and saving the result to memory."""
    
    name: str = "receipt_processor"
    description: str = "Process a receipt image to extract structured data and store in memory"
    
    def __init__(self, receipt_reader, memory: PurchaseMemory, **kwargs):
        """
        Initialize the Receipt Processor Tool.
        
        Args:
            receipt_reader: The receipt reader agent instance
            memory: The purchase memory instance for storing results
        """
        super().__init__(**kwargs)
        self._receipt_reader = receipt_reader
        self._memory = memory
        
    def _run(self, image_path: str) -> Dict[str, Any]:
        """
        Process a receipt image and store the results in memory.
        
        Args:
            image_path: Path to the receipt image file
            
        Returns:
            Structured data extracted from the receipt
        """
        # Process the receipt
        receipt_data = self._receipt_reader.process_receipt(image_path)
        
        # Store the purchase in memory
        if "merchant_name" in receipt_data and "total_amount" in receipt_data:
            # Create PurchaseItem objects
            items = []
            for item_data in receipt_data.get("items", []):
                item = PurchaseItem(
                    name=item_data.get("name", "Unknown Item"),
                    price=float(item_data.get("price", 0.0)),
                    quantity=int(item_data.get("quantity", 1)),
                    category=item_data.get("category", "Other")
                )
                items.append(item)
            
            # Create Purchase object
            purchase = Purchase(
                merchant_name=receipt_data.get("merchant_name"),
                transaction_date=receipt_data.get("transaction_date", datetime.datetime.now().strftime("%Y-%m-%d")),
                total_amount=float(receipt_data.get("total_amount", 0.0)),
                currency=receipt_data.get("currency", "USD"),
                payment_method=receipt_data.get("payment_method"),
                items=items
            )
            
            # Store the purchase
            self._memory.add_purchase(purchase)
        
        return receipt_data