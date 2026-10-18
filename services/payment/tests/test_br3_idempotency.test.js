const request = require('supertest');
const app = require('../src/index');
const Payment = require('../src/models/Payment');
const IdempotencyRecord = require('../src/models/IdempotencyRecord');
const { mongoose } = require('../src/db');

describe('Business Rule BR3: Two-Phase Cryptographic Idempotency Tests', () => {
  beforeAll(async () => {
    // Wait for mongoose connection if not yet ready
    if (mongoose.connection.readyState !== 1) {
      await new Promise((resolve) => mongoose.connection.once('open', resolve));
    }
  });

  beforeEach(async () => {
    await Payment.deleteMany({});
    await IdempotencyRecord.deleteMany({});
  });

  afterAll(async () => {
    await mongoose.connection.close();
  });

  test('BR3.1: Missing Idempotency-Key on unsafe charge operation returns 400 Bad Request', async () => {
    const res = await request(app)
      .post('/api/v1/payments/charge')
      .send({
        booking_id: 'book-test-01',
        amount: 2850.00
      });

    expect(res.statusCode).toBe(400);
    expect(res.body.code).toBe('MISSING_IDEMPOTENCY_KEY');
  });

  test('BR3.2: First call with unique Idempotency-Key successfully charges and persists 1 payment record', async () => {
    const key = 'idem-key-unique-001';
    const payload = {
      booking_id: 'book-test-02',
      amount: 2850.00,
      currency: 'INR'
    };

    const res = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send(payload);

    expect(res.statusCode).toBe(201);
    expect(res.body.status).toBe('SUCCESS');
    expect(res.body.payment_id).toBeDefined();

    // Verify 1 payment and 1 idempotency record in MongoDB
    const paymentCount = await Payment.countDocuments({ booking_id: 'book-test-02' });
    expect(paymentCount).toBe(1);

    const record = await IdempotencyRecord.findOne({ idempotency_key: key });
    expect(record).not.toBeNull();
    expect(record.status).toBe('COMPLETED');
    expect(record.request_fingerprint).toBeDefined();
  });

  test('BR3.3: Replaying identical request with same key returns cached response with X-Idempotent-Replay header and zero duplicate charge', async () => {
    const key = 'idem-key-replay-002';
    const payload = {
      booking_id: 'book-test-03',
      amount: 5000.00,
      currency: 'INR'
    };

    // First Call
    const res1 = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send(payload);

    expect(res1.statusCode).toBe(201);
    expect(res1.headers['x-idempotent-replay']).toBeUndefined();
    const originalPaymentId = res1.body.payment_id;

    // Second Call (Sequential Repeat with same key and exact same payload)
    const res2 = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send(payload);

    expect(res2.statusCode).toBe(201);
    expect(res2.headers['x-idempotent-replay']).toBe('true');
    expect(res2.body.payment_id).toBe(originalPaymentId);

    // CRITICAL ASSERTION: MongoDB must still only have exactly 1 payment record! Zero double charging.
    const paymentCount = await Payment.countDocuments({ booking_id: 'book-test-03' });
    expect(paymentCount).toBe(1);
  });

  test('BR3.4: Reusing same Idempotency-Key with altered payload is rejected with 422 Unprocessable Entity', async () => {
    const key = 'idem-key-mismatch-003';

    // Original Call
    const res1 = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send({
        booking_id: 'book-test-04',
        amount: 1000.00
      });
    expect(res1.statusCode).toBe(201);

    // Mismatched Call with same key but amount altered to 9999.00
    const res2 = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send({
        booking_id: 'book-test-04',
        amount: 9999.00 // Altered payload!
      });

    expect(res2.statusCode).toBe(422);
    expect(res2.body.code).toBe('IDEMPOTENCY_PAYLOAD_MISMATCH');
    expect(res2.body.message).toContain('different request payload');
  });

  test('BR3.5: Downstream failure simulation returns 402 Payment Required and records failure', async () => {
    const key = 'idem-key-fail-004';
    const res = await request(app)
      .post('/api/v1/payments/charge')
      .set('Idempotency-Key', key)
      .send({
        booking_id: 'book-test-05',
        amount: 2850.00,
        card_number: '4000-0000-0000-0002' // Trigger simulated decline
      });

    expect(res.statusCode).toBe(402);
    expect(res.body.code).toBe('PAYMENT_DECLINED');
    expect(res.body.status).toBe('FAILED');
  });
});
