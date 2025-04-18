import streamlit as st
from pathlib import Path
import tempfile
import os
import json

from dotenv import load_dotenv
from src.agents import CoordinatorAgent
from src.utils.image_utils import validate_image, resize_image_if_needed

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Financial Assistant",
    page_icon="💰",
    layout="wide"
)

def initialize_coordinator_agent():
    """Initialize the coordinator agent, handling API key setup."""
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    mistral_api_key = os.environ.get("MISTRAL_API_KEY")
    db_path = os.environ.get("DB_PATH")
    
    if not openai_api_key:
        st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
        st.stop()
    
    if not mistral_api_key:
        st.error("Mistral API key not found. Please set the MISTRAL_API_KEY environment variable.")
        st.stop()
    
    try:
        return CoordinatorAgent(api_key=openai_api_key, db_path=db_path)
    except Exception as e:
        st.error(f"Error initializing coordinator agent: {e}")
        st.stop()

def format_receipt_results(result):
    """Format the receipt results for display."""
    if "error" in result:
        return f"Error: {result['error']}"
    
    if "raw_text" in result:
        return f"```\n{result['raw_text']}\n```"
    
    # Display formatted receipt information
    receipt_html = f"""
    <h3>Receipt Details</h3>
    <p><strong>Merchant:</strong> {result.get('merchant_name', 'Unknown')}</p>
    <p><strong>Date:</strong> {result.get('transaction_date', 'Unknown')}</p>
    <p><strong>Total:</strong> {result.get('currency', '$')}{result.get('total_amount', 0)}</p>
    """
    
    # Add items if available
    items = result.get('items', [])
    if items:
        receipt_html += "<h4>Items</h4><ul>"
        for item in items:
            receipt_html += f"<li>{item.get('name', 'Item')}: {result.get('currency', '$')}{item.get('price', 0)}</li>"
        receipt_html += "</ul>"
    
    # Add tax info
    if "tax_information" in result and result["tax_information"] and "sales_tax" in result["tax_information"]:
        receipt_html += f"<p><strong>Tax:</strong> {result.get('currency', '$')}{result['tax_information']['sales_tax']}</p>"
    
    # Add payment method
    if result.get('payment_method'):
        receipt_html += f"<p><strong>Payment Method:</strong> {result.get('payment_method')}</p>"
    
    return receipt_html

