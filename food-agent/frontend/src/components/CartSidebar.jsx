import React from 'react';
import { ShoppingCart, X, Package, Truck } from 'lucide-react';

export default function CartSidebar({ cart, status, deliveryDetails, onClose }) {
  const total = cart.reduce((sum, item) => sum + ((item.price || 0) * item.quantity), 0);

  return (
    <div style={{
      width: '100%', height: '100%',
      background: 'var(--surface)',
      borderLeft: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 20px 16px',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <ShoppingCart size={20} color="var(--accent)" />
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 18 }}>Your Order</span>
        </div>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
          <X size={18} />
        </button>
      </div>

      {/* Status badge */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)' }}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 6,
          padding: '4px 12px', borderRadius: 99,
          background: status === 'completed' ? 'rgba(74,222,128,0.1)' :
                      status === 'confirming' ? 'rgba(251,191,36,0.1)' :
                      status === 'ordering' ? 'rgba(255,107,53,0.1)' : 'var(--surface2)',
          color: status === 'completed' ? 'var(--success)' :
                 status === 'confirming' ? 'var(--warning)' :
                 status === 'ordering' ? 'var(--accent)' : 'var(--text-muted)',
          fontSize: 12, fontWeight: 500,
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'currentColor',
            animation: status === 'ordering' || status === 'confirming' ? 'pulse 1.5s infinite' : 'none',
          }}></span>
          {status === 'active' ? 'Browsing' :
           status === 'ordering' ? 'Building order...' :
           status === 'confirming' ? 'Awaiting confirmation' :
           status === 'completed' ? 'Order placed!' : status}
        </span>
      </div>

      {/* Cart items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
        {cart.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '40px 20px',
            color: 'var(--text-muted)',
          }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🍽️</div>
            <div style={{ fontFamily: 'var(--font-display)', fontWeight: 600, marginBottom: 6 }}>Cart is empty</div>
            <div style={{ fontSize: 13 }}>Tell me what you'd like to order!</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {cart.map((item, i) => (
              <div key={i} style={{
                background: 'var(--surface2)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)',
                padding: '12px 14px',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: 14 }}>{item.itemName}</div>
                    {item.customizations?.length > 0 && (
                      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
                        {item.customizations.join(', ')}
                      </div>
                    )}
                  </div>
                  <div style={{
                    background: 'var(--bg)',
                    border: '1px solid var(--border)',
                    borderRadius: 99,
                    padding: '2px 10px',
                    fontSize: 13, fontWeight: 600,
                    color: 'var(--accent)',
                    marginLeft: 10,
                  }}>×{item.quantity}</div>
                </div>
                {item.price && (
                  <div style={{ marginTop: 6, fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>
                    ₹{item.price * item.quantity}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Delivery details */}
      {deliveryDetails?.type && (
        <div style={{
          margin: '0 20px',
          padding: '12px 14px',
          background: 'rgba(255,107,53,0.06)',
          border: '1px solid rgba(255,107,53,0.2)',
          borderRadius: 'var(--radius-sm)',
          marginBottom: 12,
          fontSize: 13,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent)', fontWeight: 600, marginBottom: 4 }}>
            {deliveryDetails.type === 'pickup' ? <Package size={14} /> : <Truck size={14} />}
            {deliveryDetails.type === 'pickup' ? 'Pickup' : 'Delivery'}
          </div>
          {deliveryDetails.address && <div style={{ color: 'var(--text-muted)' }}>{deliveryDetails.address}</div>}
          {deliveryDetails.time && <div style={{ color: 'var(--text-muted)' }}>Time: {deliveryDetails.time}</div>}
        </div>
      )}

      {/* Total + CTA */}
      {cart.length > 0 && (
        <div style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--border)',
        }}>
          {total > 0 && (
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ color: 'var(--text-muted)' }}>Estimated total</span>
              <span style={{ fontWeight: 700, color: 'var(--accent2)', fontFamily: 'var(--font-display)' }}>
                ₹{total}
              </span>
            </div>
          )}
          <div style={{
            padding: '10px 14px',
            background: 'var(--surface2)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-sm)',
            fontSize: 13, color: 'var(--text-muted)',
            textAlign: 'center',
          }}>
            💬 Tell the agent to "confirm order" to place it
          </div>
        </div>
      )}
    </div>
  );
}
