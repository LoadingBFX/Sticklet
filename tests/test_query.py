#!/usr/bin/env python
"""
Script to test SQL queries through the CoordinatorAgent.
"""
import os
from dotenv import load_dotenv
from src.agents.coordinator_agent import CoordinatorAgent

# Load environment variables
load_dotenv()

def main():
    print("Testing SQL Query Tool with CoordinatorAgent")
    
    # Initialize coordinator agent
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        return
        
    try:
        # Initialize the coordinator agent
        coordinator = CoordinatorAgent(api_key=api_key)
        print("Coordinator agent initialized successfully")
        
        # Get purchase count
        purchases = coordinator.memory.get_all_purchases()
        print(f"Found {len(purchases)} purchases in database")
        
        # Test SQL query through process_query
        print("\nTesting SQL query through process_query:")
        test_query = "How much did I spend at Whole Foods Market?"
        print(f"Query: {test_query}")
        
        response = coordinator.process_query(test_query)
        print(f"Response: {response}")
        
        print("\nTesting another SQL query:")
        test_query = "Show me my purchases for groceries"
        print(f"Query: {test_query}")
        
        response = coordinator.process_query(test_query)
        print(f"Response: {response}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()