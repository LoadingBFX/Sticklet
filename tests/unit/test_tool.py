"""
Tests for tool functionality.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

from src.tools.receipt_tools import MistralOCRTool, ReceiptParserTool
from src.utils.memory import PurchaseMemory
from src.tools.memory_tools import MemoryTool, InsightGeneratorTool

# Skip tests if no API keys are available
requires_mistral_api_key = pytest.mark.skipif(
    not os.environ.get("MISTRAL_API_KEY"),
    reason="MISTRAL_API_KEY environment variable not set"
)

requires_openai_api_key = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY environment variable not set"
)

@pytest.fixture(scope="module", autouse=True)
def load_env():
    """Load environment variables before tests."""
    load_dotenv()

@requires_mistral_api_key
def test_mistral_ocr_tool_initialization():
    """Test that the MistralOCRTool initializes properly."""
    tool = MistralOCRTool()
    assert tool is not None
    assert tool.name == "mistral_ocr"
    assert "extract text from receipt images" in tool.description.lower()

@requires_mistral_api_key
def test_receipt_parser_tool_initialization():
    """Test that the ReceiptParserTool initializes properly."""
    tool = ReceiptParserTool()
    assert tool is not None
    assert tool.name == "receipt_parser"
    assert "parse text" in tool.description.lower()

def test_memory_tool_functionality():
    """Test the MemoryTool functionality with sample data."""
    # Create a memory instance with test data
    memory = PurchaseMemory()
    
    # Create the memory tool
    memory_tool = MemoryTool(memory=memory)
    
    # Test basic functionality
    assert memory_tool.name == "purchase_memory"
    assert "purchase history" in memory_tool.description.lower()
    
    # Test query functionality
    all_purchases = memory_tool._run("all")
    assert isinstance(all_purchases, list)
    assert len(all_purchases) > 0
    
    # Test stats functionality
    stats = memory_tool._run("stats")
    assert isinstance(stats, list)
    assert len(stats) == 1
    assert "total_purchases" in stats[0]
    assert "merchant_list" in stats[0]
    assert "category_list" in stats[0]

@requires_openai_api_key
def test_insight_generator_tool():
    """Test the InsightGeneratorTool with mocks."""
    memory = PurchaseMemory()
    
    with patch('langchain_openai.ChatOpenAI') as mock_chat:
        with patch('langchain.chains.LLMChain') as mock_chain:
            # Setup mock responses
            mock_chain_instance = MagicMock()
            mock_chain.return_value = mock_chain_instance
            mock_chain_instance.invoke.return_value = {"text": "Sample insight text"}
            
            # Create tool
            tool = InsightGeneratorTool(memory=memory, openai_api_key="fake_key")
            
            # Test the tool
            result = tool._run("spending_patterns")
            assert result == "Sample insight text"