from typing import Dict, Any, Optional
import os
import json
import base64
from pathlib import Path
from io import BytesIO
import re

from mistralai import Mistral
from mistralai.client import MistralClient
from mistralai.models import File

class ReceiptReaderAgent:
    """
    Agent for reading and extracting structured data from receipts using Mistral API.
    Implements the Tool Use pattern by leveraging Mistral's OCR and vision capabilities.
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
        
        self.client = Mistral(api_key=self.api_key)
        self.ocr_model = "mistral-ocr-latest"
        self.llm_model = "mistral-large-latest"
        
        self.system_prompt = """
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

    
    def _encode_image(self, image_path: str) -> str:
        """
        Encode an image file to base64 string.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Base64 encoded string of the image
        """
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
          
            
    def process_receipt(self, image_path: str) -> Dict[str, Any]:
        """
        Process a receipt image and extract structured data using Mistral's OCR and LLM.
        
        Args:
            image_path: Path to the receipt image file
            
        Returns:
            Dictionary containing extracted receipt information
        """
        # Step 1: Use Mistral OCR to process the image
        try:
            ocr_response = self.client.ocr.process(
                model=self.ocr_model,
                include_image_base64 = True,
                document={
                    "type": "image_url",
                    "image_url": f"data:image/jpeg;base64,{self._encode_image(image_path)}"
                }
            )
            
            # Extract the OCR text content
            ocr_text = ocr_response.pages[0].markdown
            print(f"OCR text: {ocr_text}")
            
            # Check if OCR only returned an image reference without text extraction
            if ocr_text.startswith("![") and "](" in ocr_text and not any(c.isalpha() or c.isdigit() for c in ocr_text if c not in "![]()" and not c.isspace()):
                print("OCR only returned image reference. Using chat completion for text extraction instead.")
                
                
                with open(image_path, "rb") as f:
                    file_content = f.read()
                
                uploaded_file = self.client.files.upload(
                    file=File(
                        file_name=os.path.basename(image_path),
                        content=file_content,
                    ),
                    purpose="multimodal"
                )
                
                # Get signed URL
                signed_url = self.client.files.get_signed_url(file_id=uploaded_file.id)
                
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
                
                extraction_response = self.client.chat.complete(
                    model=self.llm_model,  # Using the LLM model here
                    messages=extraction_messages,
                )
                
                # Replace OCR text with extracted text
                ocr_text = extraction_response.choices[0].message.content
                print(f"Extracted text using chat completion: {ocr_text}")
            
            # Step 2: Use Mistral chat model to extract structured data from OCR text
            messages = [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": f"Here is the OCR text from a receipt. Extract the requested information:\n\n{ocr_text}"
                }
            ]
            
            chat_response = self.client.chat.complete(
                model=self.llm_model,
                messages=messages
            )
            
            # Extract and parse the response
            response_text = chat_response.choices[0].message.content
            
            # Find JSON in the response (in case there's additional text)
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response_text
                
            # Try to clean up the string to make it valid JSON
            # Remove any non-JSON parts at beginning and end
            json_str = re.sub(r'^[^{]*', '', json_str)
            json_str = re.sub(r'[^}]*$', '', json_str)
            
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                return {"raw_text": response_text, "ocr_text": ocr_text}
            
        except Exception as e:
            print(f"Error processing receipt: {e}")
            return {"error": str(e)}