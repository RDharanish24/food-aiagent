import React from 'react';
import { ExternalLink, Star, Clock, IndianRupee } from 'lucide-react';
import { navigateToRestaurant } from '../utils/api.js';

export default function SearchResults({ results, sessionId, onNavigated }) {
  if (!results || results.length === 0) return null;

  const handleOpen = async (item) => {
    if (!item.url) return;
    onNavigated?.(`Opening **${item.name}**...`);
    try {
      const data = await navigateToRestaurant(sessionId, item.url);
      if (data.success) {
        onNavigated?.(`✅ Opened **${item.name}**! Here's their menu. Now just say "add [item name]" to order.`, data.screenshot, data.menuItems);
      } else {
        onNavigated?.(`⚠️ Couldn't open ${item.name}. Try another restaurant.`);
      }
    } catch {
      onNavigated?.('Connection error. Please try again.');
    }
  };

  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
        {results[0]?.type === 'restaurant' ? '🏪 Restaurants' : '🍽️ Dishes'} — {results.length} results
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {results.map((item, i) => (
          <div key={i} style={{
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 12,
            overflow: 'hidden',
            display: 'flex',
            cursor: item.url ? 'pointer' : 'default',
            transition: 'border-color 0.15s, transform 0.1s',
          }}
          onMouseEnter={e => { if (item.url) { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}}
          onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.transform = 'translateY(0)'; }}
          onClick={() => item.url && handleOpen(item)}
          >
            {/* Image */}
            {item.img && (
              <div style={{ width: 80, height: 80, flexShrink: 0, overflow: 'hidden' }}>
                <img src={item.img} alt={item.name} style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  onError={e => { e.target.style.display = 'none'; }} />
              </div>
            )}

            {/* Info */}
            <div style={{ flex: 1, padding: '10px 12px', minWidth: 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.name}
                </div>
                {item.url && <ExternalLink size={12} color="var(--accent)" style={{ flexShrink: 0 }} />}
              </div>

              {item.cuisine && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{item.cuisine}</div>
              )}
              {item.restaurant && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>at {item.restaurant}</div>
              )}

              <div style={{ display: 'flex', gap: 10, marginTop: 6, flexWrap: 'wrap' }}>
                {item.rating && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>
                    <Star size={10} fill="currentColor" /> {item.rating}
                  </span>
                )}
                {item.deliveryTime && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 11, color: 'var(--text-muted)' }}>
                    <Clock size={10} /> {item.deliveryTime}
                  </span>
                )}
                {item.costForTwo && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: 3, fontSize: 11, color: 'var(--text-muted)' }}>
                    {item.costForTwo}
                  </span>
                )}
                {item.price && (
                  <span style={{ fontSize: 12, color: 'var(--accent)', fontWeight: 600 }}>{item.price}</span>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {results[0]?.type === 'restaurant' && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
          Tap a restaurant to open its menu
        </div>
      )}
    </div>
  );
}
