const express = require('express');
const cors = require('cors');
const { createProxyMiddleware } = require('http-proxy-middleware');
const { v4: uuidv4 } = require('uuid');
const Redis = require('ioredis');

const SERVICE_NAME = process.env.SERVICE_NAME || 'api-gateway';
const PORT = parseInt(process.env.PORT || '8000', 10);
const REDIS_URL = process.env.REDIS_URL || 'redis://redis:6379';

const BOOKING_SERVICE_URL = process.env.BOOKING_SERVICE_URL || 'http://booking-service:8001';
const INVENTORY_SERVICE_URL = process.env.INVENTORY_SERVICE_URL || 'http://inventory-service:8002';
const PAYMENT_SERVICE_URL = process.env.PAYMENT_SERVICE_URL || 'http://payment-service:8003';
const TICKETING_SERVICE_URL = process.env.TICKETING_SERVICE_URL || 'http://ticketing-service:8005';
const NOTIFICATION_SERVICE_URL = process.env.NOTIFICATION_SERVICE_URL || 'http://notification-service:8004';

const RATE_LIMIT_MAX = parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '200', 10);
const RATE_LIMIT_WINDOW = parseInt(process.env.RATE_LIMIT_WINDOW_SECONDS || '60', 10);

const app = express();
app.use(cors());

// Optional Redis client with non-fatal fallback
let redis = null;
try {
  redis = new Redis(REDIS_URL, {
    retryStrategy: (times) => Math.min(times * 100, 3000),
    maxRetriesPerRequest: 1
  });
  redis.on('error', (err) => {
    // Non-fatal, log warning
  });
} catch (e) {
  // Continue without Redis rate limiter if unreachable
}

// Correlation ID & structured logging middleware
app.use((req, res, next) => {
  const corrId = req.headers['x-correlation-id'] || `corr-${uuidv4().substring(0, 12)}`;
  req.correlationId = corrId;
  res.setHeader('X-Correlation-ID', corrId);

  const start = Date.now();
  res.on('finish', () => {
    const durationMs = Date.now() - start;
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: SERVICE_NAME,
      level: res.statusCode >= 500 ? 'ERROR' : 'INFO',
      message: `${req.method} ${req.originalUrl || req.url} ${res.statusCode} ${durationMs}ms`,
      correlation_id: corrId
    }));
  });

  next();
});

// Redis Token-Bucket / Sliding Window Rate Limiting middleware
app.use(async (req, res, next) => {
  if (req.path === '/health' || !redis || redis.status !== 'ready') {
    return next();
  }

  const clientIp = req.ip || req.connection.remoteAddress || 'unknown';
  const key = `ratelimit:${clientIp}`;

  try {
    const current = await redis.incr(key);
    if (current === 1) {
      await redis.expire(key, RATE_LIMIT_WINDOW);
    }

    if (current > RATE_LIMIT_MAX) {
      return res.status(429).json({
        status: 'error',
        code: 'RATE_LIMIT_EXCEEDED',
        message: `Too many requests. Limit is ${RATE_LIMIT_MAX} per ${RATE_LIMIT_WINDOW} seconds.`,
        correlation_id: req.correlationId,
        service: SERVICE_NAME,
        timestamp: new Date().toISOString()
      });
    }
  } catch (err) {
    // Graceful bypass on cache error
  }

  next();
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({
    status: 'UP',
    service: SERVICE_NAME,
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    routes: {
      bookings: BOOKING_SERVICE_URL,
      inventory: INVENTORY_SERVICE_URL,
      payments: PAYMENT_SERVICE_URL,
      tickets: TICKETING_SERVICE_URL,
      notifications: NOTIFICATION_SERVICE_URL
    }
  });
});

app.get('/', (req, res) => {
  res.status(200).json({
    service: SERVICE_NAME,
    status: 'running',
    health: '/health',
    version: '1.0.0'
  });
});

// Helper proxy factory injecting correlation ID header
const createServiceProxy = (targetUrl) => {
  return createProxyMiddleware({
    target: targetUrl,
    changeOrigin: true,
    on: {
      proxyReq: (proxyReq, req) => {
        if (req.correlationId) {
          proxyReq.setHeader('X-Correlation-ID', req.correlationId);
        }
      },
      error: (err, req, res) => {
        const corrId = req.correlationId || 'unknown';
        console.error(JSON.stringify({
          timestamp: new Date().toISOString(),
          service: SERVICE_NAME,
          level: 'ERROR',
          message: `Proxy error forwarding to ${targetUrl}: ${err.message}`,
          correlation_id: corrId
        }));
        if (!res.headersSent) {
          res.status(503).json({
            status: 'error',
            code: 'SERVICE_UNAVAILABLE',
            message: `Downstream service at ${targetUrl} is unreachable`,
            correlation_id: corrId,
            service: SERVICE_NAME,
            timestamp: new Date().toISOString()
          });
        }
      }
    }
  });
};

// Route proxies
app.use('/api/v1/bookings', createServiceProxy(BOOKING_SERVICE_URL));
app.use('/api/v1/inventory', createServiceProxy(INVENTORY_SERVICE_URL));
app.use('/api/v1/payments', createServiceProxy(PAYMENT_SERVICE_URL));
app.use('/api/v1/tickets', createServiceProxy(TICKETING_SERVICE_URL));
app.use('/api/v1/notifications', createServiceProxy(NOTIFICATION_SERVICE_URL));

if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, '0.0.0.0', () => {
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: SERVICE_NAME,
      level: 'INFO',
      message: `${SERVICE_NAME} listening on port ${PORT}`
    }));
  });
}

module.exports = app;
