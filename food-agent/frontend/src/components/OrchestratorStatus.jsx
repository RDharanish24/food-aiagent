import React, { useMemo } from 'react';

/**
 * OrchestratorStatus — Real-time slot-filling progress panel
 *
 * Visualizes the orchestrator brain's current state: which slots are
 * filled, which are pending, and the current intent classification.
 * Features an animated progress ring and glassmorphism styling.
 */

const SLOT_ICONS = {
  items: '🍽️',
  restaurant_preference: '🏪',
  delivery_address_tag: '📍',
};

const SLOT_LABELS = {
  items: 'Food Items',
  restaurant_preference: 'Restaurant',
  delivery_address_tag: 'Delivery Address',
};

const INTENT_CONFIG = {
  SEARCH_AND_ADD: { emoji: '🔍', label: 'Search & Add', className: 'search' },
  MODIFY_CART: { emoji: '🛒', label: 'Modify Cart', className: 'modify' },
  PLACE_ORDER: { emoji: '✅', label: 'Place Order', className: 'place' },
  SMALL_TALK: { emoji: '💬', label: 'Chat', className: 'clarify' },
  GREETING: { emoji: '👋', label: 'Greeting', className: 'clarify' },
  UNCLEAR: { emoji: '❓', label: 'Clarifying', className: 'clarify' },
};

function ProgressRing({ progress, size = 40, stroke = 3 }) {
  const radius = (size - stroke) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;

  return (
    <svg className="progress-ring" width={size} height={size}>
      <circle
        stroke="var(--slot-empty)"
        fill="transparent"
        strokeWidth={stroke}
        r={radius}
        cx={size / 2}
        cy={size / 2}
      />
      <circle
        stroke={progress >= 100 ? 'var(--success)' : 'var(--accent)'}
        fill="transparent"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={`${circumference} ${circumference}`}
        strokeDashoffset={offset}
        r={radius}
        cx={size / 2}
        cy={size / 2}
        style={{ filter: progress >= 100 ? 'drop-shadow(0 0 4px var(--success))' : 'drop-shadow(0 0 4px var(--accent))' }}
      />
      <text
        x="50%"
        y="50%"
        dy=".3em"
        textAnchor="middle"
        fill="var(--text)"
        fontSize="10"
        fontWeight="700"
        fontFamily="var(--font-body)"
        transform={`rotate(90, ${size / 2}, ${size / 2})`}
      >
        {Math.round(progress)}%
      </text>
    </svg>
  );
}

export default function OrchestratorStatus({ orderState, isComplete, missingSlots = [] }) {
  const slots = useMemo(() => {
    if (!orderState) return [];

    const result = [];

    // Items slot
    const hasItems = orderState.items && orderState.items.length > 0;
    const itemSummary = hasItems
      ? orderState.items.map(i => `${i.quantity || 1}× ${i.name}`).join(', ')
      : null;
    result.push({
      key: 'items',
      status: hasItems ? 'filled' : (missingSlots.includes('items') ? 'pending' : 'empty'),
      value: itemSummary,
    });

    // Restaurant slot
    const hasRestaurant = !!orderState.restaurant_preference;
    result.push({
      key: 'restaurant_preference',
      status: hasRestaurant ? 'filled' : 'empty',
      value: orderState.restaurant_preference || null,
    });

    // Delivery slot
    const hasAddress = !!orderState.delivery_address_tag;
    result.push({
      key: 'delivery_address_tag',
      status: hasAddress ? 'filled' : 'empty',
      value: orderState.delivery_address_tag || null,
    });

    return result;
  }, [orderState, missingSlots]);

  const progress = useMemo(() => {
    const filledCount = slots.filter(s => s.status === 'filled').length;
    // Items is required (weight=60%), restaurant is helpful (weight=30%), address is optional (weight=10%)
    let p = 0;
    if (slots.find(s => s.key === 'items')?.status === 'filled') p += 60;
    if (slots.find(s => s.key === 'restaurant_preference')?.status === 'filled') p += 30;
    if (slots.find(s => s.key === 'delivery_address_tag')?.status === 'filled') p += 10;
    return Math.min(p, 100);
  }, [slots]);

  const intentConfig = INTENT_CONFIG[orderState?.intent] || null;

  // Don't render if no state at all
  if (!orderState || (!orderState.intent && (!orderState.items || orderState.items.length === 0))) {
    return null;
  }

  return (
    <div className="orchestrator-panel fade-in" style={{ marginBottom: 12 }}>
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ProgressRing progress={isComplete ? 100 : progress} />
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, fontFamily: 'var(--font-display)', letterSpacing: '0.3px' }}>
              Order Brain
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 1 }}>
              {isComplete ? '✓ Ready to execute' : 'Collecting details...'}
            </div>
          </div>
        </div>

        {intentConfig && (
          <span className={`intent-badge ${intentConfig.className}`}>
            {intentConfig.emoji} {intentConfig.label}
          </span>
        )}
      </div>

      {/* Slot indicators */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {slots.map(slot => (
          <div
            key={slot.key}
            className={`slot-indicator ${slot.status} ${slot.status === 'filled' ? 'slot-pop' : ''}`}
          >
            <span style={{ fontSize: 14 }}>{SLOT_ICONS[slot.key]}</span>
            <span style={{ flex: 1 }}>{SLOT_LABELS[slot.key]}</span>
            {slot.value ? (
              <span style={{
                fontSize: 11,
                fontWeight: 600,
                maxWidth: 150,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}>
                {slot.value}
              </span>
            ) : (
              <span style={{ fontSize: 10, opacity: 0.5 }}>—</span>
            )}
          </div>
        ))}
      </div>

      {/* Completion bar */}
      <div style={{
        marginTop: 10,
        height: 3,
        borderRadius: 2,
        background: 'var(--slot-empty)',
        overflow: 'hidden',
      }}>
        <div style={{
          height: '100%',
          width: `${isComplete ? 100 : progress}%`,
          borderRadius: 2,
          background: isComplete
            ? 'linear-gradient(90deg, var(--success), #22d3ee)'
            : 'linear-gradient(90deg, var(--accent), var(--accent2))',
          transition: 'width 0.5s ease, background 0.3s ease',
          boxShadow: isComplete
            ? '0 0 8px var(--success-glow)'
            : '0 0 8px var(--accent-glow)',
        }} />
      </div>
    </div>
  );
}
