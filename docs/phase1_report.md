# Research and Planning Report

94-815 Agent Based Modelling and Agentic Technology

Team 8 - Fanxing Bu, Ivan Wiryadi

\newpage

## Project Overview

The base aim for our project is to build an application (portal) using LLM based agents on top of **expense receipt**, called *Sticklet*. The agent is able to extract and store key information from the receipts and use the records to: 

1. Visualize trends and data, e.g. weekly or monthly expenses.
2. Discuss with the user about anything relating to their expenses.

## 1. Overview of Selected Agent Patterns

![Sticklet Architecture Overview](../assets/architecture_overview.png)

### 1.1. Human Reflection Pattern

The Human Reflection pattern in Sticklet enables users to validate and correct AI-processed information through the Streamlit interface. In `app.py`, users can review extracted receipt data (merchant name, date, items, prices), make corrections, and confirm before saving to the database. This pattern increases accuracy by allowing humans to correct mistakes in AI processing, which is particularly important for financial data where errors could lead to incorrect insights.

### 1.2. Tool/Agent Registry Pattern

The Tool/Agent Registry pattern is implemented in the `CoordinatorAgent` class which maintains a centralized registry of specialized agents and tools. The coordinator uses `_initialize_agents()` and `_get_agent()` methods to lazily initialize and retrieve specialized agents only when needed. Each specialized agent also has access to its required tools - for example, `ReceiptReaderAgent` has OCR and parsing tools, while `MonthlyReportAgent` has access to SQL tools. This pattern enables resource conservation, provides a clean API for agent access, and facilitates modular development.

### 1.3. Role-Based Agent Coordination Pattern

The Role-Based Agent Coordination pattern distributes specialized tasks to purpose-built agents while the `CoordinatorAgent` orchestrates their activities. Each agent has a distinct role:

- `ReceiptReaderAgent`: Extracts structured data from receipt images
- `MonthlyReportAgent`: Generates financial reports based on spending history
- `MarketAgent`: Retrieves and analyzes market information

The coordinator delegates specific tasks to these specialized agents through methods like `process_receipt()`, `gen_monthly_report()`, and `get_market_indicators()`. This pattern reduces complexity through separation of concerns, allows for specialized optimizations in each agent, and enables parallel development of different agent capabilities.

### 1.4. Self-Reflection Pattern

The Self-Reflection pattern is implemented in the `ReceiptReaderAgent` through the `_reflect_on_results()` method, which validates and potentially corrects extracted data. When processing receipts, the agent extracts data and then "reflects" on whether the results make sense. For example, it identifies generic merchant names like "receipt" or "store" and attempts to find more specific merchant names from the raw text. It also validates dates and item categories. This pattern improves data quality by identifying and correcting common errors, reducing the need for human intervention, and learning from past mistakes.

### 1.5. Retrieval Augmented Generation (RAG) Pattern

The RAG pattern enhances the agent's knowledge with external data from the SQLite database. The system uses `PurchaseMemory` to store structured purchase data and provides tools like `SQLQueryTool` to query this database. When users ask questions about their spending patterns, the agent can retrieve relevant transaction data to provide personalized responses rather than relying solely on its pre-trained knowledge. This pattern enables the foundation model to access domain-specific knowledge, provide personalized responses based on user data, and perform temporal analysis of spending patterns without needing to retrain the model.

## 2. Tool Comparison and Selection Rationale

To build Sticklet, a multimodal personal receipt management portal powered by LLM agents, we conducted a comparative evaluation of candidate tools across five core components: OCR, LLM reasoning, agent orchestration, memory, and front-end integration.

We considered traditional OCR tools such as Tesseract and PaddleOCR, but ultimately selected Mistral OCR due to its robust image-to-text performance and seamless integration with language models. Traditional OCR pipelines typically require a separate Key Information Extraction (KIE) step after text recognition, which introduces additional complexity and often suffers from lower stability and accuracy, especially with noisy or unstructured receipt layouts. In contrast, Vision-Language Models (VLMs) like Mistral can directly interpret the visual content of the image and extract structured information in one step, offering a more end-to-end and robust solution. Moreover, Mistral’s multimodal API handles cropped, tilted, or degraded receipt images more effectively than conventional OCR + KIE pipelines, reducing pre-processing overhead. The API is currently free to use, making it ideal for our course-level prototype. If needed, it can be easily replaced with other vision-capable LLMs such as GPT-4o, Gemini, or Claude in future extensions, ensuring long-term flexibility and portability.

