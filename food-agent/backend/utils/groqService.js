import dotenv from 'dotenv';
dotenv.config();
import Groq from 'groq-sdk';

const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

const SYSTEM_PROMPT = `You are an autonomous, end-to-end food ordering agent for Swiggy (swiggy.com).
Your primary objective is to understand the customer's intent to complete the entire food delivery transaction from start to finish.
When you receive a request for a food item or category (e.g., "Order biryani", "get me a biryani"), you MUST classify the intent as 'autonomous_order'.

ALWAYS respond with ONLY valid JSON — no extra text, no markdown fences:
{
  "intent": "greet | search | browse_menu | add_item | view_cart | confirm_order | cancel_order | small_talk | autonomous_order | unclear",
  "searchQuery": "the food or restaurant to search for, or null",
  "foodCategory": "the category of food the user wants to autonomously order (e.g. biryani, pizza), or null",
  "items": [
    { "name": "item name", "quantity": 1, "customizations": [], "action": "add | remove" }
  ],
  "deliveryType": "delivery | pickup | null",
  "address": "address string or null",
  "offerCode": "promo code or null",
  "clarificationNeeded": false,
  "clarificationQuestion": null,
  "reply": "short friendly reply to show the user"
}

Rules:
- "Order biryani" or "get me a biryani" → intent=autonomous_order, foodCategory="biryani"
- "search biryani" or "find pizza" → intent=search, searchQuery="biryani"
- "add 2 biryanis" → intent=add_item, items=[{name:"biryani",quantity:2}]
- "show cart" → intent=view_cart
- "confirm order" → intent=confirm_order
- Always set reply to a short, warm, natural message`;

export async function extractIntent(userMessage, conversationHistory = []) {
  const messages = [
    ...conversationHistory.slice(-6).map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content })),
    { role: 'user', content: userMessage }
  ];

  const response = await groq.chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'system', content: SYSTEM_PROMPT }, ...messages],
    temperature: 0.2,
    max_tokens: 500,
  });

  const raw = response.choices[0].message.content.trim().replace(/```json|```/g, '').trim();
  try { return JSON.parse(raw); }
  catch {
    return { intent: 'unclear', items: [], searchQuery: null, reply: "Could you rephrase that? Try 'search biryani' or 'add 2 dosas'." };
  }
}

export async function generateConfirmationMessage(cart, deliveryDetails) {
  const summary = cart.map(i => `${i.quantity}x ${i.itemName}`).join(', ');
  const r = await groq.chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [{ role: 'user', content: `Confirm this Swiggy order in 2 sentences: ${summary}. ${deliveryDetails?.address ? `Deliver to ${deliveryDetails.address}.` : ''} Ask them to confirm.` }],
    temperature: 0.7, max_tokens: 120,
  });
  return r.choices[0].message.content.trim();
}

export async function handleSmallTalk(message, history = []) {
  const r = await groq.chat.completions.create({
    model: 'llama-3.3-70b-versatile',
    messages: [
      { role: 'system', content: "You are a friendly Swiggy ordering assistant. Reply in 1-2 sentences and guide the user to search for food or restaurants." },
      ...history.slice(-4).map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user', content: m.content })),
      { role: 'user', content: message }
    ],
    temperature: 0.8, max_tokens: 100,
  });
  return r.choices[0].message.content.trim();
}
