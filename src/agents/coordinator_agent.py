"""
Coordinator Agent that orchestrates other agents using LangChain.
"""
from typing import Dict, List, Any, Optional
import os
import json
import datetime
import re

from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.montly_report_agent import MonthlyReportAgent
from src.agents.receipt_reader_agent import ReceiptReaderAgent
from src.agents.market_agent import MarketAgent
from src.utils.memory import PurchaseMemory, Purchase, create_purchase_from_receipt_data
from src.tools.memory_tools import MemoryTool, InsightGeneratorTool, SQLQueryTool
from src.tools.receipt_processor_tool import ReceiptProcessorTool


class CoordinatorAgent:
    """
    Coordinator agent that orchestrates other specialized agents.
    Functions as an entry point for user interactions and delegates specialized tasks.
    Now enhanced with LangChain agents and tools for improved functionality.
    """
    
    def __init__(self, api_key: Optional[str] = None, db_path: Optional[str] = None):
        """
        Initialize the coordinator agent with OpenAI API.
        
        Args:
            api_key: Optional OpenAI API key. If not provided, will try to load from environment.
            db_path: Optional path to the SQLite database file.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Provide it directly or set OPENAI_API_KEY environment variable.")
        
        # Get database path from environment or use default
        db_path = db_path or os.environ.get("DB_PATH")
        
        # Initialize memory with SQLite
        self.memory = PurchaseMemory(db_path=db_path)
        
        # Initialize available specialized agents
        self._initialize_agents()
        
        # Set up LangChain agent
        self._setup_langchain_agent()
    
    def _initialize_agents(self):
        """Initialize the specialized agents."""
        # Dictionary of agent initializers to be called only when needed
        self.agent_initializers = {
            "receipt_reader":       lambda: self._init_receipt_reader(),
            "monthly_report":       lambda: self._init_monthly_report_agent(),
            "market":               lambda: self._init_market_agent(),
        }
        
        # Dictionary to store initialized agents
        self.agents = {}
    
    def _init_receipt_reader(self):
        """Initialize the receipt reader agent on demand."""
        return ReceiptReaderAgent()

    def _init_monthly_report_agent(self):
        """Initialize the monthly report agent on demand."""
        # pass along same API key and DB path
        return MonthlyReportAgent()

    def _init_market_agent(self):
        """Initialize the market agent on demand."""
        return MarketAgent()
    
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
        
        # Create tools with the current memory instance
        # memory_tool = MemoryTool(memory=self.memory)
        receipt_tool = ReceiptProcessorTool(receipt_reader=receipt_reader, memory=self.memory)
        insight_tool = InsightGeneratorTool(memory=self.memory, openai_api_key=self.api_key)
        sql_tool = SQLQueryTool(memory=self.memory)
        
        # self.tools = [memory_tool, receipt_tool, insight_tool, sql_tool]
        self.tools = [receipt_tool, insight_tool, sql_tool]

        # Create system message
        system_message = """
        You are Scotty's Financial Assistant, an AI designed to help users manage their receipts and finances.
        
        Your capabilities include:
        1. Reading and analyzing receipts
        2. Tracking purchase history and expenditures 
        3. Providing financial insights and recommendations
        4. Finding specific purchases when asked
        5. Running SQL queries to analyze spending data
        
        Use the tools at your disposal to help users manage their finances:
        - purchase_memory: Query the user's purchase history by merchant, category, date range, or get all purchases
        - receipt_processor: Process receipt images to extract data
        - insight_generator: Generate financial insights based on purchase history
        - sql_query: Execute SQL queries against the purchase database for detailed analysis
        
        DATABASE SCHEMA:
        - purchases table: id, merchant_name, transaction_date, total_amount, currency, payment_method
        - items table: id, purchase_id, name, price, quantity, category
        
        When users ask about their spending or purchases:
        1. For simple requests, use the purchase_memory tool
        2. For complex analysis, use the sql_query tool with appropriate SQL queries
        3. For summarizing spending patterns, use the insight_generator tool
        
        Example SQL queries for common questions:
        - "How much did I spend at Trader Joe's?" -> SELECT SUM(total_amount) FROM purchases WHERE LOWER(merchant_name) LIKE LOWER('%Trader Joe%')
        - "What groceries did I buy last month?" -> SELECT i.name, i.price, p.transaction_date FROM items i JOIN purchases p ON i.purchase_id = p.id WHERE LOWER(i.category) = 'grocery' AND p.transaction_date >= '2023-04-01' AND p.transaction_date <= '2023-04-30'
        - "What are my top spending categories?" -> SELECT i.category, SUM(i.price * i.quantity) as total FROM items i GROUP BY i.category ORDER BY total DESC
        
        Interact with users in a helpful, friendly manner. Provide accurate, specific answers.
        Be thorough in your responses and try to anticipate follow-up questions.
        Include relevant financial details and numbers in your responses.
        
        Decline requests unrelated to personal finance.
        """
        
        # Create prompt
        # OpenAI functions agent doesn't need the specific format that ReAct does
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_message),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),  # Using tuple format to avoid template issues
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
        # Get the receipt reader agent
        receipt_reader = self._get_agent("receipt_reader")
        
        # Process the receipt directly (optimized to minimize API calls)
        print("Processing receipt with receipt reader agent...")
        receipt_data = receipt_reader.process_receipt(image_path)
        
        # # Store the results in memory
        # print("Creating purchase from receipt data...")
        # purchase = create_purchase_from_receipt_data(receipt_data)
        # if purchase:
        #     # Store the purchase
        #     print(f"Storing purchase from {purchase.merchant_name} in database...")
        #     self.memory.add_purchase(purchase)
        
        return receipt_data

    def save_calibrated_receipt(self, calibrated_data: Dict[str, Any]) -> None:
        """
        Receive the complete receipt_data that has been reviewed and merged by
        the user from the original raw_result, then create a Purchase record and
        store it in the database.
        """
        purchase = create_purchase_from_receipt_data(calibrated_data)
        if purchase:
            self.memory.add_purchase(purchase)

    def delete_purchase(self, purchase_id: str) -> None:
        """
        Delete a purchase record by its ID from the purchase memory.

        Args:
            purchase_id: The unique identifier of the purchase to delete.
        """
        self.memory.delete_purchase(purchase_id)

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
        if not query or not query.strip():
            return "I'm sorry, but I didn't receive a question. Could you please try asking again?"
            
        try:
            # Check if purchase data is available
            purchases = self.memory.get_all_purchases()
            if not purchases:
                return "I don't have any purchase data to analyze yet. Please upload some receipts first so I can answer questions about your spending."
                
            # Run the query through the LangChain agent
            print(f"Processing user query: '{query}'")
            result = self.agent_executor.invoke({
                "input": query
            })
            
            output = result.get("output", "")
            if not output:
                # Fallback for empty responses
                return "I'm not sure how to answer that question. Could you try asking in a different way?"
                
            return output
                
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            return f"I encountered an error while processing your question. The error was: {str(e)}. Please try a different question or check the system logs for more details."

    def gen_monthly_report(self, month: int, year: Optional[int] = None) -> str:
        """
        Generate a bullet-pointed spending report for the given month.
        Delegates to the MonthlyReportAgent.
        """
        monthly_agent = self._get_agent("monthly_report")
        return monthly_agent.process_monthly_report(month, year)

    def get_market_indicators(self) -> Dict[str, float]:
        """
        Fetch today's latest market indicators using MarketAgent.

        Returns:
            Dict mapping tickers ('^GSPC', '^DJI', '^IXIC') to closing price.
        """
        market = self._get_agent("market")
        return market.get_current_indicators()

    def get_market_history(self) -> Dict[str, Any]:
        """
        Fetch 7-day historical index data for major US markets.

        Returns:
            Dict mapping tickers to pandas.Series of closing prices.
        """
        market = self._get_agent("market")
        return market.get_7day_history()

    def generate_daily_market_report(self) -> str:
        """
        Generate a narrative market summary for today.

        Returns:
            A descriptive paragraph summarizing today's market.
        """
        market = self._get_agent("market")
        return market.generate_daily_summary()