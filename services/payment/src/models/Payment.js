const mongoose = require('mongoose');

const paymentSchema = new mongoose.Schema({
  payment_id: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  booking_id: {
    type: String,
    required: true,
    index: true
  },
  amount: {
    type: Number,
    required: true
  },
  currency: {
    type: String,
    default: 'INR'
  },
  status: {
    type: String,
    enum: ['SUCCESS', 'FAILED', 'REFUNDED'],
    required: true
  },
  payment_method: {
    type: String,
    default: 'CARD'
  },
  idempotency_key: {
    type: String,
    index: true
  },
  failure_reason: {
    type: String,
    default: null
  },
  created_at: {
    type: Date,
    default: Date.now
  }
}, {
  versionKey: false
});

module.exports = mongoose.model('Payment', paymentSchema);
