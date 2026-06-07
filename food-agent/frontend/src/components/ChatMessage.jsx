import React from 'react';
import SearchResults from './SearchResults.jsx';

/**
 * ChatMessage — Enhanced with Orchestrator Brain UI cards
 *
 * When the backend returns orchestrator metadata, this component renders:
 * - Order Summary Card (glassmorphism) for complete payloads
 * - Clarification Card with quick-reply chips for slot-filling questions
 * - Intent badges to show what the orchestrator classified
 */

const INTENT_EMOJI = {
  SEARCH_AND_ADD: '🔍',
  MODIFY_CART: '🛒',
  PLACE_ORDER: '✅',
};

export default function ChatMessage({ msg, sessionId, onNavigated, onSend }) {
  const isUser = msg.role === 'user';

  return (
    <div className={isUser ? 'fade-in-right' : 'fade-in-left'} style={{
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
      marginBottom: 14,
      gap: 10,
      alignItems: 'flex-end',
    }}>
      {!isUser && (
        <div style={{
          width: 34, height: 34, borderRadius: '50%',
          background: 'linear-gradient(135deg, #fc8019, #e8590c)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 17, flexShrink: 0,
          boxShadow: '0 0 14px rgba(252,128,25,0.35)',
        }}>🍽️</div>
      )}

      <div style={{ maxWidth: '80%' }}>
        {/* Bubble */}
        <div style={{
          background: isUser ? 'linear-gradient(135deg, #fc8019 0%, #e8590c 100%)' : 'var(--surface)',
          color: isUser ? '#fff' : 'var(--text)',
          padding: '11px 16px',
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          border: isUser ? 'none' : '1px solid var(--border)',
          fontSize: 14, lineHeight: 1.65,
          whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        }}>
          {renderMarkdown(msg.content)}
        </div>

        {/* ── Orchestrator: Order Summary Card ────────────────────────── */}
        {!isUser && msg.orderState && msg.isComplete && msg.orderState.items?.length > 0 && (
          <OrderSummaryCard orderState={msg.orderState} intent={msg.intent} />
        )}

        {/* ── Orchestrator: Clarification Card ────────────────────────── */}
        {!isUser && msg.missingSlots?.length > 0 && !msg.isComplete && (
          <ClarificationCard
            missingSlots={msg.missingSlots}
            intent={msg.intent}
            onSend={onSend}
          />
        )}

        {/* Search results cards */}
        {!isUser && msg.searchResults?.length > 0 && (
          <SearchResults
            results={msg.searchResults}
            sessionId={sessionId}
            onNavigated={onNavigated}
          />
        )}

        {/* Screenshot */}
        {!isUser && msg.screenshot && (
          <div style={{ marginTop: 8 }}>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>📸 Live Swiggy view</div>
            <img src={`data:image/png;base64,${msg.screenshot}`} alt="Swiggy" style={{ width: '100%', borderRadius: 10, border: '1px solid var(--border)' }} />
          </div>
        )}

        {/* Timestamp */}
        <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 4, textAlign: isUser ? 'right' : 'left' }}>
          {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>

      {isUser && (
        <div style={{
          width: 34, height: 34, borderRadius: '50%',
          background: 'var(--surface2)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 15, flexShrink: 0,
        }}>👤</div>
      )}
    </div>
  );
}

/**
 * OrderSummaryCard — Glassmorphism card showing the fully extracted order
 */
function OrderSummaryCard({ orderState, intent }) {
  const intentEmoji = INTENT_EMOJI[intent] || '📝';
  const intentLabel = {
    SEARCH_AND_ADD: 'Search & Add',
    MODIFY_CART: 'Cart Update',
    PLACE_ORDER: 'Checkout',
  }[intent] || 'Order';

  return (
    <div className="order-summary-card">
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: 12, paddingBottom: 10,
        borderBottom: '1px solid rgba(255,255,255,0.05)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{intentEmoji}</span>
          <span style={{
            fontFamily: 'var(--font-display)', fontWeight: 700,
            fontSize: 13, color: 'var(--accent)',
          }}>
            {intentLabel}
          </span>
        </div>
        <span className={`intent-badge ${intent === 'SEARCH_AND_ADD' ? 'search' : intent === 'MODIFY_CART' ? 'modify' : 'place'}`}>
          COMPLETE
        </span>
      </div>

      {/* Restaurant */}
      {orderState.restaurant_preference && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 10px', marginBottom: 8,
          background: 'rgba(255, 107, 53, 0.06)',
          borderRadius: 8, border: '1px solid rgba(255, 107, 53, 0.1)',
        }}>
          <span>🏪</span>
          <span style={{ fontSize: 13, fontWeight: 600 }}>{orderState.restaurant_preference}</span>
        </div>
      )}

      {/* Items */}
      {orderState.items?.map((item, i) => (
        <div key={i} className="item-row">
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{
              width: 24, height: 24, borderRadius: 6,
              background: 'var(--surface3)', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: 'var(--accent)',
            }}>
              {item.quantity || 1}×
            </span>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{item.name}</div>
              {item.customizations?.length > 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
                  {item.customizations.join(', ')}
                </div>
              )}
            </div>
          </div>
        </div>
      ))}

      {/* Delivery */}
      {orderState.delivery_address_tag && (
        <div style={{
          marginTop: 8, display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 12, color: 'var(--text-muted)',
        }}>
          <span>📍</span> Delivering to: <strong style={{ color: 'var(--text)' }}>{orderState.delivery_address_tag}</strong>
        </div>
      )}
    </div>
  );
}

/**
 * ClarificationCard — Shown when the orchestrator needs more info
 */
function ClarificationCard({ missingSlots, intent, onSend }) {
  // Generate contextual quick-reply suggestions based on missing slots
  const suggestions = [];

  if (missingSlots.includes('items')) {
    suggestions.push(
      { label: '🍗 Chicken Biryani', text: 'Chicken Biryani' },
      { label: '🍕 Margherita Pizza', text: 'Margherita Pizza' },
      { label: '🍔 Veg Burger', text: 'Veg Burger' },
    );
  } else if (missingSlots.includes('restaurant_preference')) {
    suggestions.push(
      { label: '🏪 Search best', text: 'Find the best restaurant' },
      { label: "🍳 Meghana's", text: "From Meghana Foods" },
    );
  }

  return (
    <div className="clarification-card">
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6,
        marginBottom: 8, fontSize: 11, color: 'var(--warning)',
        fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px',
      }}>
        <span>💡</span> Need More Info
      </div>

      {suggestions.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {suggestions.map((s, i) => (
            <button
              key={i}
              className="quick-chip"
              onClick={() => onSend?.(s.text)}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function renderMarkdown(text) {
  if (!text) return null;
  // Split on **bold** and render accordingly
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}
