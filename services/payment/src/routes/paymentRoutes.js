const express = require('express');
const { v4: uuidv4 } = require('uuid');
const Payment = require('../models/Payment');
const IdempotencyRecord = require('../models/IdempotencyRecord');
const { idempotencyMiddleware } = require('../middleware/idempotency');

const router = express.Router();

let chaosConfig = {
  enabled: process.env.PAYMENT_CHAOS_MODE === 'true',
  delayMs: parseInt(process.env.PAYMENT_DELAY_MS || '0', 10)
};

/**
 * POST /api/v1/payments/charge
 * Unsafe state-mutating operation protected by BR3 Idempotency Middleware.
 */
router.post('/charge', idempotencyMiddleware, async (req, res, next) => {
  try {
    const { booking_id, amount, currency = 'INR', payment_method = 'CARD', card_number, force_failure, delay_ms } = req.body;
    const idempotencyKey = req.headers['idempotency-key'] || req.headers['x-idempotency-key'];

    if (!booking_id) {
      return res.status(400).json({
        status: 'error',
        code: 'MISSING_BOOKING_ID',
        message: 'Field "booking_id" is required.',
        correlation_id: req.correlationId
      });
    }

    if (!amount || typeof amount !== 'number' || amount <= 0) {
      return res.status(400).json({
        status: 'error',
        code: 'INVALID_AMOUNT',
        message: 'Field "amount" must be a positive number.',
        correlation_id: req.correlationId
      });
    }

    // 1. Simulate downstream gateway latency
    const waitTime = delay_ms !== undefined ? delay_ms : chaosConfig.delayMs;
    if (waitTime > 0) {
      await new Promise((resolve) => setTimeout(resolve, waitTime));
    }

    // 2. Simulate downstream bank failure (Condition e)
    const shouldFail = force_failure === true || 
                       card_number === '4000-0000-0000-0002' || 
                       chaosConfig.enabled;

    const paymentId = `pay-${uuidv4().substring(0, 16)}`;

    if (shouldFail) {
      const failedPayment = await Payment.create({
        payment_id: paymentId,
        booking_id,
        amount,
        currency,
        status: 'FAILED',
        payment_method,
        idempotency_key: idempotencyKey,
        failure_reason: 'Card declined by issuing bank (Simulated Chaos Failure)'
      });

      return res.status(402).json({
        status: 'FAILED',
        code: 'PAYMENT_DECLINED',
        message: 'Transaction declined by issuing bank. Initiating Saga compensation.',
        payment_id: failedPayment.payment_id,
        booking_id: failedPayment.booking_id,
        amount: failedPayment.amount,
        correlation_id: req.correlationId,
        timestamp: new Date().toISOString()
      });
    }

    // 3. Success Path: Record payment ledger entry
    const payment = await Payment.create({
      payment_id: paymentId,
      booking_id,
      amount,
      currency,
      status: 'SUCCESS',
      payment_method,
      idempotency_key: idempotencyKey
    });

    return res.status(201).json({
      status: 'SUCCESS',
      payment_id: payment.payment_id,
      booking_id: payment.booking_id,
      amount: payment.amount,
      currency: payment.currency,
      payment_method: payment.payment_method,
      correlation_id: req.correlationId,
      created_at: payment.created_at.toISOString()
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/v1/payments/:payment_id
 */
router.get('/:payment_id', async (req, res, next) => {
  try {
    const payment = await Payment.findOne({ payment_id: req.params.payment_id });
    if (!payment) {
      return res.status(404).json({
        status: 'error',
        code: 'PAYMENT_NOT_FOUND',
        message: `Payment '${req.params.payment_id}' not found.`,
        correlation_id: req.correlationId
      });
    }
    return res.status(200).json(payment);
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/v1/payments/booking/:booking_id
 */
router.get('/booking/:booking_id', async (req, res, next) => {
  try {
    const payments = await Payment.find({ booking_id: req.params.booking_id });
    return res.status(200).json(payments);
  } catch (err) {
    next(err);
  }
});

/**
 * POST /api/v1/payments/chaos
 * Dynamically toggles failure injection or latency for test scripts and demo
 */
router.post('/chaos', (req, res) => {
  const { enabled, delay_ms } = req.body;
  if (enabled !== undefined) chaosConfig.enabled = Boolean(enabled);
  if (delay_ms !== undefined) chaosConfig.delayMs = parseInt(delay_ms, 10);

  return res.status(200).json({
    status: 'CHAOS_CONFIG_UPDATED',
    config: chaosConfig,
    correlation_id: req.correlationId
  });
});

/**
 * POST /api/v1/payments/reset
 * Resets collections for challenge test reproducibility
 */
router.post('/reset', async (req, res, next) => {
  try {
    await Payment.deleteMany({});
    await IdempotencyRecord.deleteMany({});
    return res.status(200).json({
      status: 'RESET_COMPLETE',
      message: 'Payment and Idempotency collections cleared.',
      correlation_id: req.correlationId
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
