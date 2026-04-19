import express from 'express';
import { v4 as uuidv4 } from 'uuid';
import { Session, Conversation, OrderLog } from '../models/index.js';
import { extractIntent, generateConfirmationMessage, handleSmallTalk } from '../utils/groqService.js';
import { createAgent, destroyAgent, getAgent } from '../agents/webAgent.js';

const router = express.Router();

// ── POST /api/chat ────────────────────────────────────────────────────────────
router.post('/', async (req, res) => {
  const { message, sessionId: existingSessionId } = req.body;
  if (!message) return res.status(400).json({ error: 'Message required' });

  const sessionId = existingSessionId || uuidv4();

  try {
    let session = await Session.findOne({ sessionId });
    if (!session) session = new Session({ sessionId });

    let conversation = await Conversation.findOne({ sessionId });
    if (!conversation) conversation = new Conversation({ sessionId, messages: [] });

    conversation.messages.push({ role: 'user', content: message });

    const intentData = await extractIntent(message, conversation.messages.slice(-8), session.latestScreenData);

    let reply = '';
    let agentResult = null;
    let screenshotBase64 = null;
    let cartUpdated = false;
    let searchResults = null;

    if (intentData.clarificationNeeded) {
      reply = intentData.clarificationQuestion;
      conversation.messages.push({ role: 'assistant', content: reply });
      await conversation.save();
      return res.json({ sessionId, reply, cart: session.cart, status: session.status, intent: intentData.intent });
    }

    switch (intentData.intent) {
      case 'greet':
      case 'small_talk': {
        reply = await handleSmallTalk(message, conversation.messages.slice(-6));
        break;
      }
      // ── AUTONOMOUS ORDER ──────────────────────────────────────────────────
      case 'autonomous_order': {
        const agent = getAgent(sessionId);
        if (!agent || !agent.isLoggedIn) {
          reply = "⚠️ Please log in with your Swiggy account first! Enter your phone number to get started.";
          break;
        }

        const category = (intentData.foodCategory || intentData.searchQuery || message).toLowerCase().trim();
        
        // 1. Reference User Preferences
        const USER_PREFERENCES = {
          "biryani": { restaurant: "SS Hyderabad Biryani", item: "Chicken Dum Biryani", qty: 1 },
          "pizza": { restaurant: "Domino's Pizza", item: "Margherita", qty: 1 },
          "burger": { restaurant: "Burger King", item: "Crispy Veg Burger", qty: 1 }
        };

        // Find match in preferences or fallback
        const prefMatch = Object.entries(USER_PREFERENCES).find(([key, val]) => category.includes(key) || category.includes(val.restaurant.toLowerCase()) || category.includes(val.item.toLowerCase()));
        const pref = prefMatch ? prefMatch[1] : { restaurant: category, item: category, qty: 1 };

        try {
          // 2. Search & Locate
          const searchRes = await agent.searchFood(pref.restaurant);
          if (!searchRes.success || !searchRes.results || searchRes.results.length === 0) {
            reply = `❌ Could not find restaurant: ${pref.restaurant}`;
            screenshotBase64 = searchRes.screenshot;
            break;
          }

          // Find the exact restaurant URL
          const targetRestaurant = searchRes.results.find(r => r.type === 'restaurant' && r.url);
          if (!targetRestaurant) {
            reply = `❌ Could not find a valid link for restaurant: ${pref.restaurant}`;
            screenshotBase64 = searchRes.screenshot;
            break;
          }

          const navRes = await agent.navigateToRestaurant(targetRestaurant.url);
          if (!navRes.success) {
            reply = `❌ Failed to open restaurant menu for ${pref.restaurant}.`;
            screenshotBase64 = navRes.screenshot;
            break;
          }

          // 3. Add to Cart
          const addRes = await agent.addItemToCart(pref.item, pref.qty);
          if (!addRes.success) {
            reply = `❌ Failed to add item to cart: ${addRes.error || 'Out of stock'}`;
            screenshotBase64 = addRes.screenshot;
            break;
          }

          session.cart.push({ itemName: pref.item, quantity: pref.qty, customizations: [], price: null, itemId: uuidv4() });
          cartUpdated = true;
          
          // 4. Proceed to Checkout
          const cartRes = await agent.getCartContents();
          if (cartRes.success && cartRes.items.length > 0) {
               const checkoutRes = await agent.proceedToCheckout();
               screenshotBase64 = checkoutRes.screenshot;
               if (checkoutRes.success) {
                   reply = `✅ **Autonomous Order Complete!**\nReached checkout for your **${pref.item}** from **${pref.restaurant}**.\nYour total is **${cartRes.total}**.\n\nPlease confirm to place the final order.`;
                   session.status = 'confirming';
               } else {
                   reply = `❌ Failed to proceed to checkout.`;
               }
          } else {
               reply = `❌ Cart is empty.`;
          }
          
        } catch (e) {
             reply = `❌ Error during autonomous order: ${e.message}`;
        }
        break;
      }

      // ── SEARCH ──────────────────────────────────────────────────────────
      case 'search':
      case 'browse_menu': {
        const agent = getAgent(sessionId);
        if (!agent || !agent.isLoggedIn) {
          reply = "⚠️ Please log in with your Swiggy account first! Enter your phone number to get started.";
          break;
        }
        const query = intentData.searchQuery || intentData.items?.[0]?.name || message;
        reply = `🔍 Searching Swiggy for **"${query}"**...`;

        const result = await agent.searchFood(query);
        screenshotBase64 = result.screenshot;
        searchResults = result.results;
        session.latestScreenData = result.results;

        if (result.results?.length > 0) {
          reply = `🔍 Found **${result.results.length} results** for "${query}" on Swiggy! Tap a restaurant to open its menu, or say "add [item name]" to order.`;
        } else {
          reply = `😕 No results found for "${query}". Try a different search term!`;
        }
        agentResult = { type: 'search', results: result.results };
        break;
      }

      // ── ADD ITEM ─────────────────────────────────────────────────────────
      case 'add_item': {
        const agent = getAgent(sessionId);
        if (!agent || !agent.isLoggedIn) {
          reply = "⚠️ Please log in first! Enter your Swiggy phone number to continue.";
          break;
        }
        if (!intentData.items?.length) { reply = "What would you like to add?"; break; }

        const results = [];
        for (const item of intentData.items) {
          const r = await agent.addItemToCart(item.name, item.quantity || 1, item.customizations || [], item.restaurantName);
          results.push({ item: item.name, ...r });
          if (r.success) {
            session.cart.push({ itemName: item.name, quantity: item.quantity || 1, customizations: item.customizations || [], price: null, itemId: uuidv4() });
            screenshotBase64 = r.screenshot;
          }
        }

        const ok = results.filter(r => r.success).map(r => r.item);
        const oos = results.filter(r => r.outOfStock).map(r => r.item);
        const missing = results.filter(r => !r.success && !r.outOfStock).map(r => r.item);
        let parts = [];
        if (ok.length) parts.push(`✅ Added **${ok.join(', ')}** to your cart!`);
        if (oos.length) parts.push(`⚠️ **${oos.join(', ')}** is out of stock.`);
        if (missing.length) parts.push(`❓ Couldn't find **${missing.join(', ')}** — are you on the right restaurant page?`);
        reply = parts.join(' ') || 'Done!';
        cartUpdated = ok.length > 0;
        session.status = 'ordering';
        break;
      }

      case 'view_cart': {
        const agent = getAgent(sessionId);
        if (agent && agent.isLoggedIn) {
          const cartData = await agent.getCartContents();
          screenshotBase64 = cartData.screenshot;
          agentResult = { type: 'cart', ...cartData };
          if (cartData.items?.length > 0) {
            const list = cartData.items.map(i => `• ${i.quantity}× ${i.name}${i.price ? ` — ${i.price}` : ''}`).join('\n');
            reply = `🛒 **Your Swiggy Cart:**\n${list}${cartData.total ? `\n\n**Total: ${cartData.total}**` : ''}`;
          } else {
            reply = "Your cart is empty! Search for something to eat 🍽️";
          }
        } else {
          reply = "Please log in first to view your cart.";
        }
        break;
      }

      case 'confirm_order': {
        const agent = getAgent(sessionId);
        if (!agent || !agent.isLoggedIn) { reply = "Please log in first!"; break; }
        if (session.cart.length === 0) { reply = "Your cart is empty! Add some items first."; break; }
        const confirmMsg = await generateConfirmationMessage(session.cart, session.deliveryDetails);
        reply = confirmMsg;
        session.status = 'confirming';
        const checkout = await agent.proceedToCheckout();
        screenshotBase64 = checkout.screenshot;
        if (checkout.success) {
          new OrderLog({ sessionId, items: session.cart, status: 'placed', agentActions: agent.actionLog }).save();
          session.status = 'completed';
          reply += '\n\n✅ **Order placed!** You\'ll get a confirmation on your Swiggy app.';
        }
        break;
      }

      case 'cancel_order': {
        await destroyAgent(sessionId);
        session.cart = [];
        session.status = 'active';
        reply = "❌ Order cancelled. Start fresh anytime!";
        break;
      }

      default: {
        reply = intentData.reply || "Try searching for a restaurant or food item! E.g. 'Search biryani' or 'Find pizza near me'.";
      }
    }

    session.updatedAt = new Date();
    await session.save();
    conversation.messages.push({ role: 'assistant', content: reply });
    await conversation.save();

    res.json({ sessionId, reply, cart: session.cart, status: session.status, screenshot: screenshotBase64, cartUpdated, searchResults, intent: intentData.intent });

  } catch (err) {
    console.error(err);
    res.status(500).json({ error: 'Something went wrong.', details: err.message });
  }
});

