const express = require('express');
const cors = require('cors');
const { v4: uuidv4 } = require('uuid');
const { connectDB, mongoose } = require('./db');
const { startConsumer, isAmqpConnected } = require('./amqp');
const notificationRoutes = require('./routes/notificationRoutes');

const SERVICE_NAME = process.env.SERVICE_NAME || 'notification-service';
const PORT = parseInt(process.env.PORT || '8004', 10);

const app = express();

app.use(cors());
app.use(express.json());

// Initialize MongoDB and RabbitMQ Consumer
connectDB();
startConsumer();

// Correlation ID & structured logging middleware
app.use((req, res, next) => {
  const corrId = req.headers['x-correlation-id'] || `corr-${uuidv4().substring(0, 12)}`;
  req.correlationId = corrId;
  res.setHeader('X-Correlation-ID', corrId);

  const start = Date.now();
  res.on('finish', () => {
    const durationMs = Date.now() - start;
    const logEntry = {
      timestamp: new Date().toISOString(),
      service: SERVICE_NAME,
      level: res.statusCode >= 500 ? 'ERROR' : 'INFO',
      message: `${req.method} ${req.originalUrl || req.path} ${res.statusCode} ${durationMs}ms`,
      correlation_id: corrId
    };
    console.log(JSON.stringify(logEntry));
  });

  next();
});

// Health check endpoint with DB and Broker probes
app.get('/health', (req, res) => {
  const dbState = mongoose.connection.readyState;
  const dbHealthy = dbState === 1 || dbState === 2;
  const amqpHealthy = isAmqpConnected();
  const isHealthy = dbHealthy && amqpHealthy;

  res.status(isHealthy ? 200 : 503).json({
    status: isHealthy ? 'UP' : 'DEGRADED',
    service: SERVICE_NAME,
    database: dbHealthy ? 'connected' : 'disconnected',
    rabbitmq: amqpHealthy ? 'connected' : 'disconnected',
    version: '1.0.0',
    timestamp: new Date().toISOString()
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

// Mount Notification Routes
app.use('/api/v1/notifications', notificationRoutes);

// Global error handler
app.use((err, req, res, next) => {
  const corrId = req.correlationId || 'unknown';
  console.error(JSON.stringify({
    timestamp: new Date().toISOString(),
    service: SERVICE_NAME,
    level: 'ERROR',
    message: err.message,
    stack: err.stack,
    correlation_id: corrId
  }));

  res.status(err.status || 500).json({
    status: 'error',
    code: err.code || 'INTERNAL_SERVER_ERROR',
    message: err.message || 'An unexpected error occurred in notification-service',
    correlation_id: corrId,
    service: SERVICE_NAME,
    timestamp: new Date().toISOString()
  });
});

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