def main():
    """Main Streamlit application."""
    
    st.title("Financial Assistant")
    
    # Initialize the coordinator agent
    coordinator = initialize_coordinator_agent()
    
    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Process Receipt", "Ask Questions"])
    
    if page == "Home":
        st.markdown("## Welcome to your Financial Assistant")
        st.markdown("""
        This application helps you track your finances using AI:
        - Upload receipts to extract and store purchase information
        - Ask questions about your spending habits and purchase history
        - Get financial insights and recommendations
        
        Use the sidebar to navigate between different features.
        """)
        
        # Display stats from memory
        st.subheader("Your Financial Overview")
        try:
            purchases = coordinator.get_purchase_history()
            total_spent = sum(p.total_amount for p in purchases)
            merchant_count = len(set(p.merchant_name for p in purchases))
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Purchases", len(purchases))
            col2.metric("Total Spent", f"${total_spent:.2f}")
            col3.metric("Unique Merchants", merchant_count)
            
            if purchases:
                st.subheader("Recent Transactions")
                # Sort by date (newest first) and take the 5 most recent
                recent = sorted(purchases, key=lambda p: p.transaction_date, reverse=True)[:5]
                
                for p in recent:
                    with st.expander(f"{p.merchant_name} - ${p.total_amount:.2f} ({p.transaction_date})"):
                        st.write(f"**Items:** {len(p.items)}")
                        st.write(f"**Payment Method:** {p.payment_method or 'Unknown'}")
                        if p.items:
                            st.write("**Purchased Items:**")
                            for item in p.items:
                                st.write(f"- {item.name}: ${item.price:.2f} ({item.category})")
        except Exception as e:
            st.warning(f"Could not load purchase history: {e}")
            
    elif page == "Process Receipt":
        st.markdown("## Receipt Processing")
        st.markdown("Upload a receipt image to extract purchase information.")
        
        # File uploader
        uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "jpeg", "png"])
        
        if uploaded_file is not None:
            # Display the uploaded image
            st.image(uploaded_file, caption="Uploaded Receipt")
            
            # Add processing button
            if st.button("Process Receipt"):
                with st.spinner("Processing receipt with AI..."):
                    try:
                        # Validate and resize image if needed
                        image_bytes = uploaded_file.getvalue()
                        is_valid, error_msg = validate_image(image_bytes)
                        
                        if not is_valid:
                            st.error(f"Invalid image: {error_msg}")
                            st.stop()
                        
                        # Resize if too large
                        image_bytes = resize_image_if_needed(image_bytes, max_size_mb=5.0)
                        
                        # Save the file temporarily
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                            tmp_file.write(image_bytes)
                            temp_file_path = tmp_file.name
                        
                        # Process the receipt using the coordinator agent
                        result = coordinator.process_receipt(temp_file_path)
                        
                        # Display results
                        st.success("Receipt processed successfully and added to your purchase history!")
                        st.markdown(format_receipt_results(result), unsafe_allow_html=True)
                        
                        # Show raw JSON for debugging
                        with st.expander("Raw JSON Result"):
                            st.json(result)
                        
                        # Clean up temporary file
                        os.unlink(temp_file_path)
                        
                    except Exception as e:
                        st.error(f"Error processing receipt: {e}")
                        st.stop()
    
    elif page == "Ask Questions":
        st.markdown("## Ask Questions About Your Finances")
        st.markdown("""
        You can ask questions like:
        - How much did I spend at Trader Joe's this month?
        - What were my largest purchases last week?
        - What category do I spend the most on?
        - Show me all my grocery purchases
        """)
        
        # Debug section - shows what's in session state
        if st.checkbox("Show Debug Info"):
            st.write("Session State Contents:", st.session_state)
            st.write("Memory Status:", {"purchase_count": len(coordinator.get_purchase_history())})
            
        # Add chat history to session state if it doesn't exist
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        # Add a key to track if the query has been processed
        if "query_processed" not in st.session_state:
            st.session_state.query_processed = False
            
        # Create a simple form for the chat interface
        with st.form(key="chat_form", clear_on_submit=True):
            user_input = st.text_area("Enter your question:", height=100)
            submit = st.form_submit_button("Ask")
        
        # Process the query when submitted
        if submit and user_input:
            # Store the user's query for display
            user_query = user_input.strip()
            
            # Actually process the query
            with st.spinner("Processing your question..."):
                try:
                    # Process the query through the coordinator agent
                    response = coordinator.process_query(user_query)
                    
                    # Add to chat history
                    st.session_state.chat_history.append({"role": "user", "content": user_query})
                    st.session_state.chat_history.append({"role": "assistant", "content": response})
                    
                    # Force a rerun to update the UI
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing query: {e}")
                    st.write("Exception details:", str(e))
        
        # Display chat history
        st.subheader("Conversation")
        
        if not st.session_state.chat_history:
            st.info("No conversation history yet. Ask a question to get started!")
        else:
            # Create a container for the chat history
            chat_container = st.container()
            
            # Display the chat messages using expanders for long messages
            with chat_container:
                for idx, message in enumerate(st.session_state.chat_history):
                    if message["role"] == "user":
                        st.markdown(f"**You:** {message['content']}")
                    else:
                        content = message['content']
                        # If content is very long, use an expander
                        if len(content) > 300:
                            with st.expander(f"**Assistant:** (click to expand/collapse)"):
                                st.markdown(content)
                        else:
                            st.markdown(f"**Assistant:** {content}")
                    
                    # Add a separator between messages except for the last one
                    if idx < len(st.session_state.chat_history) - 1:
                        st.markdown("---")
    

if __name__ == "__main__":
    main()