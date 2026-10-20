const mongoose = require('mongoose');

const notificationLogSchema = new mongoose.Schema({
  notification_id: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  event_id: {
    type: String,
    required: true,
    index: true
  },
  booking_id: {
    type: String,
    required: true,
    index: true
  },
  recipient: {
    type: String,
    required: true
  },
  channel: {
    type: String,
    enum: ['SMS', 'EMAIL'],
    default: 'SMS'
  },
  subject: {
    type: String,
    default: null
  },
  message: {
    type: String,
    required: true
  },
  status: {
    type: String,
    enum: ['DELIVERED', 'FAILED'],
    default: 'DELIVERED'
  },
  metadata: {
    type: mongoose.Schema.Types.Mixed,
    default: {}
  },
  created_at: {
    type: Date,
    default: Date.now
  }
}, {
  versionKey: false,
  collection: 'notification_logs'
});

module.exports = mongoose.model('NotificationLog', notificationLogSchema, 'notification_logs');
