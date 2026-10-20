const mongoose = require('mongoose');

const processedEventSchema = new mongoose.Schema({
  event_id: {
    type: String,
    required: true,
    unique: true,
    index: true
  },
  processed_at: {
    type: Date,
    default: Date.now,
    expires: 86400 * 7 // Keep deduplication record for 7 days
  }
}, {
  versionKey: false,
  collection: 'processed_events'
});

module.exports = mongoose.model('ProcessedEvent', processedEventSchema, 'processed_events');