For natural language understanding and reasoning, we adopted a hybrid approach using both OpenAI models (GPT-4, GPT-3.5) and Mistral LLMs. OpenAI’s models demonstrated strong performance in agent orchestration, task decomposition, and natural language summarization, making them the preferred choice for high-quality interactions and complex reasoning chains. However, we acknowledge that Mistral’s current capabilities still lag behind GPT-4, particularly in multi-step reasoning and instruction following. That said, Mistral offers free or low-cost inference, making it a valuable fallback option when cost or rate limits are a concern. To balance performance with affordability, we adopted a dual-model strategy: GPT-4 is prioritized for critical reasoning tasks where high fidelity is desired, while Mistral serves as a fallback model for routine processing or when operating under resource constraints. This setup allows us to maintain a high-quality user experience without exceeding budget limitations, while also ensuring modularity and future extensibility.

To persist and query purchase history, we selected LangChain’s memory components—specifically SimpleMemory and ReadOnlySharedMemory. LangChain is currently one of the most mature and actively maintained frameworks in the agentic ecosystem. It provides a rich set of tools for agent orchestration, memory management, and tool integration. Its well-documented and modular design allowed us to quickly build a context-aware system that supports reasoning across past purchases and user queries with minimal setup overhead.

For market data and financial news, we adopted a two-pronged strategy. Market data is retrieved using the Yahoo Finance API, which provides up-to-date stock prices and financial indicators. For financial news, we currently rely on the LLM’s built-in browsing or plugin capability to access and summarize real-time news content. This approach reduces integration complexity while leveraging the LLM’s language understanding to generate concise, user-friendly summaries from live sources.

Overall, our toolchain selection balances performance, extensibility, and developer productivity. We prioritized tools that are either free or cost-efficient, quick to implement, and compatible with future upgrades. Our goal is to rapidly deliver a functional MVP while ensuring that the architecture remains flexible and scalable for future enhancements in reasoning quality, model capabilities, or external data sources.


## 3. Conceptual Design and Use Cases
The core function of Sticklet is to scan and transform receipt images into structured data that augments the personal financial agent. Users are able to upload receipt images through the web interface, which is then processed to extract information such as merchant, transaction date, total amount, the items purchased, etc and store them into persistent database. Using these data, the agent can help to provide relevant information about the users expenses. 

### 3.1 Use Case: Natural Language Financial Queries
Users can interact with Sticklet through natural language questions about their spending habits and financial patterns. The `CoordinatorAgent` processes these queries by translating them into appropriate database operations using tools like `SQLQueryTool` and `InsightGeneratorTool`. The system can answer questions ranging from simple lookups ("How much did I spend at Trader Joe's?") to complex analyses ("How has the price of white rice that I bought changed over time?"). This enables users to gain insights about their finances without needing to know specialized query languages or spreadsheet operations.

### 3.2 Use Case: Monthly Reporting & Analysis
Sticklet generates comprehensive monthly reports that provide users with an overview of their spending patterns. The `MonthlyReportAgent` aggregates all transaction data for a specified month, calculates totals by category and merchant, identifies high-spend days, and generates narrative summaries using the Mistral API. These reports include both quantitative data visualizations (spending trends, category breakdowns) and qualitative analysis (patterns, anomalies, recommendations), giving users actionable insights about their financial behavior without requiring manual data compilation.

### 3.3 Use Case: Market Intelligence Integration
The Market Agent connects personal finance data with broader market context by tracking major market indices (S&P 500, Dow Jones, NASDAQ) and generating tailored market summaries. Users can view 7-day historical market data and receive AI-generated narratives that explain market movements. This integration helps users understand how external economic factors might impact their personal finances and make more informed decisions about future spending or investments.
