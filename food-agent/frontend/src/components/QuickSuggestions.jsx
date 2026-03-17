import React from 'react';

const SUGGESTIONS = [
  { label: '🔍 Search Biryani', message: 'Search biryani near me' },
  { label: '🍕 Find Pizza', message: 'Search pizza' },
  { label: '🍔 Burgers', message: 'Search burgers' },
  { label: '🛒 View Cart', message: 'Show my cart' },
  { label: '➕ Add Item', message: 'Add 1 Margherita pizza' },
  { label: '✅ Confirm', message: 'Confirm my order' },
  { label: '🗑️ Remove', message: 'Remove one item' },
  { label: '❌ Cancel', message: 'Cancel my order' },
];

export default function QuickSuggestions({ onSend, disabled }) {
  return (
    <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 2, scrollbarWidth: 'none' }}>
      {SUGGESTIONS.map((s, i) => (
        <button key={i} onClick={() => onSend(s.message)} disabled={disabled} style={{
          flexShrink: 0, padding: '5px 13px',
          background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 99,
          color: disabled ? 'var(--text-dim)' : 'var(--text)', fontSize: 12.5,
          cursor: disabled ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
          transition: 'all 0.15s', fontFamily: 'var(--font-body)',
        }}
        onMouseEnter={e => { if (!disabled) { e.target.style.borderColor = 'var(--accent)'; e.target.style.color = 'var(--accent)'; }}}
        onMouseLeave={e => { e.target.style.borderColor = 'var(--border)'; e.target.style.color = disabled ? 'var(--text-dim)' : 'var(--text)'; }}
        >{s.label}</button>
      ))}
    </div>
  );
}
