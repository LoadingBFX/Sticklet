"""
Tools for working with receipts, including OCR and parsing.
"""
from typing import Dict, Any, Optional
import os
import base64
import json
import re

from mistralai import Mistral
from mistralai.models import File
from langchain.tools import BaseTool

class MistralOCRTool(BaseTool):
    """Tool for performing OCR on images using Mistral API."""
    
    name: str = "mistral_ocr"
    description: str = "Extract text from a receipt image using Mistral's OCR capabilities."
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize the Mistral OCR Tool."""
        super().__init__(**kwargs)
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self._api_key:
            raise ValueError("Mistral API key is required. Provide it directly or set MISTRAL_API_KEY environment variable.")
        
        self._client = Mistral(api_key=self._api_key)
        self._ocr_model = "mistral-ocr-latest"
        self._llm_model = "mistral-large-latest"
    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string of the image
        """
        from src.utils.image_utils import encode_image_to_base64
        
        with open(image_path, "rb") as image_file:
            return encode_image_to_base64(image_file.read())
    
    def _run(self, image_path: str) -> str:
        """
        Run the OCR tool on an image.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Extracted text from the image
        """
        try:
            # Try OCR first
            ocr_response = self._client.ocr.process(
                model=self._ocr_model,
                include_image_base64=True,
                document={
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{self._encode_image(image_path)}"
                }
            )
            
            # Extract the OCR text content
            ocr_text = ocr_response.pages[0].markdown
            
            # Check if OCR only returned an image reference without text extraction
            if ocr_text.startswith("![") and "](" in ocr_text and not any(c.isalpha() or c.isdigit() for c in ocr_text if c not in "![]()" and not c.isspace()):
                # Fallback to chat completion for text extraction
                with open(image_path, "rb") as f:
                    file_content = f.read()
                
                uploaded_file = self._client.files.upload(
                    file=File(
                        file_name=os.path.basename(image_path),
                        content=file_content,
                    ),
                    purpose="multimodal"
                )
                
                # Get signed URL
                signed_url = self._client.files.get_signed_url(file_id=uploaded_file.id)
                
                # Use chat completion to extract text
                extraction_messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract all the text from this receipt image and format it as plain text."
                            },
                            {
                                "type": "document_url",
                                "document_url": signed_url.url
                            }
                        ]
                    }
                ]
                
                extraction_response = self._client.chat.complete(
                    model=self._llm_model,
                    messages=extraction_messages,
                )
                
                # Replace OCR text with extracted text
                ocr_text = extraction_response.choices[0].message.content
            
            return ocr_text
            
        except Exception as e:
            return f"Error performing OCR: {str(e)}"


class ReceiptParserTool(BaseTool):
    """Tool for parsing receipt text into structured data."""
    
    name: str = "receipt_parser"
    description: str = "Parse receipt text into structured data with merchant, items, prices, etc."
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize the Receipt Parser Tool."""
        super().__init__(**kwargs)
        self._api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self._api_key:
            raise ValueError("Mistral API key is required. Provide it directly or set MISTRAL_API_KEY environment variable.")
        
        self._client = Mistral(api_key=self._api_key)
        self._llm_model = "mistral-large-latest"
        
        self._system_prompt = """
        You are a sophisticated financial receipt analyzer. Extract and structure the following data from receipt text:

        REQUIRED (use null if not found):
        - merchant_name: The business name where purchase occurred
        - transaction_date: Format as YYYY-MM-DD when possible
        - total_amount: The final amount paid (numeric value only)
        - currency: Three-letter currency code (USD, EUR, etc.)
        - items: Array of objects containing:
            * name: Item description as it appears on receipt
            * price: Individual item price (numeric value only)
            * quantity: Number of units if specified (default to 1)
            * category: Classify into one of these categories: "Grocery", "Restaurant", "Electronics", "Clothing", "Healthcare", "Office", "Transportation", "Entertainment", "Household", or "Other"
        - tax_information: Object containing:
            * sales_tax: Total sales tax amount (numeric value only)
            * tax_rate: Percentage if available (numeric value only)
        - payment_method: Card type or payment method used

        PROCESSING RULES:
        1. Remove any special characters from prices before converting to numbers
        2. Standardize item names (capitalize first letter, remove unnecessary spaces)
        3. For ambiguous items, use the most likely category based on context
        4. When multiple tax values exist, prioritize those labeled as "Sales Tax" or "VAT"
        5. When receipt contains both pre-tax and post-tax totals, use the final post-tax amount

        Respond with a clean, properly formatted JSON object containing all extracted fields. Use "null" (not empty strings) for any information that cannot be reliably determined.
        """
    
    def _run(self, receipt_text: str) -> Dict[str, Any]:
        """
        Run the receipt parser on extracted text.
        
        Args:
            receipt_text: Text extracted from a receipt image
            
        Returns:
            Structured data extracted from the receipt
        """
        try:
            print(f"Parsing receipt text ({len(receipt_text)} chars)")
            
            # Send to Mistral for structured extraction
            messages = [
                {
                    "role": "system",
                    "content": self._system_prompt
                },
                {
                    "role": "user",
                    "content": f"Here is the OCR text from a receipt. Extract the requested information:\n\n{receipt_text}"
                }
            ]
            
            chat_response = self._client.chat.complete(
                model=self._llm_model,
                messages=messages
            )
            
            # Extract and parse the response
            response_text = chat_response.choices[0].message.content
            
            # Find JSON in the response (in case there's additional text)
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                print("Found JSON code block in response")
                json_str = json_match.group(1)
            else:
                print("No JSON code block found, using entire response")
                json_str = response_text
                
            # Clean up the string to make it valid JSON
            json_str = re.sub(r'^[^{]*', '', json_str)
            json_str = re.sub(r'[^}]*$', '', json_str)
            
            try:
                parsed_data = json.loads(json_str)
                
                # Always include the OCR text in the parsed data
                parsed_data["ocr_text"] = receipt_text
                
                print(f"Successfully parsed receipt data with fields: {', '.join(sorted(parsed_data.keys()))}")
                return parsed_data
            except json.JSONDecodeError as e:
                print(f"JSON decode error: {e}")
                return {
                    "error": f"Failed to parse JSON: {e}",
                    "raw_text": response_text, 
                    "ocr_text": receipt_text
                }
            
        except Exception as e:
            print(f"Error in receipt parser: {e}")
            return {"error": str(e), "ocr_text": receipt_text}