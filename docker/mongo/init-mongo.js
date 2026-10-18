// MongoDB multi-database initialization script for Database-per-Service architecture
print("Initializing payment_db...");
var paymentDb = db.getSiblingDB('payment_db');
paymentDb.createUser({
  user: 'payment_user',
  pwd: 'payment_pass',
  roles: [{ role: 'readWrite', db: 'payment_db' }]
});
paymentDb.createCollection('payments');
paymentDb.createCollection('idempotency_records');
paymentDb.idempotency_records.createIndex({ idempotency_key: 1 }, { unique: true });

print("Initializing notification_db...");
var notifDb = db.getSiblingDB('notification_db');
notifDb.createUser({
  user: 'notif_user',
  pwd: 'notif_pass',
  roles: [{ role: 'readWrite', db: 'notification_db' }]
});
notifDb.createCollection('notification_logs');
notifDb.createCollection('processed_events');
notifDb.processed_events.createIndex({ event_id: 1 }, { unique: true });

print("MongoDB initialization complete.");
