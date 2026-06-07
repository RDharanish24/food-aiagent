import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from core.database import get_sessions_collection, get_conversations_collection, get_order_logs_collection
from models.schemas import (
    ChatRequest, LoginPhoneRequest, LoginOtpRequest, NavigateRequest, ResetOrderRequest,
    SessionDoc, ConversationDoc, MessageDoc, OrderLogDoc, CartItem
)
from services.groq_service import handle_small_talk, generate_confirmation_message
from services.orchestrator import Orchestrator
from agents.web_agent import create_agent, get_agent, destroy_agent

router = APIRouter()

@router.post("")
async def chat_endpoint(req: ChatRequest):
    if not req.message:
        raise HTTPException(status_code=400, detail="Message required")

    session_id = req.sessionId or str(uuid.uuid4())
    
    sessions_coll = get_sessions_collection()
    convs_coll = get_conversations_collection()

    try:
        # Load or create session
        session_data = await sessions_coll.find_one({"sessionId": session_id})
        if not session_data:
            session_doc = SessionDoc(sessionId=session_id)
            session_data = session_doc.model_dump()
            await sessions_coll.insert_one(session_data)
        else:
            session_data.pop("_id", None)
            
        # Load or create conversation
        conv_data = await convs_coll.find_one({"sessionId": session_id})
        if not conv_data:
            conv_doc = ConversationDoc(sessionId=session_id)
            conv_data = conv_doc.model_dump()
            await convs_coll.insert_one(conv_data)
        else:
            conv_data.pop("_id", None)

        # Add user message to conversation history
        user_msg = MessageDoc(role="user", content=req.message)
        conv_data["messages"].append(user_msg.model_dump())

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 1: ORCHESTRATOR BRAIN — NLP + Slot Filling
        # ══════════════════════════════════════════════════════════════════════
        orchestrator_result = await Orchestrator.process(
            req.message,
            session_data,
            conv_data["messages"][-10:]
        )

        reply = orchestrator_result.get("reply")
        screenshot_base64 = None
        cart_updated = False
        search_results = None
        agent_result = None

        # Persist updated order state
        session_data["orderState"] = orchestrator_result.get("orderState")

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 2: If orchestrator emits a complete payload → dispatch to agent
        # ══════════════════════════════════════════════════════════════════════
        is_complete = orchestrator_result.get("isComplete")
        final_payload = orchestrator_result.get("finalPayload")

        if is_complete and final_payload:
            agent = get_agent(session_id)

            if not agent or not agent.is_logged_in:
                reply = "⚠️ Please log in with your Swiggy account first! Enter your phone number to get started."
            else:
                intent = final_payload.get("intent")
                data = final_payload.get("data", {})
                
                # ── SEARCH_AND_ADD ──────────────────────────────────────────────
                if intent == "SEARCH_AND_ADD":
                    search_query = data.get("restaurant_preference") or (data.get("items")[0].get("name") if data.get("items") else None) or req.message
                    reply = f"🔍 Searching Swiggy for **\"{search_query}\"**...\n\n"
                    
                    search_res = await agent.search_food(search_query)
                    screenshot_base64 = search_res.get("screenshot")
                    search_results = search_res.get("results")
                    session_data["latestScreenData"] = search_results

                    if not search_res.get("success") or not search_results:
                        reply += f"😕 No results found for \"{search_query}\". Try a different name!"
                    else:
                        reply += f"Found **{len(search_results)} results**!"

                        if data.get("restaurant_preference"):
                            target_restaurant = next((r for r in search_results if r.get("type") == "restaurant" and r.get("url")), None)
                            if target_restaurant:
                                nav_res = await agent.navigate_to_restaurant(target_restaurant["url"])
                                if nav_res.get("success"):
                                    add_results = []
                                    for item in data.get("items", []):
                                        add_res = await agent.add_item_to_cart(
                                            item.get("name"),
                                            item.get("quantity", 1),
                                            item.get("customizations", [])
                                        )
                                        add_results.append({"item": item.get("name"), **add_res})
                                        if add_res.get("success"):
                                            session_data["cart"].append(CartItem(
                                                itemName=item.get("name"),
                                                quantity=item.get("quantity", 1),
                                                customizations=item.get("customizations", []),
                                                price=None,
                                                itemId=str(uuid.uuid4())
                                            ).model_dump())
                                            screenshot_base64 = add_res.get("screenshot")

                                    ok_items = [r["item"] for r in add_results if r.get("success")]
                                    failed_items = [r["item"] for r in add_results if not r.get("success")]

                                    if ok_items:
                                        reply = f"✅ Added **{', '.join(ok_items)}** to your cart from **{data.get('restaurant_preference')}**!"
                                        cart_updated = True
                                        session_data["status"] = "ordering"
                                    if failed_items:
                                        reply += f"\n⚠️ Couldn't find: **{', '.join(failed_items)}**"
                                else:
                                    reply += "\n❌ Couldn't open restaurant menu."
                                    screenshot_base64 = nav_res.get("screenshot")
                            else:
                                reply += f"\n❌ Could not find a link for **{data.get('restaurant_preference')}**."
                        else:
                            reply += " Tap a restaurant to open its menu, or tell me which one you prefer!"
                            agent_result = {"type": "search", "results": search_results}

                # ── MODIFY_CART ─────────────────────────────────────────────────
                elif intent == "MODIFY_CART":
                    mod_results = []
                    for item in data.get("items", []):
                        if item.get("action") == "remove" or item.get("quantity") == 0:
                            session_data["cart"] = [c for c in session_data["cart"] if c.get("itemName").lower() != item.get("name").lower()]
                            mod_results.append({"item": item.get("name"), "action": "removed"})
                        else:
                            existing = next((c for c in session_data["cart"] if c.get("itemName").lower() == item.get("name").lower()), None)
                            if existing:
                                existing["quantity"] = item.get("quantity") or existing.get("quantity")
                                if item.get("customizations"):
                                    existing["customizations"] = item.get("customizations")
                                mod_results.append({"item": item.get("name"), "action": "updated"})

                    cart_updated = len(mod_results) > 0
                    if mod_results:
                        summary = "\n".join([f"• **{r['item']}** → {r['action']}" for r in mod_results])
                        reply = f"🛒 Cart updated!\n\n{summary}"
                    else:
                        reply = "Hmm, I couldn't find those items in your cart. Check what's there with \"show cart\"."

                # ── PLACE_ORDER ──────────────────────────────────────────────────
                elif intent == "PLACE_ORDER":
                    if not session_data.get("cart"):
                        reply = "Your cart is empty! Add some items first. 🍽️"
                    else:
                        confirm_msg = await generate_confirmation_message(session_data["cart"], session_data.get("deliveryDetails"))
                        reply = confirm_msg
                        session_data["status"] = "confirming"

                        checkout = await agent.proceed_to_checkout()
                        screenshot_base64 = checkout.get("screenshot")

                        if checkout.get("success"):
                            order_logs_coll = get_order_logs_collection()
                            await order_logs_coll.insert_one(OrderLogDoc(
                                sessionId=session_id,
                                items=[CartItem(**c) for c in session_data["cart"]],
                                status="placed",
                                agentActions=agent.action_log
                            ).model_dump())
                            
                            session_data["status"] = "completed"
                            reply += "\n\n✅ **Order placed!** You'll get a confirmation on your Swiggy app."
                            session_data["orderState"] = Orchestrator.reset_state()

        # ── Persist & respond ──
        session_data["updatedAt"] = datetime.utcnow()
        await sessions_coll.replace_one({"sessionId": session_id}, session_data)

        assistant_msg = MessageDoc(role="assistant", content=reply)
        conv_data["messages"].append(assistant_msg.model_dump())
        conv_data["updatedAt"] = datetime.utcnow()
        await convs_coll.replace_one({"sessionId": session_id}, conv_data)

        return {
            "sessionId": session_id,
            "reply": reply,
            "cart": session_data.get("cart"),
            "status": session_data.get("status"),
            "screenshot": screenshot_base64,
            "cartUpdated": cart_updated,
            "searchResults": search_results,
            "intent": final_payload.get("intent") if final_payload else (session_data.get("orderState", {}).get("intent")),
            "orderState": session_data.get("orderState"),
            "isComplete": is_complete,
            "missingSlots": orchestrator_result.get("missingSlots", []),
            "actionHint": orchestrator_result.get("actionHint", "none")
        }

    except Exception as e:
        print("[CHAT ERROR]", str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login/phone")
async def login_phone(req: LoginPhoneRequest):
    try:
        agent = get_agent(req.sessionId)
        if not agent:
            agent = await create_agent(req.sessionId)

        result = await agent.enter_phone(req.phone)
        result["message"] = "OTP sent to your number!" if result.get("success") else result.get("error")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login/otp")
async def login_otp(req: LoginOtpRequest):
    try:
        agent = get_agent(req.sessionId)
        if not agent:
            raise HTTPException(status_code=400, detail="Session not found. Please restart.")

        result = await agent.enter_otp(req.otp)
        
        if result.get("success"):
            sessions_coll = get_sessions_collection()
            await sessions_coll.update_one(
                {"sessionId": req.sessionId}, 
                {"$set": {"status": "active"}}, 
                upsert=True
            )
            
        result["message"] = "✅ Logged in successfully!" if result.get("success") else (result.get("error") or "Invalid OTP")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/navigate")
async def navigate(req: NavigateRequest):
    try:
        agent = get_agent(req.sessionId)
        if not agent:
            raise HTTPException(status_code=400, detail="Session not found")
            
        result = await agent.navigate_to_restaurant(req.url)
        if result.get("success") and result.get("menuItems"):
            sessions_coll = get_sessions_collection()
            await sessions_coll.update_one(
                {"sessionId": req.sessionId}, 
                {"$set": {"latestScreenData": result.get("menuItems")}}
            )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    try:
        sessions_coll = get_sessions_collection()
        convs_coll = get_conversations_collection()
        
        session_data = await sessions_coll.find_one({"sessionId": session_id})
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
            
        conv_data = await convs_coll.find_one({"sessionId": session_id})
        agent = get_agent(session_id)
        
        session_data.pop("_id", None)
        if conv_data:
            conv_data.pop("_id", None)
            
        return {
            "sessionId": session_id,
            "cart": session_data.get("cart", []),
            "status": session_data.get("status", "active"),
            "deliveryDetails": session_data.get("deliveryDetails"),
            "messages": conv_data.get("messages", []) if conv_data else [],
            "isLoggedIn": agent.is_logged_in if agent else False
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/order-state/{session_id}")
async def get_order_state(session_id: str):
    try:
        sessions_coll = get_sessions_collection()
        session_data = await sessions_coll.find_one({"sessionId": session_id})
        
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return {
            "sessionId": session_id,
            "orderState": session_data.get("orderState") or Orchestrator.reset_state()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset-order")
async def reset_order(req: ResetOrderRequest):
    try:
        fresh_state = Orchestrator.reset_state()
        sessions_coll = get_sessions_collection()
        await sessions_coll.update_one(
            {"sessionId": req.sessionId},
            {"$set": {"orderState": fresh_state}}
        )
        return {"success": True, "orderState": fresh_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/orders")
async def get_orders():
    try:
        order_logs_coll = get_order_logs_collection()
        cursor = order_logs_coll.find().sort("placedAt", -1).limit(50)
        logs = await cursor.to_list(length=50)
        for log in logs:
            log.pop("_id", None)
        return logs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    try:
        await destroy_agent(session_id)
        sessions_coll = get_sessions_collection()
        await sessions_coll.delete_one({"sessionId": session_id})
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/debug/{session_id}")
async def debug_agent(session_id: str):
    try:
        agent = get_agent(session_id)
        if not agent:
            raise HTTPException(status_code=404, detail="No agent for this session")
            
        screenshot = await agent.take_screenshot()
        url = agent.page.url if agent.page else "unknown"
        return {"screenshot": screenshot, "url": url, "isLoggedIn": agent.is_logged_in}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
