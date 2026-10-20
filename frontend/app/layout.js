import './globals.css';

export const viewport = {
  width: 'device-width',
  initialScale: 1
};

export const metadata = {
  title: 'SeatLock | High-Concurrency Flash-Sale Ticket Reservation Platform',
  description: 'Enterprise microservices cockpit for IRCTC Railway Tatkal, Concert Flash-Sales, and Luxury Bus Sleeper Reservations.',
  keywords: 'SeatLock, Microservices, Tatkal, IRCTC, Distributed Saga, Idempotency, Concurrency, RabbitMQ, PostgreSQL, MongoDB'
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⚡</text></svg>" />
      </head>
      <body>{children}</body>
    </html>
  );
}
