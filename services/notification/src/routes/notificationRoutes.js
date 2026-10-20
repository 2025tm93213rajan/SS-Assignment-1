const express = require('express');
const { v4: uuidv4 } = require('uuid');
const NotificationLog = require('../models/NotificationLog');
const ProcessedEvent = require('../models/ProcessedEvent');
const { publishEvent } = require('../amqp');

const router = express.Router();

/**
 * GET /api/v1/notifications/logs
 * Retrieve all dispatched notification audit logs
 */
router.get('/logs', async (req, res, next) => {
  try {
    const logs = await NotificationLog.find().sort({ created_at: -1 }).limit(50);
    return res.status(200).json(logs);
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/v1/notifications/booking/:booking_id
 * Retrieve notifications for a specific booking reference
 */
router.get('/booking/:booking_id', async (req, res, next) => {
  try {
    const logs = await NotificationLog.find({ booking_id: req.params.booking_id });
    return res.status(200).json(logs);
  } catch (err) {
    next(err);
  }
});

/**
 * POST /api/v1/notifications/publish-test
 * Helper endpoint to publish a test booking event to RabbitMQ
 */
router.post('/publish-test', async (req, res, next) => {
  try {
    const event = {
      event_id: req.body.event_id || `evt-${uuidv4().substring(0, 16)}`,
      booking_id: req.body.booking_id || `book-${uuidv4().substring(0, 12)}`,
      quota_id: req.body.quota_id || 'TATKAL-12951-B1',
      event_name: req.body.event_name || 'Mumbai Tejas Rajdhani Express (#12951)',
      category: req.body.category || 'RAILWAY_TATKAL',
      pnr: req.body.pnr || `PNR-TATKAL-${Math.floor(100000 + Math.random() * 900000)}`,
      customer_phone: req.body.customer_phone || '+91-9876543210',
      customer_email: req.body.customer_email || 'passenger@example.com',
      amount: req.body.amount || 2850.00,
      correlation_id: req.correlationId
    };

    const routingKey = req.body.routing_key || 'booking.confirmed';
    await publishEvent(routingKey, event);

    return res.status(202).json({
      status: 'PUBLISHED',
      routing_key: routingKey,
      event
    });
  } catch (err) {
    next(err);
  }
});

/**
 * POST /api/v1/notifications/reset
 * Clears notification logs and deduplication cache for repeatable challenge runs
 */
router.post('/reset', async (req, res, next) => {
  try {
    await NotificationLog.deleteMany({});
    await ProcessedEvent.deleteMany({});
    return res.status(200).json({
      status: 'RESET_COMPLETE',
      message: 'Notification logs and processed events cleared.',
      correlation_id: req.correlationId
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