// ── POST /api/chat/login/phone ───────────────────────────────────────────────
router.post('/login/phone', async (req, res) => {
  const { sessionId, phone } = req.body;
  if (!sessionId || !phone) return res.status(400).json({ error: 'sessionId and phone required' });

  try {
    let agent = getAgent(sessionId);
    if (!agent) {
      const { createAgent } = await import('../agents/webAgent.js');
      agent = await createAgent(sessionId);
    }

    const result = await agent.enterPhone(phone);
    res.json({ ...result, message: result.success ? 'OTP sent to your number!' : result.error });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/chat/login/otp ─────────────────────────────────────────────────
router.post('/login/otp', async (req, res) => {
  const { sessionId, otp } = req.body;
  if (!sessionId || !otp) return res.status(400).json({ error: 'sessionId and otp required' });

  try {
    const agent = getAgent(sessionId);
    if (!agent) return res.status(400).json({ error: 'Session not found. Please restart.' });

    const result = await agent.enterOTP(otp);

    if (result.success) {
      await Session.findOneAndUpdate({ sessionId }, { $set: { status: 'active' } }, { upsert: true });
    }

    res.json({ ...result, message: result.success ? '✅ Logged in successfully!' : (result.error || 'Invalid OTP') });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/chat/navigate ──────────────────────────────────────────────────
router.post('/navigate', async (req, res) => {
  const { sessionId, url } = req.body;
  if (!sessionId || !url) return res.status(400).json({ error: 'sessionId and url required' });
  try {
    const agent = getAgent(sessionId);
    if (!agent) return res.status(400).json({ error: 'Session not found' });
    const result = await agent.navigateToRestaurant(url);
    if (result.success && result.menuItems) {
      await Session.findOneAndUpdate({ sessionId }, { latestScreenData: result.menuItems });
    }
    res.json(result);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── GET /api/chat/session/:id ────────────────────────────────────────────────
router.get('/session/:sessionId', async (req, res) => {
  try {
    const { sessionId } = req.params;
    const session = await Session.findOne({ sessionId });
    const conversation = await Conversation.findOne({ sessionId });
    const agent = getAgent(sessionId);
    if (!session) return res.status(404).json({ error: 'Session not found' });
    res.json({ sessionId, cart: session.cart, status: session.status, deliveryDetails: session.deliveryDetails, messages: conversation?.messages || [], isLoggedIn: agent?.isLoggedIn || false });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

router.get('/orders', async (_req, res) => {
  try { res.json(await OrderLog.find().sort({ placedAt: -1 }).limit(50)); }
  catch (err) { res.status(500).json({ error: err.message }); }
});

router.delete('/session/:sessionId', async (req, res) => {
  try { await destroyAgent(req.params.sessionId); await Session.deleteOne({ sessionId: req.params.sessionId }); res.json({ success: true }); }
  catch (err) { res.status(500).json({ error: err.message }); }
});

// ── GET /api/chat/debug/:sessionId — get live screenshot for debugging ────────
router.get('/debug/:sessionId', async (req, res) => {
  try {
    const agent = getAgent(req.params.sessionId);
    if (!agent) return res.status(404).json({ error: 'No agent for this session' });
    const screenshot = await agent.takeScreenshot();
    const url = agent.page?.url?.() || 'unknown';
    res.json({ screenshot, url, isLoggedIn: agent.isLoggedIn });
  } catch (err) { res.status(500).json({ error: err.message }); }
});

export default router;
