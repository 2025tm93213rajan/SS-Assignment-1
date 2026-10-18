const mongoose = require('mongoose');

const idempotencyRecordSchema = new mongoose.Schema({
  idempotency_key: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  request_fingerprint: {
    type: String,
    required: true
  },
  status: {
    type: String,
    enum: ['PENDING', 'COMPLETED', 'FAILED'],
    default: 'PENDING'
  },
  status_code: {
    type: Number,
    default: null
  },
  response_body: {
    type: mongoose.Schema.Types.Mixed,
    default: null
  },
  created_at: {
    type: Date,
    default: Date.now,
    expires: 86400 // TTL 24 hours
  },
  updated_at: {
    type: Date,
    default: Date.now
  }
}, {
  versionKey: false
});

module.exports = mongoose.model('IdempotencyRecord', idempotencyRecordSchema);
