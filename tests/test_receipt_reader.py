"""Tests for the receipt reader agent."""
import pytest
from pathlib import Path
import os
import json
from unittest.mock import patch, MagicMock

from src.agents.receipt_reader import ReceiptReaderAgent

# Skip tests if no API key is available
requires_api_key = pytest.mark.skipif(
    not os.environ.get("MISTRAL_API_KEY"),
    reason="MISTRAL_API_KEY environment variable not set"
)

def test_receipt_reader_agent_initialization():
    """Test that the agent initializes properly."""
    # Skip if no API key available
    if not os.environ.get("MISTRAL_API_KEY"):
        pytest.skip("MISTRAL_API_KEY environment variable not set")
        
    agent = ReceiptReaderAgent()
    assert agent is not None
    assert agent.client is not None
    assert agent.ocr_model == "mistral-ocr-latest"
    assert agent.llm_model == "mistral-small-latest"
    
@requires_api_key
def test_image_encoding():
    """Test the image encoding functionality."""
    # This is a lightweight test that doesn't call the API
    agent = ReceiptReaderAgent()
    
    # Create a simple test image path - this will fail if the file doesn't exist
    # in an actual test environment, but serves as a structure for testing
    test_image_path = str(Path(__file__).parent / "test_data" / "sample_receipt.jpg")
    
    # Skip actual encoding if file doesn't exist (for CI purposes)
    if not Path(test_image_path).exists():
        pytest.skip(f"Test image {test_image_path} not found")
        
    encoded = agent._encode_image(test_image_path)
    assert isinstance(encoded, str)
    assert len(encoded) > 0

@patch('mistralai.Mistral')
def test_process_receipt_mock(mock_mistral):
    """Test the receipt processing with mocked API responses."""
    # Setup mock responses
    mock_client = MagicMock()
    mock_mistral.return_value = mock_client
    
    # Mock OCR response
    mock_ocr_response = MagicMock()
    mock_ocr_response.text = """Walmart
123 Main St
Date: 01/15/2023
Milk $3.99
Bread $2.49
Eggs $4.29
Subtotal: $10.77
Tax: $0.86
Total: $11.63
VISA ****1234"""
    mock_client.ocr.process.return_value = mock_ocr_response
    
    # Mock Chat response
    mock_message = MagicMock()
    mock_message.content = """```json
{
  "store": "Walmart",
  "date": "01/15/2023",
  "total": 11.63,
  "currency": "USD",
  "items": [
    {"name": "Milk", "price": 3.99},
    {"name": "Bread", "price": 2.49},
    {"name": "Eggs", "price": 4.29}
  ],
  "tax": 0.86,
  "payment_method": "VISA"
}
```"""
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_chat_response = MagicMock()
    mock_chat_response.choices = [mock_choice]
    mock_client.chat.complete.return_value = mock_chat_response
    
    # Create agent with mocked client
    agent = ReceiptReaderAgent(api_key="fake_api_key")
    
    # Test with a non-existent path (it will be mocked)
    result = agent.process_receipt("fake_path.jpg")
    
    # Verify the result has the right structure
    assert result["store"] == "Walmart"
    assert result["date"] == "01/15/2023"
    assert result["total"] == 11.63
    assert len(result["items"]) == 3
    assert result["tax"] == 0.86
    assert result["payment_method"] == "VISA"
