# ManageOrders.ai

**An Agentic AI-powered order management system that lets users save, track, and manage orders using natural language.**

## 1. Why?

Managing online orders usually requires switching between different shopping apps, emails, tracking pages, and delivery platforms.

**ManageOrders.ai** provides a single AI-powered interface where users can simply describe an order and ask questions about it.

Instead of manually entering every order detail, the system can **understand an order from natural language or an order-confirmation message, extract the relevant information, save it, and later track and manage it through AI agents and tools.**

The project demonstrates how **Agentic AI can be used to perform real application actions instead of only generating text.**

---

## 2. How It Works

### Save an Order

There are two ways to add an order.

### A. Describe the Order

The user can simply tell the AI:

> "I ordered a Sony WH-1000XM6 from Amazon for ₹29,999. It should arrive on November 20th."

The agent:

```text
User Description
      ↓
AI Agent
      ↓
Extract Order Information
      ↓
Validate / Structure Data
      ↓
Save Order
      ↓
Database
```

The system extracts information such as:

- Product
- Order ID
- Seller
- Price
- Order date
- Delivery date
- Delivery address
- Tracking information
- Order status

---

### B. Paste Order Confirmation

Users can also **paste the complete order-confirmation message/email**.

For example:

> Order #123456 confirmed.  
> Sony WH-1000XM6  
> Total: ₹29,999  
> Expected delivery: November 20  
> Tracking ID: XXXXX

The agent reads the message, identifies the relevant information, converts it into structured order data, and saves it to the database.

```text
Order Confirmation
        ↓
      Agent
        ↓
Information Extraction
        ↓
Structured Order
        ↓
      Database
```

This means the user does not need to manually fill out a form.

---

## 3. Features

### 🤖 Natural Language Order Management

Users can interact with their orders conversationally.

Examples:

> "Show my orders arriving this week."

> "Where is my latest order?"

> "Show me all delayed orders."

> "What did I order from Amazon last month?"

---

### 📦 Intelligent Order Saving

Orders can be created from:

- Natural-language descriptions
- Order confirmation messages
- Structured information extracted by the agent

The AI converts unstructured information into structured order data before saving it.

---

### 📍 Automatic Order Tracking

The system can use **tools to retrieve live tracking information**.

For example:

```text
User
 │
 │ "Where is my Sony headphones order?"
 ▼
AI Agent
 │
 ├── Find order
 │
 ├── Identify tracking information
 │
 ├── Call tracking tool
 │
 └── Get latest location/status
 ▼
User
```

The agent can therefore retrieve the **latest available shipment status/location** rather than relying only on the information stored when the order was created.

---

### 🔧 Tool Calling

The agent can decide when external/application tools are required.

Examples:

```text
Search Orders
Get Order Details
Track Shipment
Update Order
Save Order
```

The LLM decides **which tool is needed based on the user's request**, executes the tool, and uses the result to formulate the response.

---

## 4. Agentic Architecture

The core of ManageOrders.ai is an **agentic workflow built with LangGraph and LangChain**.

```text
                         USER
                          │
                          ▼
                  ┌───────────────┐
                  │   AI AGENT    │
                  │   LangGraph   │
                  └───────┬───────┘
                          │
                 Understand Intent
                          │
                          ▼
                 Decide Next Action
                          │
            ┌─────────────┼─────────────┐
            ▼             ▼             ▼
       Save Order     Search Order   Track Order
            │             │             │
            ▼             ▼             ▼
        Save Tool      Query Tool    Tracking Tool
            │             │             │
            └─────────────┼─────────────┘
                          ▼
                    Application
                       Data
                          │
                          ▼
                   Supabase / DB
```

### Agentic Flow

The important part is that the LLM is not simply generating a response.

It can:

1. **Understand the user's intent**
2. **Determine what needs to be done**
3. **Select the appropriate tool**
4. **Execute the tool**
5. **Use the returned information**
6. **Continue reasoning if another action is required**
7. **Return the final result to the user**

For example:

```text
"Where is my Amazon order?"

        ↓

Agent identifies order

        ↓

Find tracking information

        ↓

Call tracking tool

        ↓

Receive latest shipment location

        ↓

Generate response
```

This makes ManageOrders.ai an **action-oriented Agentic AI application rather than a traditional chatbot.**

---

## Tech Stack

**Python · LangGraph · LangChain · LLM · Tool Calling · Supabase PostgreSQL · Docker · Google Cloud**