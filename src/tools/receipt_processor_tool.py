"""
Tools for processing receipts and storing results in memory.
"""
from typing import Dict, Any
import datetime

from langchain.tools import BaseTool

from src.utils.memory import PurchaseMemory, Purchase, PurchaseItem, create_purchase_from_receipt_data


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
        # Process the receipt - this already minimizes API calls
        receipt_data = self._receipt_reader.process_receipt(image_path)
        
        # Store the purchase in memory using the utility function
        purchase = create_purchase_from_receipt_data(receipt_data)
        if purchase:
            # Store the purchase and print confirmation
            purchase_id = self._memory.add_purchase(purchase)
            print(f"ReceiptProcessorTool: Added purchase {purchase_id} to database")
        else:
            print("ReceiptProcessorTool: Failed to create purchase from receipt data")
        
        return receipt_data