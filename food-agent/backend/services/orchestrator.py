from services.groq_service import extract_structured_order

EMPTY_ORDER_STATE = {
    "intent": None,
    "restaurant_preference": None,
    "items": [],
    "delivery_address_tag": None,
    "is_complete": False,
}

class Orchestrator:
    @staticmethod
    async def process(message: str, session: dict, conversation_history: list = []) -> dict:
        # 1. Load existing partial order state
        order_state_dict = session.get("orderState", {})
        
        current_state = {**EMPTY_ORDER_STATE}
        if order_state_dict and order_state_dict.get("intent"):
            current_state.update(order_state_dict)

        # 2. Call the LLM with full context
        llm_result = await extract_structured_order(
            message,
            conversation_history[-10:],
            current_state,
            session.get("latestScreenData")
        )

        # 3. Handle small talk / greetings
        if llm_result.get("intent") in ["SMALL_TALK", "GREETING"]:
            return {
                "reply": llm_result.get("reply") or "Hey there! 🍽️ I'm your food ordering assistant. Tell me what you'd like to eat!",
                "orderState": current_state,
                "isComplete": False,
                "finalPayload": None,
                "actionHint": "none"
            }

        # 4. Handle unclear intent
        if llm_result.get("intent") == "UNCLEAR":
            return {
                "reply": llm_result.get("clarification_question") or "I didn't quite catch that. Could you tell me what you'd like to order? For example: \"2 chicken biryani from Meghana Foods\"",
                "orderState": current_state,
                "isComplete": False,
                "finalPayload": None,
                "actionHint": "none"
            }

        # 5. Merge LLM extraction into accumulated state
        merged_state = Orchestrator._merge_state(current_state, llm_result)

        # 6. Check completeness
        if llm_result.get("is_complete") and len(merged_state.get("items", [])) > 0:
            final_payload = {
                "intent": merged_state.get("intent"),
                "data": {
                    "restaurant_preference": merged_state.get("restaurant_preference"),
                    "items": [
                        {
                            "name": item.get("name"),
                            "quantity": item.get("quantity", 1),
                            "customizations": item.get("customizations", []),
                            "action": item.get("action")
                        } for item in merged_state.get("items", [])
                    ],
                    "delivery_address_tag": merged_state.get("delivery_address_tag")
                }
            }

            return {
                "reply": llm_result.get("reply") or Orchestrator._build_confirmation_reply(final_payload),
                "orderState": {**merged_state, "is_complete": True},
                "isComplete": True,
                "finalPayload": final_payload,
                "actionHint": Orchestrator._map_intent_to_action(merged_state.get("intent"))
            }

        # 7. Not complete — return clarification question
        clarification = llm_result.get("clarification_question") or Orchestrator._generate_clarification(merged_state)

        return {
            "reply": clarification,
            "orderState": merged_state,
            "isComplete": False,
            "finalPayload": None,
            "actionHint": "clarifying",
            "missingSlots": llm_result.get("missing_slots") or Orchestrator._find_missing_slots(merged_state)
        }

    @staticmethod
    def reset_state() -> dict:
        return {**EMPTY_ORDER_STATE}

    @staticmethod
    def _merge_state(existing: dict, llm_result: dict) -> dict:
        merged = {**existing}

        if llm_result.get("intent") and llm_result.get("intent") != "UNCLEAR":
            merged["intent"] = llm_result.get("intent")

        data = llm_result.get("data", {})
        if data.get("restaurant_preference"):
            merged["restaurant_preference"] = data.get("restaurant_preference")

        if data.get("delivery_address_tag"):
            merged["delivery_address_tag"] = data.get("delivery_address_tag")

        if data.get("items"):
            if "items" not in merged:
                merged["items"] = []
                
            for new_item in data.get("items", []):
                if not new_item.get("name"):
                    continue

                # For MODIFY_CART with action=remove
                if new_item.get("action") == "remove":
                    merged["items"] = [
                        item for item in merged["items"]
                        if item.get("name", "").lower() != new_item.get("name", "").lower()
                    ]
                    continue

                # Check if item exists
                existing_idx = next(
                    (i for i, item in enumerate(merged["items"]) 
                     if item.get("name", "").lower() == new_item.get("name", "").lower()), 
                    -1
                )

                if existing_idx >= 0:
                    # Update existing
                    merged["items"][existing_idx]["quantity"] = new_item.get("quantity") or merged["items"][existing_idx].get("quantity", 1)
                    if new_item.get("customizations"):
                        merged["items"][existing_idx]["customizations"] = new_item.get("customizations")
                    if new_item.get("action"):
                        merged["items"][existing_idx]["action"] = new_item.get("action")
                else:
                    # Add new item
                    merged["items"].append({
                        "name": new_item.get("name"),
                        "quantity": new_item.get("quantity", 1),
                        "customizations": new_item.get("customizations", []),
                        "action": new_item.get("action")
                    })

        return merged

    @staticmethod
    def _find_missing_slots(state: dict) -> list:
        missing = []
        if not state.get("items") or len(state.get("items")) == 0:
            missing.append("items")
        return missing

    @staticmethod
    def _generate_clarification(state: dict) -> str:
        if not state.get("items") or len(state.get("items")) == 0:
            if state.get("restaurant_preference"):
                return f"Got it, you want to order from **{state.get('restaurant_preference')}**! 🍽️ What items would you like to add?"
            return "What would you like to order? Tell me the food items and I'll find the best options for you! 🔍"

        item_names = ", ".join([f"{i.get('quantity', 1)}× {i.get('name')}" for i in state.get("items", [])])

        if not state.get("restaurant_preference"):
            return f"I have **{item_names}** on the list. Any specific restaurant you'd like to order from, or should I find the best one? 🏪"

        return f"Almost there! I have **{item_names}** from **{state.get('restaurant_preference')}**. Shall I proceed to search and add these to your cart? Say \"confirm\" or add more items!"

    @staticmethod
    def _build_confirmation_reply(payload: dict) -> str:
        data = payload.get("data", {})
        items_desc = []
        for i in data.get("items", []):
            desc = f"**{i.get('quantity', 1)}× {i.get('name')}**"
            if i.get("customizations"):
                desc += f" ({', '.join(i.get('customizations'))})"
            items_desc.append(desc)
            
        items_str = "\n• ".join(items_desc)
        
        restaurant = f" from **{data.get('restaurant_preference')}**" if data.get("restaurant_preference") else ""

        intent_labels = {
            "SEARCH_AND_ADD": "🔍 Searching and adding to cart",
            "MODIFY_CART": "🛒 Updating your cart",
            "PLACE_ORDER": "✅ Placing your order",
        }
        intent_label = intent_labels.get(payload.get("intent"), "📝 Processing your order")

        return f"{intent_label}{restaurant}:\n\n• {items_str}\n\nWorking on it now... 🚀"

    @staticmethod
    def _map_intent_to_action(intent: str) -> str:
        mapping = {
            "SEARCH_AND_ADD": "search_and_add",
            "MODIFY_CART": "modify_cart",
            "PLACE_ORDER": "place_order"
        }
        return mapping.get(intent, "none")
