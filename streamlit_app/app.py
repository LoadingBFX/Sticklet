import base64

import streamlit as st
from pathlib import Path
import tempfile
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
from dotenv import load_dotenv
from streamlit import title

from src.agents import CoordinatorAgent
from src.tools.fetch_market_data import fetch_market_data
from src.utils.image_utils import validate_image, resize_image_if_needed
import plotly.graph_objects as go
from PIL import Image
import traceback
from collections import defaultdict

# Load environment variables
load_dotenv()

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
    # Set page config
    st.set_page_config(
        page_title="Sticklet: A Personal Receipt Journal by Scotty",
        page_icon="🐶",
        layout="wide"
    )
    st.session_state.setdefault("receipt_processed", False)
    st.session_state.setdefault("raw_result", {})
    st.session_state.setdefault("calibrated", {})

    # Initialize the coordinator agent
    coordinator = initialize_coordinator_agent()

    # Sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Receipts History", "Monthly Report", "Ask Questions", "Market & News"])


    if page == "Home":
        col1, col2 = st.columns([5,6])
        with col1:
            st.markdown("## Welcome to Sticklet!")

            st.markdown("""
            Just like Scotty builds his cozy den with little sticks, you can build a smart record of your spending.
            **Powered by AI, Sticklet helps you:**
            
            - 🧾 **Snap and Save**  
              Upload receipts to auto-record where, what, and how much.
            - 💬 **Chat with Your Spending**  
              Ask questions like “How much did I spend on snacks last month?” or “What’s my favorite grocery store?”
            - 📊 **Monthly Insights**  
              Get clear reports on your finances—track spending, spot item trends, and see price changes over time.
            - 📰 **Market Peek**  
              Stay in the loop with bite-sized financial news summaries tailored to your purchases and interests.
            """)

            uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "jpeg", "png"], key="upload_file")

        with col2:
            # Display stats from memory
            try:
                purchases = coordinator.get_purchase_history()
                today = datetime.today().date()
                today_purchases = [
                    p for p in purchases
                    if datetime.strptime(p.transaction_date, "%Y-%m-%d").date() == today
                ]
                today_spent = sum(p.total_amount for p in today_purchases)
                total_spent = sum(p.total_amount for p in purchases)

                col1, col2 = st.columns([6,4])
                with col1:
                    st.metric("Today's Spending", f"${today_spent:.2f}")
                    st.metric("Total Spent", f"${total_spent:.2f}")
                with col2:
                    st.image("./assets/greeting.png", width=300)

                df = pd.DataFrame([{
                    "date": datetime.strptime(p.transaction_date, "%Y-%m-%d").date(),
                    "amount": p.total_amount
                } for p in purchases])

                today = datetime.today().date()
                past_7_days = [today - timedelta(days=i) for i in range(6, -1, -1)]
                daily_spend = df.groupby("date")["amount"].sum().reindex(past_7_days, fill_value=0.0)

                daily_spend.index = pd.to_datetime(daily_spend.index)
                labels = daily_spend.index.strftime("%b %d")

                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=labels,
                    y=daily_spend.values,
                    mode='lines+markers',
                    name='Spend ($)',
                    line=dict(width=2)
                ))
                fig.update_layout(
                    title="Weekly Spending",
                    xaxis_title="Date",
                    yaxis_title="Amount ($)",
                    height=250,
                    margin=dict(t=30, b=30, l=30, r=30)
                )

                st.plotly_chart(fig, use_container_width=False)

            except Exception as e:
                st.warning(f"Could not load purchase history: {e}")

        if uploaded_file is not None:
            with st.container():
                col1, col2 = st.columns(2)

                # 左侧：预览
                with col1:
                    # st.image(uploaded_file, caption="Uploaded Receipt", use_container_width=True)
                    raw = uploaded_file.read()
                    b64 = base64.b64encode(raw).decode()

                    st.markdown(
                        f"<img src='data:image/jpeg;base64,{b64}' "
                        f"style='height:700px;width:auto;border-radius:8px;'/>",
                        unsafe_allow_html=True
                    )
                # 右侧：处理 & 校对
                with col2:
                    # # 1️⃣ 定义滚动区域样式
                    # st.markdown("""
                    #         <style>
                    #           .scroll-box {
                    #             max-height: 400px;
                    #             overflow-y: auto;
                    #             padding-right: 10px;
                    #           }
                    #           .scroll-box input {
                    #             background-color: #f2f4f7;
                    #             border: none;
                    #             border-radius: 6px;
                    #             padding: 8px;
                    #             width: 100%;
                    #             margin-bottom: 10px;
                    #           }
                    #           .pagination-btn {
                    #             margin-right: 5px;
                    #             border-radius: 5px;
                    #             padding: 5px 10px;
                    #           }
                    #         </style>
                    #     """, unsafe_allow_html=True)

                    # Process Receipt 按钮 & 占位符
                    result_placeholder = st.empty()
                    if st.button("Process Receipt") and not st.session_state.receipt_processed:
                        with st.spinner("Processing receipt with AI..."):
                            try:
                                # 验证 & 调整大小
                                image_bytes = uploaded_file.getvalue()
                                is_valid, err = validate_image(image_bytes)
                                if not is_valid:
                                    st.error(f"Invalid image: {err}")
                                    st.stop()

                                image_bytes = resize_image_if_needed(image_bytes, max_size_mb=5.0)

                                # 写入临时文件
                                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                                    tmp.write(image_bytes)
                                    tmp_path = tmp.name

                                # —— 在这里捕获任何来自 process_receipt 的异常 ——
                                try:
                                    result = coordinator.process_receipt(tmp_path)
                                except Exception as proc_err:
                                    st.error("Error inside process_receipt! See console for details.")
                                    traceback.print_exc()
                                    st.stop()

                                # 正常走到这里就说明没有异常
                                st.session_state.receipt_processed = True
                                st.session_state.calibrated = result.copy()

                                st.success("Receipt parsed. Please verify below.")

                            finally:
                                # 无论如何，都要尝试删掉临时文件
                                try:
                                    os.unlink(tmp_path)
                                except Exception:
                                    pass

                    # 3️⃣ 解析完成后，在占位符里渲染可编辑表单
                    if st.session_state.get("receipt_processed", False):
                        with result_placeholder.container():
                            st.markdown('<div class="scroll-box">', unsafe_allow_html=True)

                            # — 顶级三个字段 —
                            mn = st.text_input(
                                "merchant_name",
                                value=st.session_state.calibrated.get("merchant_name", ""),
                                key="cal_merchant"
                            )
                            td = st.text_input(
                                "transaction_date",
                                value=st.session_state.calibrated.get("transaction_date", ""),
                                key="cal_date"
                            )
                            ta = st.text_input(
                                "total_amount",
                                value=str(st.session_state.calibrated.get("total_amount", "")),
                                key="cal_total"
                            )

                            # — Items 列表逐行展开 —
                            items_list = st.session_state.calibrated.get("items", [])
                            for i, itm in enumerate(items_list):
                                # four columns: Name / Price / Qty / Delete
                                c_name, c_price, c_qty, c_del = st.columns([4, 2, 1, 1])

                                # 1) Inputs
                                with c_name:
                                    name_val = st.text_input(
                                        f"Item {i + 1} Name",
                                        value=itm.get("name", ""),
                                        key=f"item_{i}_name"
                                    )
                                with c_price:
                                    price_val = st.text_input(
                                        "Price",
                                        value=str(itm.get("price", "")),
                                        key=f"item_{i}_price"
                                    )
                                with c_qty:
                                    qty_val = st.text_input(
                                        "Qty",
                                        value=str(itm.get("quantity", "")),
                                        key=f"item_{i}_qty"
                                    )

                                # 2) Delete button
                                with c_del:
                                    st.write("")  # spacer line
                                    st.write("")  # spacer line
                                    if st.button("Del", key=f"delete_item_{i}"):
                                        # remove this item & save back
                                        items_list.pop(i)
                                        st.session_state.calibrated["items"] = items_list
                                        st.rerun()

                                # 3) write back edits
                                items_list[i] = {
                                    "name": name_val,
                                    "price": float(price_val) if price_val else 0.0,
                                    "quantity": int(qty_val) if qty_val else 0
                                }

                            # finally save the updated list
                            st.session_state.calibrated["items"] = items_list

                            # 写回 session_state
                            st.session_state.calibrated["merchant_name"] = mn
                            st.session_state.calibrated["transaction_date"] = td
                            st.session_state.calibrated["total_amount"] = float(ta) if ta else 0.0

                            st.markdown('</div>', unsafe_allow_html=True)

                            # When the user clicks "Done", merge raw and calibrated data and save
                            if st.button("Done"):
                                # Retrieve the original parsed data from session state
                                raw = st.session_state.get("raw_result", {})

                                # Build a dict of the user‑adjusted fields
                                calibrated = {
                                    "merchant_name": mn,
                                    "transaction_date": td,
                                    "total_amount": float(ta) if ta else 0.0,
                                    "items": items_list
                                }

                                # Merge calibrated values into the raw receipt data (overwriting raw fields)
                                full_data = raw.copy()
                                full_data.update(calibrated)

                                # Call the save method to persist the fully merged receipt
                                coordinator.save_calibrated_receipt(full_data)
                                st.success("🎉 Receipt saved!")

                                # after saving…
                                for key in ["receipt_processed", "raw_result", "calibrated", "upload_file"]:
                                    st.session_state.pop(key, None)

                                st.rerun()

        if purchases:
            st.subheader("Recent Transactions")
            recent = sorted(purchases, key=lambda p: p.transaction_date, reverse=True)[:5]

            for p in recent:
                # Build a label that includes the unique purchase ID
                label = (
                    f"{p.merchant_name} – ${p.total_amount:.2f} "
                    f"({p.transaction_date})"
                )

                # Always start closed
                with st.expander(label, expanded=False):
                    st.write(f"**Items:** {len(p.items)}")
                    st.write(f"**Payment Method:** {p.payment_method or 'Unknown'}")
                    if p.items:
                        st.write("**Purchased Items:**")
                        for item in p.items:
                            st.write(f"- {item.name}: ${item.price:.2f} ({item.category})")

                    # Delete button
                    if st.button("🗑️ Delete Transaction", key=f"del_{p.id}"):
                        coordinator.delete_purchase(p.id)
                        st.success("Transaction deleted!")
                        st.rerun()


    # elif page == "Process Receipt":
    #     st.markdown("## Receipt Processing")
    #     st.markdown("Upload a receipt image to extract purchase information.")
    #
    #     # File uploader
    #     uploaded_file = st.file_uploader("Choose a receipt image...", type=["jpg", "jpeg", "png"])
    #
    #     if uploaded_file is not None:
    #         # Display the uploaded image
    #         st.image(uploaded_file, caption="Uploaded Receipt")
    #
    #         # Add processing button
    #         if st.button("Process Receipt"):
    #             with st.spinner("Processing receipt with AI..."):
    #                 try:
    #                     # Validate and resize image if needed
    #                     image_bytes = uploaded_file.getvalue()
    #                     is_valid, error_msg = validate_image(image_bytes)
    #
    #                     if not is_valid:
    #                         st.error(f"Invalid image: {error_msg}")
    #                         st.stop()
    #
    #                     # Resize if too large
    #                     image_bytes = resize_image_if_needed(image_bytes, max_size_mb=5.0)
    #
    #                     # Save the file temporarily
    #                     with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
    #                         tmp_file.write(image_bytes)
    #                         temp_file_path = tmp_file.name
    #
    #                     # Process the receipt using the coordinator agent
    #                     result = coordinator.process_receipt(temp_file_path)
    #
    #                     # Display results
    #                     st.success("Receipt processed successfully and added to your purchase history!")
    #                     st.markdown(format_receipt_results(result), unsafe_allow_html=True)
    #
    #                     # Show raw JSON for debugging
    #                     with st.expander("Raw JSON Result"):
    #                         st.json(result)
    #
    #                     # Clean up temporary file
    #                     os.unlink(temp_file_path)
    #
    #                 except Exception as e:
    #                     st.error(f"Error processing receipt: {e}")
    #                     st.stop()
    elif page == "Receipts History":
        purchases = coordinator.get_purchase_history()
        merchant_count = len(set(p.merchant_name for p in purchases))
        col1, col2 = st.columns(2)
        col1.metric("## Total Purchases", len(purchases))
        col2.metric("## Unique Merchants", merchant_count)
        st.subheader("Receipts History")
        st.image("./assets/strick_receipt.png", width=200)


        # Pagination setup
        items_per_page = 10  # Number of receipts per page
        total_pages = (len(purchases) + items_per_page - 1) // items_per_page  # Ceiling division

        # Initialize page number in session state if not already set
        if "receipt_page" not in st.session_state:
            st.session_state.receipt_page = 0

        # Calculate which receipts to show on current page
        start_idx = st.session_state.receipt_page * items_per_page
        end_idx = min(start_idx + items_per_page, len(purchases))

        # Display current page receipts
        for p in purchases[start_idx:end_idx]:
            # Build a label that includes the unique purchase ID
            label = (
                f"{p.merchant_name} – ${p.total_amount:.2f} "
                f"({p.transaction_date})"
            )

            # Always start closed
            with st.expander(label, expanded=False):
                st.write(f"**Items:** {len(p.items)}")
                st.write(f"**Payment Method:** {p.payment_method or 'Unknown'}")
                if p.items:
                    st.write("**Purchased Items:**")
                    for item in p.items:
                        st.write(f"- {item.name}: ${item.price:.2f} ({item.category})")

                # Delete button
                if st.button("🗑️ Delete Transaction", key=f"del_{p.id}"):
                    coordinator.delete_purchase(p.id)
                    st.success("Transaction deleted!")
                    st.rerun()

        # Pagination controls
        col1, col2, col3 = st.columns([1, 3, 1])

        with col1:
            if st.session_state.receipt_page > 0:
                if st.button("← Previous", key="prev_page"):
                    st.session_state.receipt_page -= 1
                    st.rerun()

        with col2:
            page_num = st.session_state.receipt_page + 1
            total_pages = max(1, total_pages)

            st.markdown(
                f"<div style='text-align: center; font-size: 1.1em;'>"
                f"Page {page_num} of {total_pages}"
                f"</div>",
                unsafe_allow_html=True,
            )
            # st.write(f"Page {st.session_state.receipt_page + 1} of {max(1, total_pages)}")

        with col3:
            if st.session_state.receipt_page < total_pages - 1:
                spacer, btn_col = st.columns([5, 5])
                with btn_col:
                    # Only show "Next" button if there are more pages
                    if st.button("Next →", key="next_page"):
                        st.session_state.receipt_page += 1
                        st.rerun()

    elif page == "Monthly Report":
        today = datetime.today().date()
        month_name = today.strftime("%B")

        # set the page header dynamically
        st.header(f"{month_name}'s Monthly Report")

        # 1) Fetch all purchases this month
        purchases = coordinator.get_purchase_history()
        today = datetime.today().date()
        month_start = today.replace(day=1)
        this_month = [
            p for p in purchases
            if month_start <= datetime.strptime(p.transaction_date, "%Y-%m-%d").date() <= today
        ]

        # a) Daily spending line
        days = pd.date_range(month_start, today)
        df = pd.DataFrame([
            {"date": datetime.strptime(p.transaction_date, "%Y-%m-%d").date(),
             "amount": p.total_amount}
            for p in this_month
        ])
        daily = df.groupby("date")["amount"].sum().reindex(days, fill_value=0.0)
        x_days = [d.day for d in daily.index]

        fig_line = go.Figure(go.Scatter(
            x=x_days,
            y=daily.values,
            mode="lines+markers"
        ))
        fig_line.update_layout(
            title="Daily Spending This Month",
            xaxis=dict(title="Day of Month", tickmode="linear", dtick=1),
            margin=dict(t=30, l=20, r=20, b=20),
            height=300
        )

        # b) Supermarket pie chart
        # Here we treat any merchant containing "Costco" or "Whole Foods" etc. as 'Supermarket'
        purchases = coordinator.get_purchase_history()
        today = datetime.today().date()
        month_start = today.replace(day=1)
        this_month = [
            p for p in purchases
            if month_start <= datetime.strptime(p.transaction_date, "%Y-%m-%d").date() <= today
        ]

        # 按 merchant_name 累加消费金额
        merchant_sums = defaultdict(float)
        for p in this_month:
            merchant_sums[p.merchant_name] += p.total_amount

        # 如果商户太多，可以选取前 5 大，其它归为 “Others”
        top_n = 5
        sorted_merchants = sorted(
            merchant_sums.items(),
            key=lambda x: x[1],
            reverse=True
        )
        top = sorted_merchants[:top_n]
        others = sorted_merchants[top_n:]
        if others:
            others_sum = sum(val for _, val in others)
            top.append(("Others", others_sum))

        labels = [m for m, _ in top]
        values = [v for _, v in top]

        # 画饼图
        fig_pie = go.Figure(go.Pie(
            labels=labels,
            values=values,
            hole=0.4,
            hovertemplate="%{label}: $%{value:.2f} (%{percent})<extra></extra>"
        ))
        fig_pie.update_layout(
            title="Spending by Merchant This Month",
            margin=dict(t=30, l=20, r=20, b=20),
            height=300
        )

        # 渲染
        col1, col2 = st.columns([6, 4])
        with col1:
            st.plotly_chart(fig_line, use_container_width=True)  # 你的折线图
        with col2:
            st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        st.subheader("Monthly Narrative")

        # current month as integer
        month_int = today.month

        # Button to trigger generation
        if st.button("Generate Monthly Narrative"):
            with st.spinner("Generating your monthly report…"):
                try:
                    # call your real agent method
                    report = coordinator.gen_monthly_report(month_int)
                except Exception as e:
                    st.error(f"Error generating monthly report: {e}")
                    # fallback placeholder
                    report = (
                        f"**Demo Report for Month {month_int}**\n\n"
                        f"- Total spent: **${daily.sum():.2f}**\n"
                        f"- Highest spending day: **{daily.idxmax().strftime('%b %d')}**\n"
                        f"- Lowest spending day: **{daily.idxmin().strftime('%b %d')}**\n"
                        f"- Average daily spend: **${daily.mean():.2f}**\n"
                    )
            # render the report (markdown + HTML)
            st.markdown(report, unsafe_allow_html=True)
        else:
            # prompt user to click
            st.info("Click the button above to generate your monthly narrative.")

    elif page == "Market & News":
        st.header("Today's Market & News")
        # 1) Define the tickers and friendly names
        indices = ["^GSPC", "^DJI", "^IXIC"]
        name_map = {"^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "Nasdaq"}

        # 2) Fetch the last 7 days of closing prices
        data = fetch_market_data(indices, days=7)

        # 3) Display the most recent close and daily change as metrics
        metric_cols = st.columns(len(indices))
        for idx, symbol in enumerate(indices):
            series = data[symbol]
            if not series.empty:
                latest = float(series.iloc[-1])
                previous = float(series.iloc[-2]) if len(series) > 1 else latest
                delta = latest - previous
                metric_cols[idx].metric(
                    label=name_map[symbol],
                    value=f"{latest:,.2f}",
                    delta=f"{delta:+,.2f}"
                )
            else:
                metric_cols[idx].metric(
                    label=name_map[symbol],
                    value="N/A",
                    delta="N/A"
                )

        # 4) Render three separate 7‑day line charts side by side
        chart_cols = st.columns(3)
        for idx, symbol in enumerate(indices):
            series = data[symbol]
            if series.empty:
                chart_cols[idx].write(f"No data for {name_map[symbol]}")
                continue

            # Prepare x/y values
            dates = [d.strftime("%b %d") for d in series.index]
            values = [float(v) for v in series.values]

            # Build a standalone figure for each index
            fig = go.Figure(go.Scatter(
                x=dates,
                y=values,
                mode="lines+markers",
                name=name_map[symbol]
            ))
            fig.update_layout(
                title=f"7‑Day Close: {name_map[symbol]}",
                xaxis_title="Date",
                yaxis_title="Price",
                margin=dict(l=20, r=20, t=30, b=20),
                height=250
            )

            # Display the figure in its column
            chart_cols[idx].plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        st.subheader("News Summary")

        # Add a button to trigger generation
        if st.button("Generate Today's Market Summary"):
            with st.spinner("Generating today's market narrative…"):
                try:
                    summary = coordinator.generate_daily_market_report()
                except Exception as e:
                    summary = f"Failed to generate market summary: {e}"
            # Render the full paragraph
            st.write(summary)
        else:
            st.info("Click the button above to generate today's market summary.")





    elif page == "Ask Questions":

        st.markdown("## 💬 Ask Questions About Your Finances")

        st.markdown("""

        Curious about your spending? Ask anything like:


        - 🛒 How much did I spend at Trader Joe's this month?  

        - 💰 What were my biggest purchases last week?  

        - 📊 Which category do I spend the most on?  

        - 🥦 Show me all grocery-related purchases.

        """)

        # Debug info (optional)

        with st.expander("🛠 Debug Info"):

            st.write("Session State:", st.session_state)

            st.write("Memory Status:", {"purchase_count": len(coordinator.get_purchase_history())})

        # Initialize chat history if needed

        st.session_state.setdefault("chat_history", [])

        # Display chat history (user + assistant bubbles)

        for msg in st.session_state.chat_history:

            with st.chat_message(msg["role"]):

                if msg["role"] == "assistant" and len(msg["content"]) > 300:

                    with st.expander("Long reply — click to expand"):

                        st.markdown(msg["content"])

                else:

                    st.markdown(msg["content"])

        # Chat input field fixed at bottom

        user_input = st.chat_input("Ask me anything about your purchases or financial habits...")

        if user_input:

            # Display user message immediately

            with st.chat_message("user"):

                st.markdown(user_input)

            # Process the query

            with st.chat_message("assistant"):

                with st.spinner("Thinking..."):

                    try:

                        response = coordinator.process_query(user_input)

                        st.markdown(response)

                    except Exception as e:

                        response = f"⚠️ Oops, something went wrong: `{e}`"

                        st.error(response)

            # Append both messages to chat history

            st.session_state.chat_history.append({"role": "user", "content": user_input})

            st.session_state.chat_history.append({"role": "assistant", "content": response})


if __name__ == "__main__":
    main()