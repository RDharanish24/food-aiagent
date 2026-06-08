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

        # Persist updated order state
        session_data["orderState"] = orchestrator_result.get("orderState")

        # ══════════════════════════════════════════════════════════════════════
        # PHASE 2: BROWSER EXECUTION WORKER
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
                
                # Update reply to indicate action starting
                if intent == "SEARCH_AND_ADD":
                    reply = f"🔍 Launching execution worker for **{data.get('restaurant_preference') or 'your items'}**...\n\n"
                elif intent == "MODIFY_CART":
                    reply = f"🛒 Launching execution worker to modify cart...\n\n"
                elif intent == "PLACE_ORDER":
                    reply = f"✅ Launching execution worker for checkout...\n\n"

                # Delegate the entire intent payload to the encapsulated Browser Execution Worker
                worker_response = await agent.execute_intent(final_payload)
                
                status = worker_response.get("status")
                current_cart = worker_response.get("current_cart", [])
                screenshot_base64 = worker_response.get("screenshot_path")
                error_message = worker_response.get("error_message")

                # Update the session cart
                if current_cart is not None:
                    # Convert to DB models
                    session_data["cart"] = []
                    for item in current_cart:
                        session_data["cart"].append(CartItem(
                            itemName=item.get("name"),
                            quantity=item.get("quantity", 1),
                            price=item.get("price"),
                            itemId=str(uuid.uuid4())
                        ).model_dump())
                    cart_updated = True

                # Process the outcome
                if status == "SUCCESS":
                    if intent == "SEARCH_AND_ADD":
                        added_names = ", ".join([i.get("name") for i in data.get("items", [])])
                        reply += f"✅ Successfully completed search and add for: **{added_names}**"
                        session_data["status"] = "ordering"
                    elif intent == "MODIFY_CART":
                        reply += "✅ Cart modifications successful!"
                    elif intent == "PLACE_ORDER":
                        reply += "🎉 Order placed successfully! You will receive confirmation on Swiggy."
                        session_data["status"] = "completed"
                        session_data["orderState"] = Orchestrator.reset_state()
                        
                        # Log order
                        order_logs_coll = get_order_logs_collection()
                        await order_logs_coll.insert_one(OrderLogDoc(
                            sessionId=session_id,
                            items=[CartItem(**c) for c in session_data["cart"]],
                            status="placed",
                            agentActions=agent.action_log
                        ).model_dump())
                else:
                    reply += f"❌ Execution Worker Failed: {error_message}"

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
