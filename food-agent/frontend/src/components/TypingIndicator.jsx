import React from 'react';

export default function TypingIndicator({ agentAction }) {
  return (
    <div className="fade-in" style={{ display: 'flex', gap: 10, alignItems: 'flex-end', marginBottom: 12 }}>
      <div style={{
        width: 32, height: 32, borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--accent), #ff9f6b)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 16, flexShrink: 0,
        animation: 'pulse 2s infinite',
        boxShadow: '0 0 12px rgba(255,107,53,0.3)',
      }}>🍽️</div>

      <div style={{
        background: 'var(--bot-bubble)',
        border: '1px solid var(--border)',
        padding: '14px 18px',
        borderRadius: '18px 18px 18px 4px',
        display: 'flex', flexDirection: 'column', gap: 8,
      }}>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center' }}>
          <span className="typing-dot"></span>
          <span className="typing-dot"></span>
          <span className="typing-dot"></span>
        </div>
        {agentAction && (
          <div style={{
            fontSize: 11, color: 'var(--accent)',
            display: 'flex', alignItems: 'center', gap: 5,
          }}>
            <span style={{ animation: 'pulse 1s infinite' }}>⚙️</span>
            {agentAction}
          </div>
        )}
      </div>
    </div>
  );
}
