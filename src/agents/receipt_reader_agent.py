"""
Receipt Reader Agent that uses LangChain to extract data from receipts.
"""
import base64
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple

from langchain.agents import AgentExecutor, create_react_agent
from langchain.memory import ConversationBufferMemory
from langchain_mistralai import ChatMistralAI
from mistralai import Mistral

from src.tools.receipt_tools import MistralOCRTool, ReceiptParserTool


class ReceiptReaderAgent:
    """
    Agent for reading and extracting structured data from receipts using Mistral API.
    Implements the Tool Use pattern by leveraging Mistral's OCR and vision capabilities.
    Now enhanced with LangChain for improved agent capabilities and tool usage.
    Implements the Reflection pattern to validate and refine extraction results.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the receipt reader agent with the Mistral API.
        
        Args:
            api_key: Optional Mistral API key. If not provided, will try to load from environment.
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Mistral API key is required. Provide it directly or set MISTRAL_API_KEY environment variable.")
        
        # Direct Mistral client for potential fallback
        self.client = Mistral(api_key=self.api_key)
        self.ocr_model = "mistral-ocr-latest"
        self.llm_model = "mistral-large-latest"
        
        # Initialize tools directly
        self.ocr_tool = MistralOCRTool(api_key=self.api_key)
        self.parser_tool = ReceiptParserTool(api_key=self.api_key)
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file as a base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64-encoded image
        """
        from src.utils.image_utils import encode_image_to_base64
        
        with open(image_path, "rb") as image_file:
            return encode_image_to_base64(image_file.read())
        
    def process_receipt(self, image_path: str) -> Dict[str, Any]:
        """
        Process a receipt image and extract structured data.
        Optimized to minimize API calls by doing a single OCR call and a single parse call.
        
        Args:
            image_path: Path to the receipt image file
            
        Returns:
            Dictionary containing extracted receipt information
        """
        try:
            # Step 1: Perform OCR once
            print("Performing OCR on receipt image...")
            ocr_text = self.ocr_tool._run(image_path)
            
            if "Error performing OCR" in ocr_text:
                return {"error": ocr_text}
            
            # Step 2: Parse the OCR text once
            print("Parsing receipt text...")
            parsed_data = self.parser_tool._run(ocr_text)
            
            # Store the OCR text in the parsed data for reference
            if isinstance(parsed_data, dict) and "ocr_text" not in parsed_data:
                parsed_data["ocr_text"] = ocr_text
            
            # Step 3: Normalize field names if needed
            normalized_data = self._normalize_field_names(parsed_data)
            
            # Step 4: Reflect on and validate the results
            print("Validating extracted data...")
            validated_data = self._reflect_on_results(normalized_data)
            
            return validated_data
            
        except Exception as e:
            print(f"Error processing receipt: {e}")
            return {"error": str(e)}
    
    def _normalize_field_names(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize field names to ensure consistent naming across the application.
        
        Args:
            data: Dictionary containing parsed receipt data
            
        Returns:
            Dictionary with normalized field names
        """
        normalized = data.copy()
        
        # Normalize common field name variations
        if "store" in normalized and "merchant_name" not in normalized:
            normalized["merchant_name"] = normalized["store"]
            
        if "date" in normalized and "transaction_date" not in normalized:
            normalized["transaction_date"] = normalized["date"]
            
        if "total" in normalized and "total_amount" not in normalized:
            normalized["total_amount"] = normalized["total"]
            
        return normalized
            
    def _reflect_on_results(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Implement the Reflection pattern to validate and potentially correct extracted data.
        
        Args:
            data: The extracted receipt data to validate
            
        Returns:
            Validated and potentially corrected receipt data
        """
        # Clone the data to avoid modifying the original
        validated = data.copy()
        
        # Common validation issues to check
        invalid_merchant_names = ["receipt", "groceries", "store", "supermarket", "market", "receipt data", "unknown"]
        
        # 1. Validate merchant name
        if "merchant_name" in validated:
            merchant = validated["merchant_name"]
            
            # Check if merchant name is too generic
            if merchant and merchant.lower() in invalid_merchant_names:
                # Try to find more specific merchant name in the ocr text
                if "ocr_text" in validated:
                    # Use the LLM to analyze the raw text for a better merchant name
                    messages = [
                        {
                            "role": "system",
                            "content": "You are a receipt analysis specialist. Extract the most likely merchant/store name from this receipt text."
                        },
                        {
                            "role": "user",
                            "content": f"Current extraction gave generic name '{merchant}'. Analyze this text to find the actual store name:\n\n{validated['ocr_text']}"
                        }
                    ]
                    
                    try:
                        response = self.client.chat.complete(
                            model=self.llm_model,
                            messages=messages
                        )
                        better_merchant = response.choices[0].message.content.strip()
                        
                        # Only update if it found something more specific
                        if better_merchant and better_merchant.lower() not in invalid_merchant_names:
                            validated["merchant_name"] = better_merchant
                            print(f"Reflection: Updated generic merchant name '{merchant}' to '{better_merchant}'")
                    except Exception as e:
                        print(f"Error during merchant name reflection: {e}")
        
        # 2. Validate transaction date
        if "transaction_date" in validated:
            date_str = validated["transaction_date"]
            
            # Basic format validation
            if isinstance(date_str, str):
                try:
                    # Try to parse the date
                    import datetime
                    
                    # Handle various date formats
                    date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]
                    parsed_date = None
                    
                    for fmt in date_formats:
                        try:
                            parsed_date = datetime.datetime.strptime(date_str, fmt).date()
                            break
                        except ValueError:
                            continue
                    
                    # Check if the date is in the future
                    if parsed_date and parsed_date > datetime.date.today():
                        # Replace with today's date
                        validated["transaction_date"] = datetime.date.today().strftime("%Y-%m-%d")
                        print(f"Reflection: Corrected future date to today's date")
                        
                    # If valid date but wrong format, standardize to YYYY-MM-DD
                    elif parsed_date:
                        validated["transaction_date"] = parsed_date.strftime("%Y-%m-%d")
                except Exception:
                    # If date can't be parsed, leave as is
                    pass
        
        # 3. Check item categories for reasonableness
        if "items" in validated and isinstance(validated["items"], list):
            for item in validated["items"]:
                if "name" in item and "category" in item:
                    item_name = item["name"].lower()
                    category = item["category"]
                    
                    # Basic category validation (can be expanded with more rules)
                    food_keywords = ["milk", "bread", "cheese", "beef", "chicken", "fish", "vegetable", "fruit"]
                    if any(keyword in item_name for keyword in food_keywords) and category not in ["Grocery", "Restaurant"]:
                        item["category"] = "Grocery"
                        print(f"Reflection: Updated category for {item_name} to Grocery")
        
        return validated