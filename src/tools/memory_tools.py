"""
Tools for working with memory, including purchase history.
"""
from typing import Dict, List, Any, Optional
import json

from langchain.tools import BaseTool, Tool
from langchain_core.tools import BaseTool as CoreBaseTool
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

from src.utils.memory import PurchaseMemory, Purchase, PurchaseItem


class MemoryTool(BaseTool):
    """Tool for interacting with purchase memory using LangChain's memory features."""
    
    name: str = "purchase_memory"
    description: str = "Access and query the user's purchase history"
    
    def __init__(self, memory: PurchaseMemory, **kwargs):
        """Initialize the Memory Tool with a PurchaseMemory instance."""
        super().__init__(**kwargs)
        self._memory = memory
        
    def _run(self, query_type: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Query the purchase memory.
        
        Args:
            query_type: Type of query to perform (all, merchant, category, date_range)
            **kwargs: Additional arguments for specific query types
            
        Returns:
            List of purchase records matching the query
        """
        # Use the shared memory to access purchase data if needed
        # This leverages LangChain's memory features 
        
        if query_type == "all":
            purchases = self._memory.get_all_purchases()
        elif query_type == "merchant" and "merchant_name" in kwargs:
            purchases = self._memory.get_purchases_by_merchant(kwargs["merchant_name"])
        elif query_type == "category" and "category" in kwargs:
            purchases = self._memory.get_purchases_by_category(kwargs["category"])
        elif query_type == "date_range" and "start_date" in kwargs and "end_date" in kwargs:
            purchases = self._memory.get_purchases_by_date_range(kwargs["start_date"], kwargs["end_date"])
        elif query_type == "stats":
            # Return memory statistics from LangChain memory
            return [{
                "total_purchases": len(self._memory.get_all_purchases()),
                "merchant_list": self._memory.lc_memory.memories.get("merchant_list", []),
                "category_list": self._memory.lc_memory.memories.get("category_list", []),
                "total_spent": self._memory.lc_memory.memories.get("total_spent", 0)
            }]
        else:
            return [{"error": "Invalid query type or missing required parameters"}]
            
        return [p.to_dict() for p in purchases]


class InsightGeneratorTool(BaseTool):
    """Tool for generating financial insights from purchase history using LangChain."""
    
    name: str = "insight_generator"
    description: str = "Generate financial insights based on purchase history"
    
    def __init__(self, memory: PurchaseMemory, openai_api_key: str, **kwargs):
        """Initialize the Insight Generator Tool with LangChain components."""
        super().__init__(**kwargs)
        self._memory = memory
        self._api_key = openai_api_key
        
        # Set up LangChain LLM and chains
        self._setup_langchain()
    
    def _setup_langchain(self):
        """Set up LangChain components."""
        # Initialize the LLM
        self._llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.7,
            api_key=self._api_key
        )
        
        # Create prompt templates for different insight types
        self._spending_prompt = PromptTemplate(
            input_variables=["purchase_data"],
            template="""
            You are a financial analysis assistant that provides insightful, concise, 
            and helpful analysis of spending patterns.
            
            Analyze the following purchase history and identify spending patterns:
            {purchase_data}
            
            Please provide insights on:
            1. Top spending categories
            2. Merchants with highest spending
            3. Spending trends over time
            4. Any unusual or notable spending patterns
            """
        )
        
        self._budget_prompt = PromptTemplate(
            input_variables=["purchase_data"],
            template="""
            You are a financial analysis assistant that provides insightful, concise, 
            and helpful analysis of spending patterns.
            
            Based on the following purchase history, provide budget recommendations:
            {purchase_data}
            
            Please provide:
            1. Suggested category budgets based on current spending
            2. Areas where spending could be reduced
            3. Recommended allocation of funds
            4. Savings opportunities
            """
        )
        
        self._general_prompt = PromptTemplate(
            input_variables=["purchase_data"],
            template="""
            You are a financial analysis assistant that provides insightful, concise, 
            and helpful analysis of spending patterns.
            
            Analyze the following purchase history and provide general financial insights:
            {purchase_data}
            
            Please provide helpful insights and recommendations.
            """
        )
        
        # Create chains
        self._spending_chain = LLMChain(llm=self._llm, prompt=self._spending_prompt)
        self._budget_chain = LLMChain(llm=self._llm, prompt=self._budget_prompt)
        self._general_chain = LLMChain(llm=self._llm, prompt=self._general_prompt)
        
    def _run(self, insight_type: str) -> str:
        """
        Generate financial insights using LangChain.
        
        Args:
            insight_type: Type of insight to generate (spending_patterns, budget_recommendations, etc.)
            
        Returns:
            Generated insight text
        """
        # Get purchase data from memory
        purchases = self._memory.get_all_purchases()
        purchase_data = json.dumps([p.to_dict() for p in purchases], indent=2)
        
        # Run the appropriate chain based on insight type
        if insight_type == "spending_patterns":
            return self._spending_chain.invoke({"purchase_data": purchase_data})["text"]
        elif insight_type == "budget_recommendations":
            return self._budget_chain.invoke({"purchase_data": purchase_data})["text"]
        else:
            return self._general_chain.invoke({"purchase_data": purchase_data})["text"]