"""
@author: bfx
@version: 1.0.0
@file: fetch_market_data.py
@time: 4/18/25 18:37
"""
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd

def fetch_market_data(indices: List[str], days: int) -> Dict[str, pd.Series]:
    """
    Fetch historical daily closing prices for given market indices.

    Args:
        indices: A list of ticker symbols for the indices, for example:
            - '^GSPC' for S&P 500
            - '^DJI'  for Dow Jones Industrial Average
            - '^IXIC' for Nasdaq Composite
            - '^RUT'  for Russell 2000
            - '^VIX'  for CBOE Volatility Index (fear gauge)
        days:    How many calendar days of history to retrieve (including weekends; only trading days returned).

    Returns:
        A dict mapping each ticker symbol to a pandas Series of closing prices, indexed by date.
    """
    end_date = datetime.today()
    start_date = end_date - timedelta(days=days)

    result: Dict[str, pd.Series] = {}
    for symbol in indices:
        # Download history; auto-adjusts for market holidays
        df = yf.download(
            tickers=symbol,
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            progress=False,
            interval="1d",
        )
        # If data exists, take the 'Close' column
        if not df.empty and 'Close' in df.columns:
            result[symbol] = df['Close']
        else:
            # Return an empty Series if download failed
            result[symbol] = pd.Series(dtype=float)

    return result

# Example usage:
if __name__ == "__main__":
    indices = ["^GSPC", "^DJI", "^IXIC"]
    data = fetch_market_data(indices, days=7)
    for symbol, series in data.items():
        print(f"\n=== {symbol} ===")
        print(series)
