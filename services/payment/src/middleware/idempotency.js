const crypto = require('crypto');
const IdempotencyRecord = require('../models/IdempotencyRecord');

// Recursively sort object keys for deterministic canonical JSON stringification
const canonicalize = (obj) => {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }
  if (Array.isArray(obj)) {
    return obj.map(canonicalize);
  }
  const sortedKeys = Object.keys(obj).sort();
  const result = {};
  for (const key of sortedKeys) {
    result[key] = canonicalize(obj[key]);
  }
  return result;
};

const computeFingerprint = (method, path, body) => {
  const canonicalBody = JSON.stringify(canonicalize(body || {}));
  const rawString = `${method.toUpperCase()}:${path}:${canonicalBody}`;
  return crypto.createHash('sha256').update(rawString).digest('hex');
};

const waitForCompletion = async (key, maxWaitMs = 2500) => {
  const startTime = Date.now();
  while (Date.now() - startTime < maxWaitMs) {
    await new Promise((resolve) => setTimeout(resolve, 100));
    const rec = await IdempotencyRecord.findOne({ idempotency_key: key });
    if (rec && rec.status === 'COMPLETED') {
      return rec;
    }
  }
  return null;
};

const idempotencyMiddleware = async (req, res, next) => {
  // Only enforce for state-mutating requests (POST, PUT, PATCH)
  if (!['POST', 'PUT', 'PATCH'].includes(req.method)) {
    return next();
  }

  const idempotencyKey = req.headers['idempotency-key'] || req.headers['x-idempotency-key'];

  if (!idempotencyKey) {
    return res.status(400).json({
      status: 'error',
      code: 'MISSING_IDEMPOTENCY_KEY',
      message: 'Idempotency-Key header is required for unsafe payment operations.',
      correlation_id: req.correlationId || 'unknown',
      service: process.env.SERVICE_NAME || 'payment-service',
      timestamp: new Date().toISOString()
    });
  }

  const fingerprint = computeFingerprint(req.method, req.path, req.body);

  try {
    // 1. Check for existing idempotency record
    const existing = await IdempotencyRecord.findOne({ idempotency_key: idempotencyKey });

    if (existing) {
      // Case 1: Payload mismatch with existing key (BR3 violation prevention)
      if (existing.request_fingerprint !== fingerprint) {
        return res.status(422).json({
          status: 'error',
          code: 'IDEMPOTENCY_PAYLOAD_MISMATCH',
          message: 'Idempotency-Key re-used with a different request payload.',
          correlation_id: req.correlationId || 'unknown',
          service: process.env.SERVICE_NAME || 'payment-service',
          timestamp: new Date().toISOString(),
          details: {
            idempotency_key: idempotencyKey,
            stored_fingerprint: existing.request_fingerprint,
            received_fingerprint: fingerprint
          }
        });
      }

      // Case 2: In-flight duplicate call -> Poll for completion
      if (existing.status === 'PENDING') {
        const completedRecord = await waitForCompletion(idempotencyKey);
        if (completedRecord) {
          res.setHeader('X-Idempotent-Replay', 'true');
          return res.status(completedRecord.status_code).json(completedRecord.response_body);
        }

        return res.status(409).json({
          status: 'error',
          code: 'CONCURRENT_REQUEST_IN_FLIGHT',
          message: 'A request with this Idempotency-Key is currently being processed. Please retry in a moment.',
          correlation_id: req.correlationId || 'unknown',
          service: process.env.SERVICE_NAME || 'payment-service',
          timestamp: new Date().toISOString()
        });
      }

      // Case 3: Completed duplicate call -> Return cached replay
      if (existing.status === 'COMPLETED') {
        res.setHeader('X-Idempotent-Replay', 'true');
        return res.status(existing.status_code).json(existing.response_body);
      }
    }

    // 2. First-time request: Atomically acquire PENDING lock
    try {
      await IdempotencyRecord.create({
        idempotency_key: idempotencyKey,
        request_fingerprint: fingerprint,
        status: 'PENDING'
      });
    } catch (createErr) {
      // Unique constraint race condition: Another concurrent thread won insertion
      if (createErr.code === 11000) {
        const completedRecord = await waitForCompletion(idempotencyKey);
        if (completedRecord) {
          res.setHeader('X-Idempotent-Replay', 'true');
          return res.status(completedRecord.status_code).json(completedRecord.response_body);
        }

        return res.status(409).json({
          status: 'error',
          code: 'CONCURRENT_IDEMPOTENCY_RACE',
          message: 'Concurrent duplicate request detected and timed out awaiting result.',
          correlation_id: req.correlationId || 'unknown',
          service: process.env.SERVICE_NAME || 'payment-service',
          timestamp: new Date().toISOString()
        });
      }
      throw createErr;
    }

    // 3. Intercept res.json to capture and persist the final response
    const originalJson = res.json.bind(res);
    res.json = async function (body) {
      try {
        await IdempotencyRecord.updateOne(
          { idempotency_key: idempotencyKey },
          {
            $set: {
              status: res.statusCode >= 400 && res.statusCode !== 402 ? 'FAILED' : 'COMPLETED',
              status_code: res.statusCode,
              response_body: body,
              updated_at: new Date()
            }
          }
        );
      } catch (saveErr) {
        console.error('Failed to update idempotency cache:', saveErr);
      }
      return originalJson(body);
    };

    next();
  } catch (err) {
    next(err);
  }
};

module.exports = {
  idempotencyMiddleware,
  computeFingerprint,
  canonicalize
};
