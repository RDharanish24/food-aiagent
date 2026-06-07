import json
from groq import AsyncGroq
from core.config import settings

groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)

ORCHESTRATOR_SYSTEM_PROMPT = """You are the Orchestrator Brain for an Autonomous Food Ordering Agent on Swiggy.
Your job is to analyze user text, understand their order intent, and extract structured data.

You MUST understand:
- Slang & abbreviations: "briyani", "biriyani" = biryani; "xtra" = extra; "pyaaz"/"pyaz" = onion
- Bilingual (Hindi/English): "ek plate momos de do" = 1 plate momos; "do biryani chahiye" = 2 biryani
- Quantities: "a couple" = 2; "few" = 3; "half dozen" = 6; no number = 1
- Customizations: "no onion", "extra cheese", "less spicy", "jain", "without garlic"
- Multi-item: "2 biryani and 1 naan with butter" = [{"name":"biryani", "quantity":2}, {"name":"naan", "quantity":1, "customizations":["butter"]}]
- Pronouns: resolve "it", "that", "the same thing" from conversation history

INTENT CLASSIFICATION:
- SEARCH_AND_ADD: User wants to find food/restaurant AND add items to cart. This is the default for new orders.
- MODIFY_CART: User wants to change quantity, remove items, swap items, or update customizations on existing cart items.
- PLACE_ORDER: User explicitly wants to confirm/checkout/place the current order ("confirm", "place order", "checkout", "that's all", "done").
- SMALL_TALK: Greeting, general question, chit-chat, not food-related.
- GREETING: "hi", "hello", "hey", "yo".
- UNCLEAR: Cannot determine intent — ask for clarification.

You will receive:
1. The user's current message
2. Recent conversation history
3. The current accumulated orderState (partially filled slots from previous turns)
4. Current screen/UI context (search results or menu items visible)

RESPOND WITH ONLY VALID JSON (no markdown, no extra text):
{
  "intent": "SEARCH_AND_ADD | MODIFY_CART | PLACE_ORDER | SMALL_TALK | GREETING | UNCLEAR",
  "is_complete": true,
  "data": {
    "restaurant_preference": "string or null",
    "items": [
      {
        "name": "string",
        "quantity": 1,
        "customizations": ["string"],
        "action": "add | remove | update"
      }
    ],
    "delivery_address_tag": "string or null"
  },
  "missing_slots": ["items", "restaurant_preference"],
  "clarification_question": "string or null",
  "reply": "short friendly message to show the user"
}

RULES:
1. "is_complete" = true ONLY when the user's order intent is fully clear with at least one item specified.
2. If the user says just a food name without specifying a restaurant, set is_complete=true — we will search for the best restaurant.
3. If the user says "from X" or names a restaurant, fill restaurant_preference.
4. For PLACE_ORDER, is_complete=true if there are items in the current orderState.
5. For MODIFY_CART, set action="remove" to delete items, action="update" to change quantity/customizations.
6. For SMALL_TALK/GREETING, set is_complete=false and provide a friendly reply.
7. If ambiguous (e.g., "I want something spicy"), set is_complete=false and ask what specific item.
8. ALWAYS set "reply" to a short, warm, natural message.
9. When you see the accumulated orderState has items, and the user provides a restaurant, merge them — set is_complete=true."""

async def extract_structured_order(user_message: str, conversation_history: list = [], current_order_state: dict = {}, screen_context: dict = None) -> dict:
    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM_PROMPT}
    ]

    for msg in conversation_history[-10:]:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": msg.get("content")})

    if current_order_state and (current_order_state.get("intent") or current_order_state.get("items")):
        messages.append({
            "role": "system",
            "content": f"CURRENT ACCUMULATED ORDER STATE (from previous turns):\n{json.dumps(current_order_state, indent=2)}\n\nMerge the user's new input into this state. Do not discard previously accumulated items unless the user explicitly removes them."
        })

    if screen_context:
        messages.append({
            "role": "system",
            "content": f"CURRENT SCREEN CONTEXT (visible search results or menu items):\n{json.dumps(screen_context)}"
        })

    messages.append({"role": "user", "content": user_message})

    try:
        response = await groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.1,
            max_tokens=600,
        )
        
        raw_content = response.choices[0].message.content.strip()
        # Remove markdown formatting if present
        raw_content = raw_content.replace('```json', '').replace('```', '').strip()
        
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError:
            print("[ORCHESTRATOR] LLM returned non-JSON:", raw_content)
            return {
                "intent": "UNCLEAR",
                "is_complete": False,
                "data": {"restaurant_preference": None, "items": [], "delivery_address_tag": None},
                "missing_slots": ["items"],
                "clarification_question": "I didn't quite understand that. Could you tell me what you'd like to order?",
                "reply": raw_content
            }
            
    except Exception as e:
        print("[ORCHESTRATOR] Groq API call failed:", str(e))
        return {
            "intent": "UNCLEAR",
            "is_complete": False,
            "data": {"restaurant_preference": None, "items": [], "delivery_address_tag": None},
            "missing_slots": [],
            "clarification_question": None,
            "reply": "⚠️ I'm having a moment — could you try again?"
        }

async def handle_small_talk(message: str, history: list = []) -> str:
    messages = [
        {"role": "system", "content": "You are a friendly Swiggy ordering assistant. Reply in 1-2 sentences and guide the user to search for food or restaurants."}
    ]
    for msg in history[-4:]:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        messages.append({"role": role, "content": msg.get("content")})
    messages.append({"role": "user", "content": message})
    
    response = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.8,
        max_tokens=100,
    )
    return response.choices[0].message.content.strip()

async def generate_confirmation_message(cart_items: list, delivery_details: dict = None) -> str:
    prompt = "Format this order into a natural, friendly confirmation message:\n\nItems:\n"
    for item in cart_items:
        prompt += f"- {item.get('quantity', 1)}x {item.get('itemName')}\n"
    
    if delivery_details:
        prompt += f"\nDelivering to: {delivery_details.get('address')} at {delivery_details.get('time')}"
        
    messages = [
        {"role": "system", "content": "You are a helpful food ordering assistant. Create a brief, friendly confirmation message for the following order. End by asking the user to confirm the checkout."},
        {"role": "user", "content": prompt}
    ]
    
    response = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.7,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()
