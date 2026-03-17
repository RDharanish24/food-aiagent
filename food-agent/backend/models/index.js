import mongoose from 'mongoose';

// ─── Session Model ───────────────────────────────────────────────────────────
const sessionSchema = new mongoose.Schema({
  sessionId: { type: String, required: true, unique: true },
  userId: { type: String },
  cart: [{
    itemName: String,
    quantity: Number,
    customizations: [String],
    price: Number,
    itemId: String,
  }],
  status: {
    type: String,
    enum: ['active', 'ordering', 'confirming', 'completed', 'failed'],
    default: 'active'
  },
  deliveryDetails: {
    type: { type: String, enum: ['delivery', 'pickup'], default: 'delivery' },
    address: String,
    time: String,
  },
  createdAt: { type: Date, default: Date.now },
  updatedAt: { type: Date, default: Date.now },
});

// ─── Conversation Log Model ──────────────────────────────────────────────────
const conversationSchema = new mongoose.Schema({
  sessionId: { type: String, required: true },
  messages: [{
    role: { type: String, enum: ['user', 'assistant', 'system'] },
    content: String,
    timestamp: { type: Date, default: Date.now },
  }],
  createdAt: { type: Date, default: Date.now },
});

// ─── Order Log Model ─────────────────────────────────────────────────────────
const orderLogSchema = new mongoose.Schema({
  sessionId: { type: String, required: true },
  orderId: String,
  items: [{
    itemName: String,
    quantity: Number,
    customizations: [String],
    price: Number,
  }],
  totalAmount: Number,
  deliveryDetails: {
    type: { type: String },
    address: String,
    time: String,
  },
  status: {
    type: String,
    enum: ['pending', 'placed', 'failed'],
    default: 'pending'
  },
  agentActions: [{
    action: String,
    target: String,
    result: String,
    timestamp: { type: Date, default: Date.now },
  }],
  errorDetails: String,
  placedAt: { type: Date, default: Date.now },
});

export const Session = mongoose.model('Session', sessionSchema);
export const Conversation = mongoose.model('Conversation', conversationSchema);
export const OrderLog = mongoose.model('OrderLog', orderLogSchema);
