"""
@author: bfx
@version: 1.0.0
@file: montly_report_agent.py
@time: 4/18/25 16:59
"""
import os
from typing import Dict, List, Any, Optional
from datetime import date, datetime, timedelta
from collections import defaultdict, Counter

from mistralai import Mistral

from src.utils.memory import PurchaseMemory, Purchase

class MonthlyReportAgent:
    """
    MonthlyReportAgent is responsible for generating monthly reports based on the receipts processed by the ReceiptReaderAgent.
    It aggregates the data and provides insights into spending patterns, categories, and other relevant information.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the receipt reader agent with the Mistral API.

        Args:
            api_key: Optional Mistral API key. If not provided, will try to load from environment.
        """
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Mistral API key is required. Provide it directly or set MISTRAL_API_KEY environment variable.")

        # Direct Mistral client for potential fallback
        self.client = Mistral(api_key=self.api_key)
        self.model = "mistral-large-latest"
        self.memory = PurchaseMemory()

    def process_monthly_report(self, month: int, year: Optional[int] = None) -> str:
        # 1) Date range
        today = date.today()
        year = year or today.year
        month_start = date(year, month, 1)
        next_month = date(year + (month == 12), (month % 12) + 1, 1)
        end_date = next_month - timedelta(days=1)

        # 2) Fetch purchases
        purchases = self.memory.get_purchases_by_date_range(
            month_start.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
        if not purchases:
            return f"No spending data for {month_start.strftime('%B %Y')}."

        # 3) Aggregate metrics
        total_spent = sum(p.total_amount for p in purchases)
        # daily totals
        daily = defaultdict(float)
        for p in purchases:
            d = datetime.strptime(p.transaction_date, "%Y-%m-%d").date()
            daily[d] += p.total_amount
        top_days = sorted(daily.items(), key=lambda x: x[1], reverse=True)[:3]
        # top merchants
        merchant_totals = Counter(p.merchant_name for p in purchases)
        top_merchants = merchant_totals.most_common(3)

        # 4) Flatten every item in the month
        item_lines = []
        for p in purchases:
            for itm in p.items:
                item_lines.append(
                    f"  • {itm.name} x{itm.quantity} @ ${itm.price:.2f}"
                )
        items_section = "\n".join(item_lines)

        # 5) Build the prompt
        month_name = month_start.strftime("%B %Y")
        item_lines = []
        for p in purchases:
            for itm in p.items:
                item_lines.append(f"{itm.name} x{itm.quantity} @ ${itm.price:.2f}")

        # 5) Build the data context (as input, not as output format)
        data_context = (
            f"Month: {month_name}\n"
            f"Total spent: ${total_spent:.2f}\n"
            f"Top 3 spending days:\n"
        )
        for d, amt in top_days:
            data_context += f"  - {d.strftime('%b %d')}: ${amt:.2f}\n"

        data_context += "Top 3 merchants by spend:\n"
        for m, _ in top_merchants:
            amt = sum(p.total_amount for p in purchases if p.merchant_name == m)
            data_context += f"  - {m}: ${amt:.2f}\n"

        data_context += "Items purchased this month (name × qty @ unit price):\n"
        for line in item_lines:
            data_context += f"  - {line}\n"

        prompt = f"""
        Here is a concise data summary of your spending for {month_name}:

        {data_context}

        As a friendly financial advisor, please write a clear, well‑structured report in 3–4 paragraphs based on that data.
        Start with an overview of your total spend, then discuss any notable high‑spend days,
        mention which merchants took the biggest share of your budget and why,
        briefly describe the types of items you purchased (using the list above),
        and finish with one or two actionable insights for next month.
        """

        # 6) Call Mistral
        messages = [
            {
                "role": "system",
                "content": "You are a financial analyst assistant."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        resp = self.client.chat.complete(
            model=self.model,
            messages=messages,
        )
        content = resp.choices[0].message.content.strip()
        return content or f"Could not generate report for {month_name}."