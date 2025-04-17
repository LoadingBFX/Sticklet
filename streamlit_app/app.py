import streamlit as st
from pathlib import Path
import tempfile
import os
import json

from dotenv import load_dotenv
from src.agents import ReceiptReaderAgent
from src.utils.image_utils import validate_image, resize_image_if_needed

# Load environment variables
load_dotenv()

# Set page config
st.set_page_config(
    page_title="Financial Portal - Receipt Reader",
    page_icon="💰",
    layout="centered"
)

def initialize_receipt_reader():
    """Initialize the receipt reader agent, handling API key setup."""
    api_key = os.environ.get("MISTRAL_API_KEY")
    
    if not api_key:
        st.error("Mistral API key not found. Please set the MISTRAL_API_KEY environment variable.")
        st.stop()
    
    try:
        return ReceiptReaderAgent(api_key=api_key)
    except Exception as e:
        st.error(f"Error initializing receipt reader agent: {e}")
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
    <p><strong>Store:</strong> {result.get('store', 'Unknown')}</p>
    <p><strong>Date:</strong> {result.get('date', 'Unknown')}</p>
    <p><strong>Total:</strong> {result.get('currency', '$')}{result.get('total', 0)}</p>
    """
    
    # Add items if available
    items = result.get('items', [])
    if items:
        receipt_html += "<h4>Items</h4><ul>"
        for item in items:
            receipt_html += f"<li>{item.get('name', 'Item')}: {result.get('currency', '$')}{item.get('price', 0)}</li>"
        receipt_html += "</ul>"
    
    # Add tax info
    if result.get('tax') is not None:
        receipt_html += f"<p><strong>Tax:</strong> {result.get('currency', '$')}{result.get('tax')}</p>"
    
    # Add payment method
    if result.get('payment_method'):
        receipt_html += f"<p><strong>Payment Method:</strong> {result.get('payment_method')}</p>"
    
    return receipt_html

def main():
    """Main Streamlit application."""
    
    st.title("Receipt Reader")
    st.markdown("Upload a receipt image to extract information using Mistral OCR and LLM.")
    
    # Initialize the receipt reader agent
    receipt_reader = initialize_receipt_reader()
    
    # File uploader
    uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        # Display the uploaded image
        st.image(uploaded_file, caption="Uploaded Receipt")
        
        # Add processing button
        if st.button("Process Receipt"):
            with st.spinner("Processing receipt with Mistral AI..."):
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
                    
                    # Process the receipt
                    result = receipt_reader.process_receipt(temp_file_path)
                    
                    # Display results
                    st.success("Receipt processed successfully!")
                    st.markdown(format_receipt_results(result), unsafe_allow_html=True)
                    
                    # Show raw JSON for debugging
                    with st.expander("Raw JSON Result"):
                        st.json(result)
                    
                    # Clean up temporary file
                    os.unlink(temp_file_path)
                    
                except Exception as e:
                    st.error(f"Error processing receipt: {e}")
                    st.stop()

if __name__ == "__main__":
    main()