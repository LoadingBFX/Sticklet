"""
Main entry point for the Financial Portal application.
This script launches the Streamlit web interface.
"""
import os
import subprocess
import sys

def main():
    """
    Launch the Streamlit application.
    """
    streamlit_file = os.path.join(os.path.dirname(__file__), "streamlit_app", "app.py")
    
    print(f"Starting Financial Portal application...")
    
    # Launch Streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", streamlit_file])

if __name__ == "__main__":
    main()