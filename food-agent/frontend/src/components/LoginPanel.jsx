import React, { useState } from 'react';
import { Smartphone, KeyRound, Loader, Bug } from 'lucide-react';
import { sendPhoneLogin, sendOTPLogin } from '../utils/api.js';
import axios from 'axios';

export default function LoginPanel({ sessionId, onLoginSuccess }) {
  const [step, setStep] = useState('phone');
  const [phone, setPhone] = useState('');
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [screenshot, setScreenshot] = useState(null);
  const [debugInfo, setDebugInfo] = useState('');

  const fetchDebugScreenshot = async () => {
    try {
      const { data } = await axios.get(`/api/chat/debug/${sessionId}`);
      if (data.screenshot) setScreenshot(data.screenshot);
      setDebugInfo(`URL: ${data.url} | LoggedIn: ${data.isLoggedIn}`);
    } catch (e) {
      setDebugInfo('No active browser session yet.');
    }
  };

  const handlePhone = async () => {
    if (phone.length < 10) { setError('Enter a valid 10-digit number'); return; }
    setLoading(true); setError(''); setScreenshot(null); setDebugInfo('');
    try {
      const data = await sendPhoneLogin(sessionId, phone);
      if (data.screenshot) setScreenshot(data.screenshot);
      if (data.success) {
        setStep('otp');
      } else {
        setError(data.error || data.message || 'Failed to find phone input on Swiggy.');
      }
    } catch (e) {
      setError('Server error: ' + (e.response?.data?.error || e.message));
    } finally { setLoading(false); }
  };

  const handleOTP = async () => {
    if (otp.length < 4) { setError('Enter the OTP'); return; }
    setLoading(true); setError(''); setScreenshot(null);
    try {
      const data = await sendOTPLogin(sessionId, otp);
      if (data.screenshot) setScreenshot(data.screenshot);
      if (data.success) {
        onLoginSuccess();
      } else {
        setError(data.message || data.error || 'Invalid OTP. Please try again.');
      }
    } catch (e) {
      setError('Server error: ' + (e.response?.data?.error || e.message));
    } finally { setLoading(false); }
  };

  return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
      <div style={{ width: '100%', maxWidth: 420, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 20, overflow: 'hidden' }}>

        {/* Swiggy-orange header */}
        <div style={{ background: 'linear-gradient(135deg, #fc8019, #e8590c)', padding: '26px 28px 22px', textAlign: 'center' }}>
          <div style={{ fontSize: 42, marginBottom: 8 }}>🍽️</div>
          <div style={{ fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 21, color: '#fff' }}>Swiggy AI Agent</div>
          <div style={{ color: 'rgba(255,255,255,0.82)', fontSize: 13, marginTop: 4 }}>Connect your Swiggy account to start ordering</div>
        </div>

        <div style={{ padding: 26 }}>
          {step === 'phone' ? (
            <>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Swiggy Mobile Number
              </label>
              <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', padding: '0 12px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text-muted)', fontSize: 14, whiteSpace: 'nowrap' }}>
                  🇮🇳 +91
                </div>
                <input type="tel" maxLength={10} value={phone}
                  onChange={e => setPhone(e.target.value.replace(/\D/g, ''))}
                  onKeyDown={e => e.key === 'Enter' && handlePhone()}
                  placeholder="10-digit mobile number"
                  style={{ flex: 1, padding: '12px 14px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 10, color: 'var(--text)', fontFamily: 'var(--font-body)', fontSize: 15, outline: 'none' }}
                />
              </div>

              {error && <div style={{ color: 'var(--error)', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(248,113,113,0.1)', borderRadius: 8 }}>⚠️ {error}</div>}

              <button onClick={handlePhone} disabled={loading || phone.length < 10} style={{
                width: '100%', padding: '13px', marginBottom: 10,
                background: phone.length >= 10 && !loading ? '#fc8019' : 'var(--border)',
                border: 'none', borderRadius: 12,
                color: phone.length >= 10 && !loading ? '#fff' : 'var(--text-dim)',
                fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15,
                cursor: phone.length >= 10 && !loading ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}>
                {loading
                  ? <><Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> Opening Swiggy...</>
                  : <><Smartphone size={16} /> Get OTP via Swiggy</>}
              </button>

              {/* Debug button */}
              {loading && (
                <button onClick={fetchDebugScreenshot} style={{
                  width: '100%', padding: '8px', background: 'none',
                  border: '1px dashed var(--border)', borderRadius: 10, cursor: 'pointer',
                  color: 'var(--text-muted)', fontSize: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}>
                  <Bug size={13} /> Peek at browser
                </button>
              )}

              <div style={{ marginTop: 14, padding: '11px 13px', background: 'rgba(252,128,25,0.06)', border: '1px solid rgba(252,128,25,0.15)', borderRadius: 10, fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.7 }}>
                🔐 We open a real Swiggy browser on your behalf. Your credentials are never stored.
              </div>
            </>
          ) : (
            <>
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <div style={{ fontSize: 34, marginBottom: 8 }}>📱</div>
                <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 16 }}>Enter OTP</div>
                <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 4 }}>Sent to +91 {phone} via Swiggy</div>
              </div>

              <input type="tel" maxLength={6} value={otp}
                onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
                onKeyDown={e => e.key === 'Enter' && handleOTP()}
                placeholder="• • • • • •"
                style={{
                  width: '100%', padding: '14px', marginBottom: 14,
                  background: 'var(--surface2)', border: '1px solid var(--border)',
                  borderRadius: 10, color: 'var(--text)',
                  fontFamily: 'var(--font-display)', fontSize: 28, fontWeight: 700,
                  letterSpacing: '0.4em', textAlign: 'center', outline: 'none', boxSizing: 'border-box',
                }}
              />

              {error && <div style={{ color: 'var(--error)', fontSize: 13, marginBottom: 12, padding: '8px 12px', background: 'rgba(248,113,113,0.1)', borderRadius: 8 }}>⚠️ {error}</div>}

              <button onClick={handleOTP} disabled={loading || otp.length < 4} style={{
                width: '100%', padding: '13px', marginBottom: 10,
                background: otp.length >= 4 && !loading ? '#fc8019' : 'var(--border)',
                border: 'none', borderRadius: 12,
                color: otp.length >= 4 && !loading ? '#fff' : 'var(--text-dim)',
                fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 15,
                cursor: otp.length >= 4 && !loading ? 'pointer' : 'not-allowed',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              }}>
                {loading
                  ? <><Loader size={16} style={{ animation: 'spin 1s linear infinite' }} /> Verifying...</>
                  : <><KeyRound size={16} /> Verify OTP</>}
              </button>

              <button onClick={() => { setStep('phone'); setOtp(''); setError(''); setScreenshot(null); }} style={{
                width: '100%', padding: '10px', background: 'none',
                border: '1px solid var(--border)', borderRadius: 10,
                color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, fontFamily: 'var(--font-body)',
              }}>← Change number</button>
            </>
          )}

          {/* Debug info */}
          {debugInfo && <div style={{ marginTop: 10, fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface2)', borderRadius: 8, padding: '6px 10px' }}>{debugInfo}</div>}

          {/* Live browser screenshot */}
          {screenshot && (
            <div style={{ marginTop: 16 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5 }}>📸 Live browser view</div>
              <img src={`data:image/png;base64,${screenshot}`} alt="Browser" style={{ width: '100%', borderRadius: 8, border: '1px solid var(--border)' }} />
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
