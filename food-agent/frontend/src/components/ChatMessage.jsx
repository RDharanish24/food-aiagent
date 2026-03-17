import React from 'react';
import SearchResults from './SearchResults.jsx';

export default function ChatMessage({ msg, sessionId, onNavigated }) {
  const isUser = msg.role === 'user';

  return (
    <div className="fade-in" style={{
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
          {/* Render **bold** markdown */}
          {renderMarkdown(msg.content)}
        </div>

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
