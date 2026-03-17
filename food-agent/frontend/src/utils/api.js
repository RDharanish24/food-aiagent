import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

export const sendMessage = (message, sessionId) =>
  api.post('/chat', { message, sessionId }).then(r => r.data);

export const sendPhoneLogin = (sessionId, phone) =>
  api.post('/chat/login/phone', { sessionId, phone }).then(r => r.data);

export const sendOTPLogin = (sessionId, otp) =>
  api.post('/chat/login/otp', { sessionId, otp }).then(r => r.data);

export const navigateToRestaurant = (sessionId, url) =>
  api.post('/chat/navigate', { sessionId, url }).then(r => r.data);

export const getSession = (sessionId) =>
  api.get(`/chat/session/${sessionId}`).then(r => r.data);

export default api;
