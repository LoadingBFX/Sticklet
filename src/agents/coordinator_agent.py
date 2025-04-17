"""
Coordinator Agent that orchestrates other agents using LangChain.
"""
from typing import Dict, List, Any, Optional
import os
import json
import datetime
import re

from openai import OpenAI
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.receipt_reader_agent import ReceiptReaderAgent
from src.utils.memory import PurchaseMemory, Purchase, PurchaseItem
from src.tools.memory_tools import MemoryTool, InsightGeneratorTool
from src.tools.receipt_processor_tool import ReceiptProcessorTool


class CoordinatorAgent:
    """
    Coordinator agent that orchestrates other specialized agents.
    Functions as an entry point for user interactions and delegates specialized tasks.
    Now enhanced with LangChain agents and tools for improved functionality.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the coordinator agent with OpenAI API.
        
        Args:
            api_key: Optional OpenAI API key. If not provided, will try to load from environment.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide it directly or set OPENAI_API_KEY environment variable.")
        
        # Initialize memory
        self.memory = PurchaseMemory()
        
        # Initialize available specialized agents
        self._initialize_agents()
        
        # Set up LangChain agent
        self._setup_langchain_agent()
    
    def _initialize_agents(self):
        """Initialize the specialized agents."""
        # Dictionary of agent initializers to be called only when needed
        self.agent_initializers = {
            "receipt_reader": lambda: self._init_receipt_reader()
        }
        
        # Dictionary to store initialized agents
        self.agents = {}
    
    def _init_receipt_reader(self):
        """Initialize the receipt reader agent on demand."""
        return ReceiptReaderAgent()
    
    def _get_agent(self, agent_name: str):
        """Get an agent, initializing it if necessary."""
        if agent_name not in self.agents:
            if agent_name not in self.agent_initializers:
                raise ValueError(f"Unknown agent: {agent_name}")
                
            # Initialize the agent
            self.agents[agent_name] = self.agent_initializers[agent_name]()
            
        return self.agents[agent_name]
    
    def _setup_langchain_agent(self):
        """Set up the LangChain agent with tools."""
        # Initialize the LLM
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",  
            temperature=0.7,
            api_key=self.api_key
        )
        
        # Initialize receipt reader if needed
        receipt_reader = self._get_agent("receipt_reader")
        
        # Create tools
        memory_tool = MemoryTool(memory=self.memory)
        receipt_tool = ReceiptProcessorTool(receipt_reader=receipt_reader, memory=self.memory)
        insight_tool = InsightGeneratorTool(memory=self.memory, openai_api_key=self.api_key)
        
        self.tools = [memory_tool, receipt_tool, insight_tool]
        
        # Create system message
        system_message = """
        You are Scotty's Financial Assistant, an AI designed to help users manage their receipts and finances.
        
        Your capabilities include:
        1. Reading and analyzing receipts
        2. Tracking purchase history and expenditures 
        3. Providing financial insights and recommendations
        4. Finding specific purchases when asked
        
        Use the tools at your disposal to help users manage their finances:
        - purchase_memory: Query the user's purchase history
        - receipt_processor: Process receipt images to extract data
        - insight_generator: Generate financial insights based on purchase history
        
        Interact with users in a helpful, friendly manner. When users ask about their spending or purchases, 
        search through their purchase history to provide accurate, specific answers.
        
        Be thorough in your responses and try to anticipate follow-up questions.
        
        Decline requests unrelated to personal finance.
        """
        
        # Create prompt
        # OpenAI functions agent doesn't need the specific format that ReAct does
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            HumanMessage(content="{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Set up memory
        self.agent_memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True
        )
        
        # Create agent
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create agent executor
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.agent_memory,
            verbose=True,
            handle_parsing_errors=True
        )
    
    def process_receipt(self, image_path: str) -> Dict[str, Any]:
        """
        Process a receipt image using the receipt reader agent.
        
        Args:
            image_path: Path to the receipt image
            
        Returns:
            Structured receipt data
        """
        # Use the LangChain agent to process the receipt
        result = self.agent_executor.invoke({
            "input": f"Process this receipt image and extract all data: {image_path}"
        })
        
        # Get the receipt reader agent as fallback
        receipt_reader = self._get_agent("receipt_reader")
        
        # Attempt to extract receipt data from agent response
        try:
            # Check if result contains JSON data
            response_text = result.get("output", "")
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            
            if json_match:
                receipt_data = json.loads(json_match.group(1))
                return receipt_data
        except:
            # Fallback to direct processing
            pass
            
        # Use direct processing as fallback
        receipt_data = receipt_reader.process_receipt(image_path)
        
        # Store the results in memory if needed
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
            self.memory.add_purchase(purchase)
        
        return receipt_data
    
    def get_purchase_history(self, 
                            merchant_name: Optional[str] = None, 
                            category: Optional[str] = None,
                            start_date: Optional[str] = None,
                            end_date: Optional[str] = None) -> List[Purchase]:
        """
        Get purchase history filtered by various criteria.
        
        Args:
            merchant_name: Optional merchant name to filter by
            category: Optional category to filter by
            start_date: Optional start date (format: YYYY-MM-DD)
            end_date: Optional end date (format: YYYY-MM-DD)
            
        Returns:
            List of Purchase objects matching the criteria
        """
        if merchant_name:
            return self.memory.get_purchases_by_merchant(merchant_name)
        elif category:
            return self.memory.get_purchases_by_category(category)
        elif start_date and end_date:
            return self.memory.get_purchases_by_date_range(start_date, end_date)
        else:
            return self.memory.get_all_purchases()
    
    def process_query(self, query: str) -> str:
        """
        Process a natural language query using the LangChain agent.
        
        Args:
            query: User's natural language query
            
        Returns:
            Response from the agent
        """
        # Run the query through the LangChain agent
        result = self.agent_executor.invoke({
            "input": query
        })
        
        return result.get("output", "I'm sorry, I couldn't process your query.")