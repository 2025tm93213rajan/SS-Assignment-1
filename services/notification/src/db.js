const mongoose = require('mongoose');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://notif_user:notif_pass@mongo:27017/notification_db?authSource=notification_db';

let isConnected = false;

const connectDB = async () => {
  if (isConnected) return;
  try {
    await mongoose.connect(MONGO_URI, {
      maxPoolSize: 20,
      serverSelectionTimeoutMS: 5000,
    });
    isConnected = true;
    console.log(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: process.env.SERVICE_NAME || 'notification-service',
      level: 'INFO',
      message: 'Connected to MongoDB (notification_db)'
    }));
  } catch (error) {
    console.error(JSON.stringify({
      timestamp: new Date().toISOString(),
      service: process.env.SERVICE_NAME || 'notification-service',
      level: 'ERROR',
      message: `MongoDB connection error: ${error.message}`
    }));
  }
};

module.exports = { connectDB, mongoose };
