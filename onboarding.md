# Agentic Project Onboarding Guide

Welcome to the Agentic Project! This document will help you understand our project structure, capabilities, and the technology choices we've made. By the end, you should have a good understanding of how everything fits together and be ready to contribute.

## Project Overview

This is a Multi-Agent Personal Financial Portal that uses AI agent design patterns to help users track and analyze their purchases. The system can:

1. Process receipt images using OCR (Optical Character Recognition)
2. Extract structured data from receipts (merchant, items, prices, etc.)
3. Store purchase history
4. Analyze spending patterns and provide financial insights
5. Answer natural language queries about purchase history

## Project Structure

The codebase follows a modular architecture organized as follows:

```
agentic-project/
├── app.py                 # Main application entry point
├── data/                  # Data storage directory
│   └── purchases.json     # Purchase history database
├── src/                   # Source code
│   ├── agents/            # Agent modules
│   │   ├── coordinator_agent.py    # Orchestrates other agents
│   │   └── receipt_reader_agent.py  # Processes receipt images
│   ├── tools/             # Tools used by agents
│   │   ├── memory_tools.py          # Tools for accessing memory
│   │   ├── receipt_processor_tool.py # Tool for processing receipts
│   │   └── receipt_tools.py         # Receipt OCR and parsing tools
│   └── utils/             # Utility modules
│       ├── image_utils.py            # Image processing utilities
│       └── memory.py                 # Purchase memory storage
├── streamlit_app/         # Streamlit web interface
│   └── app.py             # Streamlit application
└── tests/                 # Test suite
    ├── test_data/         # Test images and fixtures
    └── unit/              # Unit tests
```

## Core Components

### Agents

We use a multi-agent architecture where each agent has specific responsibilities:

1. **Coordinator Agent** (`src/agents/coordinator_agent.py`):
   - Acts as the main entry point for user interactions
   - Orchestrates other specialized agents
   - Handles natural language queries about purchases
   - Delegates specialized tasks to other agents
   - Uses OpenAI's GPT models for natural language understanding

2. **Receipt Reader Agent** (`src/agents/receipt_reader_agent.py`):
   - Extracts structured data from receipt images
   - Uses Mistral AI's OCR capabilities to read text from images
   - Implements the Tool Use pattern for leveraging LLM capabilities

### Tools

Tools are specialized components that agents use to perform specific tasks:

1. **Receipt Tools** (`src/tools/receipt_tools.py`):
   - `MistralOCRTool`: Extracts text from receipt images using Mistral's OCR
   - `ReceiptParserTool`: Converts raw text to structured receipt data

2. **Memory Tools** (`src/tools/memory_tools.py`):
   - `MemoryTool`: Provides access to purchase history
   - `InsightGeneratorTool`: Generates financial insights from purchase history

3. **Receipt Processor Tool** (`src/tools/receipt_processor_tool.py`):
   - Acts as a bridge between the receipt reader agent and memory
   - Processes receipts and stores results in purchase memory

### Memory

The memory system (`src/utils/memory.py`) stores and manages purchase history:

- Implements the Memory Pattern for persistence
- Uses data classes (`Purchase` and `PurchaseItem`) for type safety
- Provides filtering capabilities (by merchant, date, category)
- Integrates with LangChain's memory system for agent access

## Key Libraries and Why We Use Them

### LangChain

[LangChain](https://www.langchain.com/) is our primary framework for building LLM-powered applications. We use it because:

1. **Agent Architecture**: LangChain provides robust agent frameworks that enable LLMs to use tools, make decisions, and execute multi-step tasks
   - `AgentExecutor`: Manages agent execution and tool usage
   - `create_openai_functions_agent`: Creates OpenAI function-calling agents
   - `create_react_agent`: Creates ReAct-style agents for reasoning and action

2. **Memory Systems**: LangChain offers memory components that help maintain context
   - `ConversationBufferMemory`: Stores conversation history
   - `SimpleMemory` and `ReadOnlySharedMemory`: Let us share data between components

3. **Prompt Management**: LangChain's prompt templates make it easy to create consistent interactions with LLMs
   - `ChatPromptTemplate` and `MessagesPlaceholder`: Structure agent prompts
   - System messages and human messages: Create proper conversation context

4. **Tool Integration**: LangChain's tools framework makes it easy to extend agent capabilities
   - `BaseTool`: Base class for all our custom tools
   - Tool registration: Automatically makes tools available to agents

### Mistral AI

We use [Mistral AI](https://mistral.ai/) for:

1. **OCR Capabilities**: Extract text from images through their OCR model
2. **LLM Models**: Process extracted text and generate structured data
3. **Multi-modal Understanding**: Process both text and images in a single API call

### OpenAI

We use [OpenAI](https://openai.com/) models for:

1. **Natural Language Understanding**: Process user queries about their finances
2. **Agent Orchestration**: The coordinator agent uses OpenAI models for high-level reasoning
3. **Financial Insights**: Generate useful financial insights from purchase history

## Agent Design Patterns

Our system implements several agent design patterns:

1. **Coordinator Pattern**: The coordinator agent orchestrates specialized agents to solve complex tasks

2. **Tool Use Pattern**: Agents use specialized tools to extend their capabilities beyond just text generation

3. **Memory Pattern**: The system maintains persistent memory of purchase history and user interactions

4. **ReAct Pattern**: Agents follow a "Reasoning and Acting" cycle where they:
   - Think about what to do next
   - Choose an action (tool to use)
   - Observe the result
   - Plan the next step

## Workflow Examples

### Processing a Receipt

When a user submits a receipt image:

1. The coordinator agent receives the image path
2. It delegates to the receipt reader agent
3. The receipt reader uses OCR to extract text from the image
4. The extracted text is parsed into structured data
5. The structured purchase data is stored in memory
6. The purchase data is returned to the user

### Answering User Queries

When a user asks about their spending:

1. The coordinator agent processes the natural language query
2. It determines what information is needed
3. It uses the memory tool to access relevant purchase data
4. It formulates a helpful response based on the retrieved data
5. For complex insights, it may use the insight generator tool

## Getting Started

To set up your development environment:

1. Install dependencies: `pip install -r requirements.txt`
2. Set up environment variables:
   - `MISTRAL_API_KEY`: Your Mistral AI API key
   - `OPENAI_API_KEY`: Your OpenAI API key
3. Run the application: `python app.py`

