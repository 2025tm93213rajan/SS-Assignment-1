const amqp = require('amqplib');
const { v4: uuidv4 } = require('uuid');
const NotificationLog = require('./models/NotificationLog');
const ProcessedEvent = require('./models/ProcessedEvent');

const RABBITMQ_URL = process.env.RABBITMQ_URL || 'amqp://guest:guest@rabbitmq:5672/';
const EXCHANGE_NAME = process.env.RABBITMQ_EXCHANGE || 'seatlock.events';
const QUEUE_NAME = process.env.RABBITMQ_QUEUE || 'booking.notifications';

let channel = null;
let connection = null;

const startConsumer = async () => {
  try {
    connection = await amqp.connect(RABBITMQ_URL);
    channel = await connection.createChannel();

    // Declare durable topic exchange and durable queue
    await channel.assertExchange(EXCHANGE_NAME, 'topic', { durable: true });
    await channel.assertQueue(QUEUE_NAME, { durable: true });

    // Bind queue to booking confirmation and ticketing events
    await channel.bindQueue(QUEUE_NAME, EXCHANGE_NAME, 'booking.*');
    await channel.bindQueue(QUEUE_NAME, EXCHANGE_NAME, 'ticket.*');

    await channel.prefetch(10);

    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: process.env.SERVICE_NAME || 'notification-service',
      level: 'INFO',
      message: `RabbitMQ Consumer connected. Listening on queue '${QUEUE_NAME}'`
    }));

    channel.consume(QUEUE_NAME, async (msg) => {
      if (!msg) return;

      const rawContent = msg.content.toString();
      try {
        const event = JSON.parse(rawContent);
        const eventId = event.event_id || event.booking_id;
        const correlationId = msg.properties.correlationId || event.correlation_id || 'unknown';

        // 1. Consumer-side Idempotency Check (Challenge 3D Requirement)
        const alreadyProcessed = await ProcessedEvent.findOne({ event_id: eventId });
        if (alreadyProcessed) {
          console.log(JSON.stringify({
            timestamp: new Date().toISOString(),
            service: process.env.SERVICE_NAME || 'notification-service',
            level: 'WARN',
            message: `[IDEMPOTENT CONSUMER] Duplicate event '${eventId}' discarded without re-dispatch.`,
            correlation_id: correlationId
          }));
          channel.ack(msg);
          return;
        }

        // 2. Format and dispatch notification (Mock SMS / Email)
        const bookingId = event.booking_id || 'unknown';
        const recipient = event.customer_phone || event.customer_email || '+91-9876543210';
        const pnr = event.pnr || 'N/A';
        const title = event.event_name || 'SeatLock Reservation';

        let messageText = '';
        if (event.category === 'RAILWAY_TATKAL' || (pnr && pnr.includes('TATKAL'))) {
          messageText = `IRCTC Tatkal Ticket Confirmed! PNR: ${pnr} | Train: ${title} | Berths: ${event.berths || 'Assigned'} | Happy Journey!`;
        } else if (event.category === 'CONCERT_EVENT' || (pnr && pnr.includes('CONCERT'))) {
          messageText = `SeatLock Concert Pass Confirmed! Pass: ${pnr} | Show: ${title} | Gates open 2 hrs before showtime.`;
        } else {
          messageText = `Booking Confirmed! Reference: ${bookingId} | PNR: ${pnr} | Amount Paid: INR ${event.amount || 'N/A'}`;
        }

        // 3. Persist delivery audit log
        await NotificationLog.create({
          notification_id: `notif-${uuidv4().substring(0, 16)}`,
          event_id: eventId,
          booking_id: bookingId,
          recipient,
          channel: 'SMS',
          message: messageText,
          status: 'DELIVERED',
          metadata: {
            pnr,
            correlation_id: correlationId,
            routing_key: msg.fields.routingKey
          }
        });

        // 4. Mark event as processed
        await ProcessedEvent.create({ event_id: eventId });

        console.log(JSON.stringify({
          timestamp: new Date().toISOString(),
          service: process.env.SERVICE_NAME || 'notification-service',
          level: 'INFO',
          message: `[DISPATCHED] Notification sent for booking '${bookingId}', PNR '${pnr}'`,
          correlation_id: correlationId
        }));

        channel.ack(msg);
      } catch (err) {
        console.error('Error processing notification event:', err);
        // Nack without requeue if malformed JSON, or requeue if transient
        channel.nack(msg, false, false);
      }
    });

    connection.on('error', (err) => {
      console.error('RabbitMQ connection error:', err);
    });

    connection.on('close', () => {
      console.warn('RabbitMQ connection closed. Reconnecting in 5s...');
      setTimeout(startConsumer, 5000);
    });

  } catch (err) {
    console.error('Failed to connect to RabbitMQ:', err.message);
    setTimeout(startConsumer, 5000);
  }
};

const publishEvent = async (routingKey, eventData) => {
  if (!channel) {
    throw new Error('RabbitMQ channel is not available.');
  }
  const buffer = Buffer.from(JSON.stringify(eventData));
  return channel.publish(EXCHANGE_NAME, routingKey, buffer, {
    persistent: true,
    correlationId: eventData.correlation_id || `corr-${uuidv4().substring(0, 12)}`
  });
};

const isAmqpConnected = () => connection !== null && channel !== null;

module.exports = {
  startConsumer,
  publishEvent,
  isAmqpConnected
};
