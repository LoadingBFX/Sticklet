# Research and Planning Report
Team 8 - Fanxing Bu, Ivan Wiryadi

## Project Overview

The base aim for our project is to build an application (portal) using LLM based agents on top of **expense receipt**, called *Sticklet*. The agent is able to extract and store key information from the receipts and use the records to: 

1. Visualize trends and data, e.g. weekly or monthly expenses.
2. Discuss with the user about anything relating to their expenses.


## 1. Overview of Selected Agent Patterns

### 1.1 Multi-Agent Pattern
The Multi-Agent pattern is central to our Sticklet system architecture, implemented through the `CoordinatorAgent` class coordinating specialized worker agents. This pattern:
- Centralizes user interactions through a single coordinator agent
- Distributes specialized tasks to purpose-built agents (ReceiptReader, MonthlyReport, Market)
- Also creates separation of concerns / modularity for maintainability and scalability

### 1.2 ReAct Pattern
The ReAct (Reasoning + Acting) pattern is implemented in the coordinator agent through LangChain's `create_react_agent` function:

```python
self.agent = create_react_agent(
    llm=self.llm,
    tools=self.tools,
    prompt=prompt
)
```

This pattern enables:
- Step-by-step reasoning before taking actions
- Explicit thought processes for improved transparency
- Dynamic planning based on interim results
- Better error handling through reasoning

The ReAct pattern, as implemented in LangChain, allows the agent to reason through financial queries in a loop of:
1. **Thought**: The agent considers what information it needs and what steps to take
2. **Action**: The agent decides which tool to use and what input to provide
3. **Observation**: The agent processes the tool's output
4. **Repeat** until the agent has enough information to answer the query

This pattern is particularly valuable for complex financial queries that require multiple steps of reasoning and tool use, such as analyzing spending patterns or identifying budget optimization opportunities.

### 1.3 Self-Reflection Pattern
The Self-Reflection pattern is implemented in the `ReceiptReaderAgent` through the `_reflect_on_results` method. Before the agent passess back the results to Coordinator, it attempt to self-correct the parsed results. For example, when the OCR produces generic merchant names like "receipt" or "store," the reflection mechanism attempts to find a more specific merchant name from the raw text.


### 1.3 Human-Reflection Pattern
While it may not exactly be human-reflection as described in [AGENT DESIGN PATTERN CATALOGUE], we utilize a design pattern to allow users correct any mistakes in the parsed receipt results through the interface. 


### 1.4 Tool Use Pattern
The Tool Use pattern enables our agents to perform specialized tasks by leveraging dedicated utility functions:
- `SQLQueryTool`: Executes structured queries against the purchase database
- `ReceiptProcessorTool`: Processes receipt images and extracts structured data
- `InsightGeneratorTool`: Generates financial insights from purchase history
Also, we leverage LangChain's wrappers to wrap other Agents as Tools for the `CoordinatorAgent` to use.

### 1.5 Prompt/Response Optimizer Pattern
This pattern is implemented through engineered system prompts by:
- Provides structured templates for agent responses
- Includes domain-specific knowledge in prompts
- Delivers consistent outputs across interactions
- Improves efficiency by reducing clarification loops

For example, the ReceiptParserTool uses a detailed system prompt with processing rules and expected output format to optimize the extraction process.

## 2. Tool Comparison and Selection Rationale

TBD


## 3. Conceptual Design and Use Cases

### 3.1 System Architecture

Sticklet implements a multi-agent architecture with the following components:

**CoordinatorAgent**: The central orchestrator that:
- Manages user interactions
- Delegates specialized tasks to appropriate agents
- Maintains consistent memory access
- Handles errors and state management

**ReceiptReaderAgent**: Specializes in extracting data from receipt images:
- Uses OCR to extract raw text
- Parses text into structured data
- Performs validation and correction
- Categorizes items and expenses

**MonthlyReportAgent**: Generates financial insights and reports:
- Aggregates monthly spending data
- Identifies spending patterns and trends
- Produces narrative summaries using LLMs
- Visualizes financial data

**MarketAgent**: Provides market data and news:
- Fetches current market indicators
- Retrieves historical price data
- Generates market summaries using LLMs
- Relates market trends to personal finance

**Streamlit Web App**: Provides the user interface for:
- Uploading and processing receipts
- Viewing transaction history
- Generating reports
- Getting market updates
- Asking questions about finances

### 3.2 Core Use Cases

**Use Case 1: Receipt Processing**
1. User uploads a receipt image
2. System performs OCR using Mistral API
3. System extracts structured data (merchant, date, items, amounts)
4. User verifies and adjusts extracted data if needed
5. System stores the validated receipt data in the database
6. System confirms successful storage and updates financial metrics

**Use Case 2: Financial Query Answering**
1. User asks a natural language question about their finances
2. Coordinator agent analyzes the query using ReAct pattern
3. System retrieves relevant purchase data through SQL queries
4. Agent generates a coherent and accurate response
5. System presents the answer to the user

**Use Case 3: Monthly Report Generation**
1. User requests a monthly spending report
2. System retrieves all purchases for the specified month
3. System aggregates data by merchant, category, and day
4. LLM generates a narrative report explaining spending patterns
5. System presents the report with visualizations to the user

**Use Case 4: Market Monitoring**
1. User navigates to the Market & News section
2. System fetches current market data from external sources
3. System retrieves 7-day historical data for major indices
4. System generates a narrative market summary using LLM
5. System presents market data and summary to the user
