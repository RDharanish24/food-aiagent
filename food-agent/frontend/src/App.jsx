import React, { useState, useEffect, useRef, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { Send, ShoppingCart, Mic, MicOff, LogOut, RefreshCw } from 'lucide-react';
import ChatMessage from './components/ChatMessage.jsx';
import TypingIndicator from './components/TypingIndicator.jsx';
import CartSidebar from './components/CartSidebar.jsx';
import QuickSuggestions from './components/QuickSuggestions.jsx';
import LoginPanel from './components/LoginPanel.jsx';
import { sendMessage } from './utils/api.js';

const SESSION_KEY = 'swiggy_agent_session';
const LOGIN_KEY = 'swiggy_agent_loggedin';

const WELCOME_MSG = {
  role: 'assistant',
  content: '✅ **Logged in to Swiggy!**\n\nI\'m your AI ordering assistant. Just tell me what you want!\n\nTry:\n• "Search biryani near me"\n• "Find Pizza Hut"\n• "Search Chinese food"',
  timestamp: new Date(),
};

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function App() {
  const [sessionId] = useState(() => {
    const s = localStorage.getItem(SESSION_KEY);
    if (s) return s;
    const id = uuidv4();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  });

  const [isLoggedIn, setIsLoggedIn] = useState(() => localStorage.getItem(LOGIN_KEY) === 'true');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentAction, setAgentAction] = useState('');
  const [cart, setCart] = useState([]);
  const [orderStatus, setOrderStatus] = useState('active');
  const [showCart, setShowCart] = useState(false);
  const [isListening, setIsListening] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (isLoggedIn && messages.length === 0) {
      setMessages([WELCOME_MSG]);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  useEffect(() => {
    if (SpeechRecognition) {
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = false;
      recognitionRef.current.lang = 'en-IN';
      recognitionRef.current.onresult = e => { setInput(e.results[0][0].transcript); setIsListening(false); };
      recognitionRef.current.onerror = () => setIsListening(false);
      recognitionRef.current.onend = () => setIsListening(false);
    }
  }, []);

  const handleLoginSuccess = () => {
    localStorage.setItem(LOGIN_KEY, 'true');
    setIsLoggedIn(true);
  };

  const handleLogout = () => {
    localStorage.removeItem(LOGIN_KEY);
    localStorage.removeItem(SESSION_KEY);
    window.location.reload();
  };

  // Called by SearchResults when user taps a restaurant
  const handleNavigated = useCallback((replyText, screenshot, menuItems) => {
    const msg = { role: 'assistant', content: replyText, timestamp: new Date(), screenshot };
    setMessages(prev => [...prev, msg]);
  }, []);

  const handleSend = useCallback(async (overrideText) => {
    const text = (overrideText || input).trim();
    if (!text || loading) return;
    setInput('');

    const userMsg = { role: 'user', content: text, timestamp: new Date() };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    const lc = text.toLowerCase();
    if (lc.includes('search') || lc.includes('find')) setAgentAction('Searching Swiggy...');
    else if (lc.includes('add')) setAgentAction('Adding to cart...');
    else if (lc.includes('cart')) setAgentAction('Fetching cart...');
    else if (lc.includes('confirm')) setAgentAction('Proceeding to checkout...');
    else setAgentAction('Processing...');

    try {
      const data = await sendMessage(text, sessionId);

      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.reply,
        timestamp: new Date(),
        screenshot: data.screenshot,
        searchResults: data.searchResults,
        cart: data.cart,
        cartUpdated: data.cartUpdated,
        intent: data.intent,
      }]);

      if (data.cart) setCart(data.cart);
      if (data.status) setOrderStatus(data.status);
      if (data.cartUpdated && data.cart?.length > 0) setShowCart(true);

    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant', content: '⚠️ Connection error. Is the backend running on port 5000?', timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
      setAgentAction('');
      inputRef.current?.focus();
    }
  }, [input, loading, sessionId]);

  const handleKeyDown = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const cartCount = cart.reduce((s, i) => s + i.quantity, 0);

  if (!isLoggedIn) {
    return (
      <div style={{ height: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>
        <header style={{ padding: '16px 24px', background: 'var(--surface)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'linear-gradient(135deg, #fc8019, #e8590c)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>🍽️</div>
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 18 }}>Swiggy AI Agent</span>
        </header>
        <div style={{ flex: 1, overflow: 'auto' }}>
          <LoginPanel sessionId={sessionId} onLoginSuccess={handleLoginSuccess} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--bg)', overflow: 'hidden' }}>
      {/* Header */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '13px 20px',
        background: 'var(--surface)', borderBottom: '1px solid var(--border)', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 38, height: 38, borderRadius: 11, background: 'linear-gradient(135deg, #fc8019, #e8590c)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 19, boxShadow: '0 0 16px rgba(252,128,25,0.35)' }}>🍽️</div>
          <div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 16 }}>Swiggy AI Agent</div>
            <div style={{ fontSize: 11, color: '#fc8019', display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', display: 'inline-block', animation: 'pulse 2s infinite' }}></span>
              Logged in • swiggy.com
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button onClick={() => setShowCart(!showCart)} style={{
            display: 'flex', alignItems: 'center', gap: 7, padding: '7px 14px',
            background: cartCount > 0 ? '#fc8019' : 'var(--surface2)',
            border: '1px solid ' + (cartCount > 0 ? '#fc8019' : 'var(--border)'),
            borderRadius: 10, color: cartCount > 0 ? '#fff' : 'var(--text)',
            cursor: 'pointer', fontFamily: 'var(--font-body)', fontSize: 13, fontWeight: 500,
          }}>
            <ShoppingCart size={15} />
            {cartCount > 0 ? `${cartCount} item${cartCount > 1 ? 's' : ''}` : 'Cart'}
          </button>
          <button onClick={handleLogout} title="Logout" style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 8px', color: 'var(--text-muted)', cursor: 'pointer' }}>
            <LogOut size={14} />
          </button>
        </div>
      </header>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        {/* Chat */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 1, overflowY: 'auto', padding: '18px 18px 8px' }}>
            {messages.map((msg, i) => (
              <ChatMessage key={i} msg={msg} sessionId={sessionId} onNavigated={handleNavigated} />
            ))}
            {loading && <TypingIndicator agentAction={agentAction} />}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div style={{ padding: '10px 18px 18px', borderTop: '1px solid var(--border)', background: 'var(--surface)', flexShrink: 0 }}>
            <div style={{ marginBottom: 10 }}>
              <QuickSuggestions onSend={handleSend} disabled={loading} />
            </div>
            <div style={{
              display: 'flex', gap: 8, alignItems: 'flex-end',
              background: 'var(--surface2)', border: '1px solid var(--border)',
              borderRadius: 14, padding: '9px 9px 9px 14px',
            }}>
              <textarea
                ref={inputRef} value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder='Search food, say "add biryani", or ask anything...'
                disabled={loading} rows={1}
                style={{
                  flex: 1, background: 'none', border: 'none', outline: 'none',
                  color: 'var(--text)', fontFamily: 'var(--font-body)', fontSize: 14,
                  resize: 'none', lineHeight: 1.5, maxHeight: 90, overflowY: 'auto',
                }}
              />
              {SpeechRecognition && (
                <button onClick={() => {
                  if (isListening) { recognitionRef.current.stop(); setIsListening(false); }
                  else { recognitionRef.current.start(); setIsListening(true); }
                }} style={{
                  background: isListening ? 'rgba(252,128,25,0.15)' : 'none',
                  border: isListening ? '1px solid #fc8019' : '1px solid var(--border)',
                  borderRadius: 8, padding: '6px 8px',
                  color: isListening ? '#fc8019' : 'var(--text-muted)', cursor: 'pointer',
                }}>
                  {isListening ? <MicOff size={15} /> : <Mic size={15} />}
                </button>
              )}
              <button onClick={() => handleSend()} disabled={!input.trim() || loading} style={{
                background: input.trim() && !loading ? '#fc8019' : 'var(--border)',
                border: 'none', borderRadius: 10, padding: '8px 14px',
                color: input.trim() && !loading ? '#fff' : 'var(--text-dim)',
                cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', gap: 5,
                fontFamily: 'var(--font-body)', fontWeight: 500, fontSize: 13,
              }}>
                <Send size={14} /> Send
              </button>
            </div>
            <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-dim)', textAlign: 'center' }}>
              AI agent browsing swiggy.com on your behalf
            </div>
          </div>
        </div>

        {/* Cart sidebar */}
        {showCart && (
          <div style={{ width: 290, borderLeft: '1px solid var(--border)', flexShrink: 0, animation: 'fadeSlideIn 0.2s ease' }}>
            <CartSidebar cart={cart} status={orderStatus} onClose={() => setShowCart(false)} />
          </div>
        )}
      </div>
    </div>
  );
}
