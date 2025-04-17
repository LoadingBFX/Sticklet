"""
Tests for agent initialization.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

from src.agents import ReceiptReaderAgent, CoordinatorAgent

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
def test_receipt_reader_agent_initialization():
    """Test that the ReceiptReaderAgent initializes properly."""
    agent = ReceiptReaderAgent()
    assert agent is not None
    assert agent.client is not None
    assert agent.ocr_model == "mistral-ocr-latest"
    assert agent.llm_model == "mistral-large-latest"
    assert hasattr(agent, "agent_executor")
    assert len(agent.tools) == 2

@requires_openai_api_key
def test_coordinator_agent_initialization():
    """Test that the CoordinatorAgent initializes properly."""
    agent = CoordinatorAgent()
    assert agent is not None
    assert agent.api_key is not None
    assert hasattr(agent, "memory")
    assert hasattr(agent, "agent_executor")
    assert len(agent.tools) == 3

@patch('src.agents.receipt_reader_agent.Mistral')
@patch('src.agents.receipt_reader_agent.ChatMistralAI')
@patch('src.agents.receipt_reader_agent.AgentExecutor')
def test_receipt_reader_agent_mock(mock_agent_executor, mock_langchain_mistral, mock_mistral):
    """Test the ReceiptReaderAgent initialization with mocks."""
    # Setup mock responses
    mock_client = MagicMock()
    mock_mistral.return_value = mock_client
    
    # Mock LangChain components
    mock_agent_instance = MagicMock()
    mock_agent_executor.return_value = mock_agent_instance
    
    # Create agent with mocked client
    agent = ReceiptReaderAgent(api_key="fake_api_key")
    
    # Verify mocks were called
    mock_mistral.assert_called_once_with(api_key="fake_api_key")
    mock_langchain_mistral.assert_called_once()
    mock_agent_executor.assert_called_once()