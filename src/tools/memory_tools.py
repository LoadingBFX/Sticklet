"""
Tools for working with purchase memory.
"""
from typing import Dict, List, Any, Optional
import datetime
import json

from langchain.tools import BaseTool

from src.utils.memory import PurchaseMemory


class MemoryTool(BaseTool):
    """Tool for querying purchase memory."""
    
    name: str = "purchase_memory"
    description: str = "Query purchase history by merchant, category, date range, or get all purchases"
    
    def __init__(self, memory: PurchaseMemory, **kwargs):
        """
        Initialize the Memory Tool.
        
        Args:
            memory: The purchase memory instance
        """
        super().__init__(**kwargs)
        self._memory = memory
    
    def _run(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """
        Run the memory tool with the specified query.
        
        Args:
            query_type: Type of query to run (merchant, category, date_range, all)
            **kwargs: Additional query parameters
            
        Returns:
            Results of the query
        """
        if query_type == "merchant":
            merchant_name = kwargs.get("merchant_name")
            if not merchant_name:
                return {"error": "merchant_name parameter is required"}
                
            purchases = self._memory.get_purchases_by_merchant(merchant_name)
            return {
                "merchant_name": merchant_name,
                "purchases": [p.to_dict() for p in purchases],
                "count": len(purchases),
                "total_spent": sum(p.total_amount for p in purchases)
            }
        
        elif query_type == "category":
            category = kwargs.get("category")
            if not category:
                return {"error": "category parameter is required"}
                
            purchases = self._memory.get_purchases_by_category(category)
            return {
                "category": category,
                "purchases": [p.to_dict() for p in purchases],
                "count": len(purchases),
                "total_spent": sum(p.total_amount for p in purchases)
            }
        
        elif query_type == "date_range":
            start_date = kwargs.get("start_date")
            end_date = kwargs.get("end_date")
            
            if not start_date or not end_date:
                return {"error": "start_date and end_date parameters are required"}
                
            purchases = self._memory.get_purchases_by_date_range(start_date, end_date)
            return {
                "start_date": start_date,
                "end_date": end_date,
                "purchases": [p.to_dict() for p in purchases],
                "count": len(purchases),
                "total_spent": sum(p.total_amount for p in purchases)
            }
        
        elif query_type == "all":
            purchases = self._memory.get_all_purchases()
            return {
                "purchases": [p.to_dict() for p in purchases],
                "count": len(purchases),
                "total_spent": sum(p.total_amount for p in purchases)
            }
            
        else:
            return {"error": f"Unknown query type: {query_type}"}


class SQLQueryTool(BaseTool):
    """Tool for executing SQL queries against the purchase database."""
    
    name: str = "sql_query"
    description: str = """
    Execute SQL queries against the purchase database. Only SELECT queries are allowed.
    
    Database Schema:
    - purchases table: id, merchant_name, transaction_date, total_amount, currency, payment_method
    - items table: id, purchase_id, name, price, quantity, category
    
    Example queries:
    - To find total spent at a specific merchant: "SELECT SUM(total_amount) as total FROM purchases WHERE LOWER(merchant_name) LIKE LOWER('%Trader Joe%')"
    - To find purchases in a date range: "SELECT * FROM purchases WHERE transaction_date BETWEEN '2023-01-01' AND '2023-01-31'"
    - To find all purchases with items in a category: "SELECT DISTINCT p.* FROM purchases p JOIN items i ON p.id = i.purchase_id WHERE LOWER(i.category) = LOWER('Grocery')"
    - To get monthly spending summary: "SELECT strftime('%Y-%m', transaction_date) as month, SUM(total_amount) as total FROM purchases GROUP BY month ORDER BY month DESC"
    
    IMPORTANT: When searching for merchant names, always use LIKE with wildcards (%) to ensure partial matches, for example: 
    WHERE LOWER(merchant_name) LIKE LOWER('%Whole Foods%') instead of WHERE merchant_name = 'Whole Foods'
    """
    
    def __init__(self, memory: PurchaseMemory, **kwargs):
        """
        Initialize the SQL Query Tool.
        
        Args:
            memory: The purchase memory instance
        """
        super().__init__(**kwargs)
        self._memory = memory
    
    def _run(self, query: str) -> Dict[str, Any]:
        """
        Run an SQL query against the purchase database.
        
        Args:
            query: SQL query string (only SELECT queries are allowed)
            
        Returns:
            Results of the query
        """
        # Basic validation to ensure only SELECT queries
        if not query.strip().lower().startswith("select"):
            return {"error": "Only SELECT queries are allowed"}
        
        try:
            # Execute the query
            results = self._memory.execute_query(query)
            
            return {
                "query": query,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            return {"error": str(e)}


class InsightGeneratorTool(BaseTool):
    """Tool for generating insights from purchase history."""
    
    name: str = "insight_generator"
    description: str = "Generate financial insights based on purchase history"
    
    def __init__(self, memory: PurchaseMemory, openai_api_key: str = None, **kwargs):
        """
        Initialize the Insight Generator Tool.
        
        Args:
            memory: The purchase memory instance
            openai_api_key: OpenAI API key for generating insights
        """
        super().__init__(**kwargs)
        self._memory = memory
        self._openai_api_key = openai_api_key
    
    def _run(self, insight_type: str = "all", **kwargs) -> Dict[str, Any]:
        """
        Generate financial insights based on purchase history.
        
        Args:
            insight_type: Type of insight to generate (spending_pattern, savings_opportunity, budget_alert, all)
            **kwargs: Additional parameters
            
        Returns:
            Generated insights
        """
        # Get purchase data
        purchases = self._memory.get_all_purchases()
        
        if not purchases:
            return {"error": "No purchase data available"}
        
        # Calculate basic stats
        total_spent = sum(p.total_amount for p in purchases)
        merchant_spending = {}
        category_spending = {}
        
        for purchase in purchases:
            # Aggregate by merchant
            merchant = purchase.merchant_name
            if merchant not in merchant_spending:
                merchant_spending[merchant] = 0
            merchant_spending[merchant] += purchase.total_amount
            
            # Aggregate by category
            for item in purchase.items:
                category = item.category
                if category not in category_spending:
                    category_spending[category] = 0
                category_spending[category] += item.price * item.quantity
        
        # Sort by amount spent (descending)
        top_merchants = sorted(
            [(merchant, amount) for merchant, amount in merchant_spending.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        top_categories = sorted(
            [(category, amount) for category, amount in category_spending.items()],
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        # Get date range
        transaction_dates = [p.transaction_date for p in purchases]
        start_date = min(transaction_dates)
        end_date = max(transaction_dates)
        
        # Monthly spending
        monthly_spending = {}
        for purchase in purchases:
            month_key = purchase.transaction_date[:7]  # YYYY-MM
            if month_key not in monthly_spending:
                monthly_spending[month_key] = 0
            monthly_spending[month_key] += purchase.total_amount
        
        # Sort months chronologically
        sorted_months = sorted(monthly_spending.keys())
        
        # Generate insights
        insights = {
            "summary": {
                "total_spent": total_spent,
                "transaction_count": len(purchases),
                "date_range": f"{start_date} to {end_date}",
                "unique_merchants": len(merchant_spending),
                "unique_categories": len(category_spending)
            },
            "top_merchants": [{"merchant": m, "amount": a} for m, a in top_merchants],
            "top_categories": [{"category": c, "amount": a} for c, a in top_categories],
            "monthly_spending": [{"month": m, "amount": monthly_spending[m]} for m in sorted_months]
        }
        
        # Add specific insight types if requested
        if insight_type == "spending_pattern" or insight_type == "all":
            # Simple spending pattern analysis
            if len(sorted_months) > 1:
                changes = []
                for i in range(1, len(sorted_months)):
                    current_month = sorted_months[i]
                    prev_month = sorted_months[i-1]
                    
                    current_spend = monthly_spending[current_month]
                    prev_spend = monthly_spending[prev_month]
                    
                    if prev_spend > 0:
                        percent_change = ((current_spend - prev_spend) / prev_spend) * 100
                    else:
                        percent_change = 100
                        
                    changes.append({
                        "month": current_month,
                        "previous_month": prev_month,
                        "amount": current_spend,
                        "previous_amount": prev_spend,
                        "change_percent": round(percent_change, 2)
                    })
                
                insights["spending_pattern"] = {
                    "month_to_month_changes": changes
                }
        
        if insight_type == "savings_opportunity" or insight_type == "all":
            # Simple savings opportunities
            repeat_purchases = []
            for merchant, amount in top_merchants:
                merchant_purchases = [p for p in purchases if p.merchant_name == merchant]
                if len(merchant_purchases) > 1:
                    repeat_purchases.append({
                        "merchant": merchant,
                        "purchase_count": len(merchant_purchases),
                        "total_amount": amount,
                        "average_per_purchase": amount / len(merchant_purchases)
                    })
            
            insights["savings_opportunity"] = {
                "repeat_purchases": repeat_purchases
            }
        
        return insights