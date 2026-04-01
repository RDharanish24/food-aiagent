# 🍽️ Swiggy AI Ordering Agent

An AI-powered agent that automates food ordering on **swiggy.com** through natural language conversation.

## Architecture

```
User (Chat UI)
    ↓  Natural language
React Frontend (Vite)
    ↓  REST API
Express Backend (Node.js)
    ├── Groq LLaMA 3.3  → Intent extraction (add_item, remove_item, confirm_order, etc.)
    ├── Playwright Agent → Automates browser on swiggy.com
    └── MongoDB          → Sessions, conversations, order logs
```

## Quick Start

### Prerequisites
- Node.js 18+
- MongoDB running locally (`mongod`)
- Groq API key → https://console.groq.com

---

### 1. Backend Setup

```bash
cd backend
cp .env.example .env        # add your GROQ_API_KEY
npm install
npx playwright install chromium   # one-time browser install
npm run dev
```

Backend runs on: http://localhost:5000

---

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on: http://localhost:5173

---

## Features

| Feature | Description |
|---|---|
| 🤖 Natural Language | "Add 2 biryanis, extra spicy, no onion" |
| 🌐 Browser Automation | Playwright controls real swiggy.com |
| 🛒 Cart Management | Add, remove, update quantities |
| 📸 Live Screenshots | See what the agent is doing |
| 🚚 Delivery Address | Set address automatically |
| 🎁 Offer Codes | Apply promo codes automatically |
| 🎤 Voice Input | Speak your order (Chrome/Edge) |
| 📊 Order Logs | Full MongoDB audit trail |
| ⚠️ Error Handling | Out-of-stock, item not found, etc. |

## Example Conversations

```
User: "Search for Pizza Hut on Swiggy"
Agent: 🌐 Navigating to Pizza Hut...

User: "Add 1 Margherita pizza"
Agent: ✅ Added Margherita pizza to your cart!

User: "I want home delivery to 42 Anna Nagar, Chennai"
Agent: 🚚 Delivery address set!

User: "Apply offer code SWIGGY50"
Agent: 🎉 Offer code applied!

User: "Confirm my order"
Agent: ✅ Proceeding to checkout...
```

## API Endpoints

```
POST /api/chat              → Send message, get AI response + agent action
GET  /api/chat/session/:id  → Get session state
GET  /api/chat/orders       → List all order logs
DELETE /api/chat/session/:id → End session
GET  /api/health            → Server health check
```

## Project Structure

```
food-agent/
├── backend/
│   ├── agents/webAgent.js       ← Playwright automation for Swiggy
│   ├── models/index.js          ← MongoDB schemas
│   ├── routes/chat.js           ← API + orchestration
│   ├── utils/groqService.js     ← Groq LLaMA intent extraction
│   └── server.js
└── frontend/
    └── src/
        ├── App.jsx
        ├── components/
        └── utils/api.js
```

## Note on Swiggy Automation

Swiggy is a dynamic React app. The Playwright agent:
- Bypasses bot detection with a real Chrome user-agent
- Handles location popups automatically
- Uses Swiggy-specific data-testid selectors
- Supports customization modals for variants (size, spice level, etc.)

You must be **logged into Swiggy** in the browser session for checkout to work.
To inject a saved session, export cookies from a logged-in Chrome and load them via Playwright's `context.addCookies()`.
