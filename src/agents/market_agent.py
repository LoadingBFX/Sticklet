"""
@author: bfx
@version: 1.0.0
@file: market_agent.py
@time: 4/18/25 18:59
"""
import os
from typing import Dict, List
import pandas as pd

from mistralai import Mistral
from datetime import datetime

from src.tools.fetch_market_data import fetch_market_data


class MarketAgent:
    """
    Agent responsible for fetching market indicators and
    historical index data using the fetch_market_data tool.
    """
    def __init__(self, api_key: str = None):
        """
        Initialize the MarketAgent.
        Args:
            api_key: Optional API key for future enhancements.
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("Mistral API key is required. Provide it directly or set MISTRAL_API_KEY environment variable.")
        self.client = Mistral(api_key=self.api_key) if self.api_key else None
        self.model = "mistral-large-latest"

    def get_current_indicators(self) -> Dict[str, float]:
        """
        Fetch the most recent closing prices for the three major US indices:
        S&P 500, Dow Jones Industrial Average, and Nasdaq Composite.

        Returns:
            A dict mapping ticker symbols to the latest closing price.
        """
        # fetch last 2 calendar days to compute change
        tickers = ["^GSPC", "^DJI", "^IXIC"]
        data = fetch_market_data(tickers, days=2)
        latest = {}
        for sym in tickers:
            series: pd.Series = data.get(sym, pd.Series())
            if not series.empty:
                latest[sym] = float(series.iloc[-1])
            else:
                latest[sym] = None
        return latest

    def get_7day_history(self) -> Dict[str, pd.Series]:
        """
        Fetch the past 7 days of daily closing prices for the
        three major US indices.

        Returns:
            A dict mapping ticker symbols to pd.Series of closing prices.
        """
        tickers = ["^GSPC", "^DJI", "^IXIC"]
        return fetch_market_data(tickers, days=7)

    def generate_daily_summary(self) -> str:
        """
        Create a concise narrative summary of today's market performance,
        using the latest indicators for S&P 500, Dow Jones, and Nasdaq.

        Returns:
            A multi-sentence string summarizing today's market.
        """
        if not self.client:
            raise RuntimeError("Mistral client not initialized for summary generation.")

        # Retrieve current indicators
        inds = self.get_current_indicators()
        # Build user content with today's date and indicator values
        today_str = datetime.today().strftime("%B %d, %Y")
        content = (
            f"Market Summary for {today_str}:\n"
            f"- S&P 500 closed at {inds.get('^GSPC', 'N/A'):.2f}\n"
            f"- Dow Jones closed at {inds.get('^DJI', 'N/A'):.2f}\n"
            f"- Nasdaq closed at {inds.get('^IXIC', 'N/A'):.2f}\n"
        )

        # Construct prompt
        prompt = (
            "You are a financial news analyst. "
            "Based on the data below, write a clear, engaging paragraph "
            "summarizing today's US equity market performance. "
            "Mention key drivers, direction, and contextual insight.\n\n"
            f"{content}"
        )

        # Call Mistral
        resp = self.client.chat.complete(
            model=self.model,
            messages=[
                {"role": "system", "content": "You provide concise market commentary."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip() or "No summary available."
