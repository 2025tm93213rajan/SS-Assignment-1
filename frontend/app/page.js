'use client';

import React, { useState, useEffect } from 'react';
import { 
  Zap, Server, Database, CheckCircle2, AlertTriangle, 
  XCircle, RefreshCw, ShieldCheck, Cpu, ArrowRight,
  Train, Music, Bus, CreditCard, Ticket, Bell, Sparkles, Flame, Check, Lock
} from 'lucide-react';

const GATEWAY_URL = 'http://localhost:8000/api/v1';

export default function Home() {
  const [activeTab, setActiveTab] = useState('reservations');
  const [servicesHealth, setServicesHealth] = useState({
    gateway: { status: 'CHECKING', latency: 0 },
    booking: { status: 'CHECKING', latency: 0 },
    inventory: { status: 'CHECKING', latency: 0 },
    payment: { status: 'CHECKING', latency: 0 },
    ticketing: { status: 'CHECKING', latency: 0 },
    notification: { status: 'CHECKING', latency: 0 }
  });

  // Selected Domain: TATKAL, CONCERT, BUS
  const [selectedDomain, setSelectedDomain] = useState('TATKAL');
  const [inventoryState, setInventoryState] = useState({
    'TATKAL-12951-B1': { available: 5, total: 5, price: 2850 },
    'CONCERT-COLDPLAY-VIP': { available: 10, total: 10, price: 12500 },
    'BUS-BLR-GOA-SL': { available: 8, total: 8, price: 1650 }
  });

  // Reservation Form State
  const [passengerName, setPassengerName] = useState('Rajan Sharma');
  const [passengerEmail, setPassengerEmail] = useState('rajan.sharma@example.com');
  const [passengerPhone, setPassengerPhone] = useState('+91-9876543210');
  const [selectedBerths, setSelectedBerths] = useState(['LOWER']);
  const [paymentCardType, setPaymentCardType] = useState('4000-0000-0000-0001'); // 0001=OK, 0002=Decline
  const [bookingLoading, setBookingLoading] = useState(false);
  const [latestBooking, setLatestBooking] = useState(null);
  const [bookingError, setBookingError] = useState(null);

  // Challenge 1: Concurrency Test State
  const [concurrencyRunning, setConcurrencyRunning] = useState(false);
  const [concurrencyResults, setConcurrencyResults] = useState(null);

  // Challenge 2: Idempotency Test State
  const [idempotencyKey, setIdempotencyKey] = useState('');
  const [idempotencyAmount, setIdempotencyAmount] = useState(2850);
  const [idempotencyResults, setIdempotencyResults] = useState([]);
  const [idempotencyLoading, setIdempotencyLoading] = useState(false);

  // Challenge 3D: Notifications Feed
  const [notifications, setNotifications] = useState([]);

  // Fetch Health & Inventory on Mount
  useEffect(() => {
    checkHealth();
    fetchInventory();
    fetchNotifications();
    setIdempotencyKey(`key-${Math.floor(Date.now() / 1000)}`);
    const timer = setInterval(() => {
      fetchInventory();
      fetchNotifications();
    }, 5000);
    return () => clearInterval(timer);
  }, []);

  const checkHealth = async () => {
    const endpoints = [
      { key: 'gateway', url: 'http://localhost:8000/health' },
      { key: 'booking', url: 'http://localhost:8001/health' },
      { key: 'inventory', url: 'http://localhost:8002/health' },
      { key: 'payment', url: 'http://localhost:8003/health' },
      { key: 'ticketing', url: 'http://localhost:8005/health' },
      { key: 'notification', url: 'http://localhost:8004/health' }
    ];

    const results = {};
    for (const ep of endpoints) {
      const t0 = performance.now();
      try {
        const res = await fetch(ep.url, { cache: 'no-store' });
        const latency = Math.round(performance.now() - t0);
        results[ep.key] = {
          status: res.ok ? 'UP' : 'DEGRADED',
          latency
        };
      } catch (err) {
        results[ep.key] = { status: 'DOWN', latency: 0 };
      }
    }
    setServicesHealth(results);
  };

  const fetchInventory = async () => {
    try {
      const quotas = ['TATKAL-12951-B1', 'CONCERT-COLDPLAY-VIP', 'BUS-BLR-GOA-SL'];
      const updated = { ...inventoryState };
      for (const q of quotas) {
        const res = await fetch(`${GATEWAY_URL}/inventory/quotas/${q}`);
        if (res.ok) {
          const data = await res.json();
          updated[q] = {
            available: data.available_seats,
            total: data.total_capacity,
            price: data.price
          };
        }
      }
      setInventoryState(updated);
    } catch (e) {
      // Gateway might be restarting
    }
  };

  const fetchNotifications = async () => {
    try {
      const res = await fetch(`${GATEWAY_URL}/notifications/logs`);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data.slice(0, 10));
      }
    } catch (e) {}
  };

  const handleResetAll = async () => {
    try {
      await fetch(`${GATEWAY_URL}/inventory/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      await fetch(`${GATEWAY_URL}/payments/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      await fetch(`${GATEWAY_URL}/tickets/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      await fetch(`${GATEWAY_URL}/notifications/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      await fetch(`${GATEWAY_URL}/bookings/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      await fetchInventory();
      await fetchNotifications();
      setLatestBooking(null);
      setBookingError(null);
      setConcurrencyResults(null);
      setIdempotencyResults([]);
    } catch (e) {
      alert('Reset completed with partial network notification.');
    }
  };

  const handleBookingSubmit = async (e) => {
    e?.preventDefault();
    setBookingLoading(true);
    setBookingError(null);
    setLatestBooking(null);

    const quotaId = selectedDomain === 'TATKAL' ? 'TATKAL-12951-B1' 
                  : selectedDomain === 'CONCERT' ? 'CONCERT-COLDPLAY-VIP' 
                  : 'BUS-BLR-GOA-SL';
    
    const eventName = selectedDomain === 'TATKAL' ? 'Mumbai Tejas Rajdhani Express (#12951)'
                    : selectedDomain === 'CONCERT' ? 'Coldplay Music of the Spheres VIP'
                    : 'Intercity Volvo Luxury Sleeper';

    const category = selectedDomain === 'TATKAL' ? 'RAILWAY_TATKAL'
                   : selectedDomain === 'CONCERT' ? 'CONCERT_EVENT'
                   : 'EXPRESS_BUS';

    const pricePerSeat = inventoryState[quotaId]?.price || 2850;
    const totalAmount = pricePerSeat * selectedBerths.length;

    const payload = {
      quota_id: quotaId,
      event_name: eventName,
      category,
      passengers: selectedBerths.map((b, i) => ({
        name: i === 0 ? passengerName : `${passengerName} (P${i+1})`,
        berth_preference: b
      })),
      total_amount: totalAmount,
      customer_name: passengerName,
      customer_email: passengerEmail,
      customer_phone: passengerPhone,
      payment: {
        payment_method: 'CARD',
        card_number: paymentCardType,
        force_failure: false
      }
    };

    try {
      const res = await fetch(`${GATEWAY_URL}/bookings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.status === 201) {
        setLatestBooking(data);
      } else {
        setBookingError(data);
      }
      await fetchInventory();
      await fetchNotifications();
    } catch (err) {
      setBookingError({ error: err.message, status: 'FAILED_NETWORK' });
    } finally {
      setBookingLoading(false);
    }
  };

  // Challenge 1 Runner: 20 simultaneous threads
  const runConcurrencyChallenge = async () => {
    setConcurrencyRunning(true);
    setConcurrencyResults(null);
    const quotaId = 'TATKAL-12951-B1';

    const requests = Array.from({ length: 20 }, (_, i) => ({
      threadId: i + 1,
      quota_id: quotaId,
      quantity: 1,
      booking_id: `burst-user-${i+1}`
    }));

    const results = await Promise.all(
      requests.map(async (req) => {
        const t0 = performance.now();
        try {
          const res = await fetch(`${GATEWAY_URL}/inventory/reserve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req)
          });
          const timeMs = Math.round(performance.now() - t0);
          const data = await res.json();
          return {
            threadId: req.threadId,
            status: res.status,
            success: res.status === 201,
            timeMs,
            token: data.reservation_token || null,
            message: data.message || (res.status === 201 ? 'Seat Reserved' : 'Sold Out')
          };
        } catch (err) {
          return { threadId: req.threadId, status: 500, success: false, timeMs: 0, message: err.message };
        }
      })
    );

    const successful = results.filter(r => r.success).length;
    const rejected = results.filter(r => !r.success).length;

    await fetchInventory();
    setConcurrencyResults({
      total: 20,
      successful,
      rejected,
      threads: results
    });
    setConcurrencyRunning(false);
  };

  // Challenge 2: Idempotency execution
  const executeIdempotencyCharge = async (tampered = false) => {
    setIdempotencyLoading(true);
    const amount = tampered ? idempotencyAmount + 1000 : idempotencyAmount;
    const payload = {
      booking_id: `test-idemp-${idempotencyKey.slice(-6)}`,
      amount,
      currency: 'INR',
      payment_method: 'CARD',
      card_number: '4000-0000-0000-0001'
    };

    const t0 = performance.now();
    try {
      const res = await fetch(`${GATEWAY_URL}/payments/charge`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey
        },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      const replayHeader = res.headers.get('X-Idempotent-Replay');
      const timeMs = Math.round(performance.now() - t0);

      setIdempotencyResults(prev => [
        {
          timestamp: new Date().toLocaleTimeString(),
          key: idempotencyKey,
          amount,
          status: res.status,
          replayed: replayHeader === 'true' || data.replayed === true,
          fingerprint: data.fingerprint || (data.details?.received_fingerprint) || 'N/A',
          data
        },
        ...prev
      ]);
    } catch (e) {
      alert(`Payment test error: ${e.message}`);
    } finally {
      setIdempotencyLoading(false);
    }
  };

  const currentQuotaKey = selectedDomain === 'TATKAL' ? 'TATKAL-12951-B1' 
                        : selectedDomain === 'CONCERT' ? 'CONCERT-COLDPLAY-VIP' 
                        : 'BUS-BLR-GOA-SL';
  const currentQuota = inventoryState[currentQuotaKey] || { available: 0, total: 5, price: 2850 };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', padding: '24px 20px' }}>
      
      {/* 1. Header & Live Microservices Health Bar */}
      <header className="glass-panel" style={{ padding: '20px 24px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{ background: 'linear-gradient(135deg, #6366f1, #06b6d4)', padding: '10px', borderRadius: '12px', display: 'flex' }}>
                <Zap size={24} color="#fff" />
              </div>
              <div>
                <h1 style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(90deg, #fff 0%, #cbd5e1 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                  SeatLock Cockpit
                </h1>
                <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Distributed High-Concurrency Flash-Sale Reservation Platform &bull; SEZG583
                </p>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <button className="btn-secondary" onClick={handleResetAll} id="reset-system-btn" title="Clears and resets all 5 databases">
              <RefreshCw size={15} /> Reset All Databases
            </button>
            <button className="btn-secondary" onClick={checkHealth} id="refresh-health-btn">
              <RefreshCw size={15} /> Check Health
            </button>
          </div>
        </div>

        {/* Live Service Status Pills */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '10px', marginTop: '18px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          {Object.entries(servicesHealth).map(([srv, info]) => (
            <div key={srv} style={{ background: 'rgba(0,0,0,0.25)', padding: '8px 12px', borderRadius: '8px', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Server size={14} color="var(--text-dim)" />
                <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'capitalize' }}>{srv}</span>
              </div>
              <span className={info.status === 'UP' ? 'badge-up' : info.status === 'DEGRADED' ? 'badge-degraded' : 'badge-down'}>
                <span className="pulse-dot" style={{ backgroundColor: info.status === 'UP' ? '#34d399' : '#f43f5e' }}></span>
                {info.status} {info.latency > 0 && `(${info.latency}ms)`}
              </span>
            </div>
          ))}
        </div>
      </header>

      {/* 2. Interactive Navigation Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border-subtle)', marginBottom: '24px', overflowX: 'auto' }}>
        <button className={`tab-btn ${activeTab === 'reservations' ? 'active' : ''}`} onClick={() => setActiveTab('reservations')} id="tab-reservations">
          <Ticket size={18} /> Live Reservations (Tatkal / Concert / Bus)
        </button>
        <button className={`tab-btn ${activeTab === 'concurrency' ? 'active' : ''}`} onClick={() => setActiveTab('concurrency')} id="tab-concurrency">
          <Flame size={18} /> Challenge 1: Concurrency Arena (BR1 & BR2)
        </button>
        <button className={`tab-btn ${activeTab === 'idempotency' ? 'active' : ''}`} onClick={() => setActiveTab('idempotency')} id="tab-idempotency">
          <ShieldCheck size={18} /> Challenge 2: Idempotency Lab (BR3)
        </button>
        <button className={`tab-btn ${activeTab === 'saga' ? 'active' : ''}`} onClick={() => setActiveTab('saga')} id="tab-saga">
          <Cpu size={18} /> Challenge 3C: Saga Orchestrator (BR4)
        </button>
        <button className={`tab-btn ${activeTab === 'notifications' ? 'active' : ''}`} onClick={() => setActiveTab('notifications')} id="tab-notifications">
          <Bell size={18} /> Challenge 3D: AMQP Event Feed
        </button>
      </div>

      {/* =========================================================================
          TAB 1: LIVE RESERVATION COCKPIT (TATKAL / CONCERT / BUS)
         ========================================================================= */}
      {activeTab === 'reservations' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '24px' }}>
          
          {/* Left Column: Domain Selector & Seat Grid */}
          <div>
            {/* Domain Switcher */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginBottom: '20px' }}>
              <div 
                onClick={() => { setSelectedDomain('TATKAL'); setSelectedBerths(['LOWER']); }}
                className="glass-panel" 
                style={{ 
                  padding: '16px', cursor: 'pointer', 
                  borderColor: selectedDomain === 'TATKAL' ? 'var(--primary)' : 'var(--border-subtle)',
                  background: selectedDomain === 'TATKAL' ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-card)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Train size={20} color="#6366f1" />
                  <span className="badge-up">TATKAL 10:00 AM</span>
                </div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Mumbai Tejas Rajdhani</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Coach B1 (AC 3-Tier)</p>
                <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                  <span>Price: ₹2,850</span>
                  <strong style={{ color: inventoryState['TATKAL-12951-B1']?.available > 0 ? '#34d399' : '#f43f5e' }}>
                    {inventoryState['TATKAL-12951-B1']?.available} / {inventoryState['TATKAL-12951-B1']?.total} Left
                  </strong>
                </div>
              </div>

              <div 
                onClick={() => { setSelectedDomain('CONCERT'); setSelectedBerths(['VIP']); }}
                className="glass-panel" 
                style={{ 
                  padding: '16px', cursor: 'pointer',
                  borderColor: selectedDomain === 'CONCERT' ? 'var(--cyan)' : 'var(--border-subtle)',
                  background: selectedDomain === 'CONCERT' ? 'rgba(6, 182, 212, 0.15)' : 'var(--bg-card)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Music size={20} color="#06b6d4" />
                  <span className="badge-up" style={{ color: '#22d3ee', borderColor: 'rgba(6, 182, 212, 0.4)' }}>FLASH-SALE</span>
                </div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Coldplay World Tour</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>VIP Lounge & Standing Pit</p>
                <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                  <span>Price: ₹12,500</span>
                  <strong style={{ color: '#22d3ee' }}>
                    {inventoryState['CONCERT-COLDPLAY-VIP']?.available} / {inventoryState['CONCERT-COLDPLAY-VIP']?.total} Left
                  </strong>
                </div>
              </div>

              <div 
                onClick={() => { setSelectedDomain('BUS'); setSelectedBerths(['LOWER']); }}
                className="glass-panel" 
                style={{ 
                  padding: '16px', cursor: 'pointer',
                  borderColor: selectedDomain === 'BUS' ? 'var(--emerald)' : 'var(--border-subtle)',
                  background: selectedDomain === 'BUS' ? 'rgba(16, 185, 129, 0.15)' : 'var(--bg-card)'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Bus size={20} color="#10b981" />
                  <span className="badge-up">EXPRESS SLEEPER</span>
                </div>
                <h3 style={{ fontSize: '0.95rem', fontWeight: 700 }}>Volvo 9600 Multi-Axle</h3>
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>BLR &rarr; GOA Coastal Line</p>
                <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
                  <span>Price: ₹1,650</span>
                  <strong style={{ color: '#34d399' }}>
                    {inventoryState['BUS-BLR-GOA-SL']?.available} / {inventoryState['BUS-BLR-GOA-SL']?.total} Left
                  </strong>
                </div>
              </div>
            </div>

            {/* Interactive Coach Seat Map */}
            <div className="glass-panel" style={{ padding: '24px', marginBottom: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                    {selectedDomain === 'TATKAL' ? 'IRCTC Coach B1 Berth Matrix' : selectedDomain === 'CONCERT' ? 'Concert Lounge Pass Matrix' : 'Volvo Luxury Sleeper Berths'}
                  </h3>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    Atomic conditional decrement guarantees zero over-allocation
                  </p>
                </div>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.75rem' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#34d399' }}><Check size={12} /> Available ({currentQuota.available})</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#818cf8' }}><Zap size={12} /> Selected ({selectedBerths.length})</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px', color: '#fb7185' }}><Lock size={12} /> Sold ({currentQuota.total - currentQuota.available})</span>
                </div>
              </div>

              {/* Berth Cards */}
              <div className="seat-grid">
                {Array.from({ length: currentQuota.total }, (_, i) => {
                  const isAvailable = i < currentQuota.available;
                  const berthNumber = i + 1;
                  const berthType = selectedDomain === 'TATKAL' 
                    ? (berthNumber % 3 === 1 ? 'LOWER' : berthNumber % 3 === 2 ? 'MIDDLE' : 'UPPER')
                    : selectedDomain === 'CONCERT' ? 'VIP' : (berthNumber % 2 === 1 ? 'LOWER' : 'UPPER');
                  const isSelected = selectedBerths.includes(berthType) && isAvailable;

                  return (
                    <div 
                      key={berthNumber}
                      onClick={() => {
                        if (!isAvailable) return;
                        setSelectedBerths([berthType]);
                      }}
                      className={`seat-card ${isSelected ? 'selected' : isAvailable ? 'available' : 'reserved'}`}
                    >
                      <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)' }}>
                        {selectedDomain === 'TATKAL' ? `B1-${berthNumber}` : selectedDomain === 'CONCERT' ? `VIP-${berthNumber}` : `SL-${berthNumber}`}
                      </div>
                      <div style={{ fontSize: '0.9rem', fontWeight: 800, margin: '4px 0' }}>{berthType}</div>
                      <div style={{ fontSize: '0.68rem' }}>{isAvailable ? '₹' + currentQuota.price : 'SOLD OUT'}</div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Saga Result Notification / Ticket Card */}
            {latestBooking && (
              <div className="glass-panel" style={{ padding: '20px', borderColor: 'rgba(16, 185, 129, 0.4)', background: 'rgba(16, 185, 129, 0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#34d399' }}>
                    <CheckCircle2 size={20} />
                    <strong style={{ fontSize: '1rem' }}>Saga Successfully Completed (CONFIRMED)</strong>
                  </div>
                  <span className="badge-up">PNR: {latestBooking.pnr}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', fontSize: '0.82rem', marginBottom: '14px' }}>
                  <div><span style={{ color: 'var(--text-dim)' }}>Booking ID:</span><br /><code>{latestBooking.booking_id}</code></div>
                  <div><span style={{ color: 'var(--text-dim)' }}>Payment ID:</span><br /><code>{latestBooking.payment_id}</code></div>
                  <div><span style={{ color: 'var(--text-dim)' }}>Amount Paid:</span><br /><strong>INR ₹{latestBooking.total_amount}</strong></div>
                </div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  RabbitMQ event published &bull; SMS confirmation dispatched to {latestBooking.customer_phone}.
                </div>
              </div>
            )}

            {bookingError && (
              <div className="glass-panel" style={{ padding: '20px', borderColor: 'rgba(244, 63, 94, 0.4)', background: 'rgba(244, 63, 94, 0.08)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fb7185', marginBottom: '8px' }}>
                  <XCircle size={20} />
                  <strong style={{ fontSize: '1rem' }}>Saga Rollback Triggered ({bookingError.status || 'FAILED'})</strong>
                </div>
                <p style={{ fontSize: '0.85rem', color: '#fda4af', marginBottom: '12px' }}>
                  {bookingError.error || bookingError.booking?.compensation_reason || 'Transaction could not be completed.'}
                </p>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  <strong>BR4 Invariant Preserved:</strong> The held inventory seats were automatically released back into the pool. Zero leakage.
                </div>
              </div>
            )}
          </div>

          {/* Right Column: Checkout & Saga Execution Panel */}
          <div>
            <div className="glass-panel" style={{ padding: '24px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <CreditCard size={18} color="#6366f1" /> Fast Checkout
              </h3>

              <form onSubmit={handleBookingSubmit}>
                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Passenger Name</label>
                  <input 
                    type="text" 
                    value={passengerName} 
                    onChange={e => setPassengerName(e.target.value)}
                    required
                    style={{ width: '100%', padding: '10px 12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Email</label>
                  <input 
                    type="email" 
                    value={passengerEmail} 
                    onChange={e => setPassengerEmail(e.target.value)}
                    required
                    style={{ width: '100%', padding: '10px 12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Phone (For SMS alerts via AMQP)</label>
                  <input 
                    type="text" 
                    value={passengerPhone} 
                    onChange={e => setPassengerPhone(e.target.value)}
                    required
                    style={{ width: '100%', padding: '10px 12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '8px', color: '#fff', fontSize: '0.85rem' }}
                  />
                </div>

                {/* Simulated Payment Card Instrument */}
                <div style={{ marginBottom: '18px' }}>
                  <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '6px' }}>Payment Simulator (BR3 / BR4)</label>
                  <select 
                    value={paymentCardType} 
                    onChange={e => setPaymentCardType(e.target.value)}
                    style={{ width: '100%', padding: '10px 12px', background: 'rgba(0,0,0,0.4)', border: '1px solid var(--border-subtle)', borderRadius: '8px', color: '#fff', fontSize: '0.85rem' }}
                  >
                    <option value="4000-0000-0000-0001">Approved Card (...0001) &rarr; Happy Path Saga</option>
                    <option value="4000-0000-0000-0002">Declined Card (...0002) &rarr; Trigger BR4 Compensation</option>
                  </select>
                </div>

                {/* Price Breakdown */}
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '14px', borderRadius: '8px', marginBottom: '18px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', marginBottom: '6px', color: 'var(--text-muted)' }}>
                    <span>Selected Berths:</span>
                    <span>{selectedBerths.join(', ')}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '1rem', fontWeight: 700 }}>
                    <span>Total Amount:</span>
                    <span style={{ color: '#38bdf8' }}>₹{currentQuota.price * selectedBerths.length}</span>
                  </div>
                </div>

                <button 
                  type="submit" 
                  disabled={bookingLoading || currentQuota.available === 0} 
                  className="btn-primary" 
                  style={{ width: '100%', justifyContent: 'center' }}
                  id="submit-booking-btn"
                >
                  {bookingLoading ? <RefreshCw className="animate-spin" size={18} /> : <Zap size={18} />}
                  {currentQuota.available === 0 ? 'SOLD OUT' : 'Reserve & Orchestrate Saga'}
                </button>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 2: CHALLENGE 1: CONCURRENCY ARENA (BR1 & BR2)
         ========================================================================= */}
      {activeTab === 'concurrency' && (
        <div>
          <div className="glass-panel" style={{ padding: '24px', marginBottom: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Flame size={22} color="#f43f5e" /> Challenge 1: High-Concurrency 20-Thread Race
                </h2>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '750px' }}>
                  Demonstrates <strong>Business Rules 1 & 2</strong>: Fires 20 simultaneous parallel HTTP requests against Tatkal inventory with 5 available seats.
                  The PostgreSQL atomic conditional decrement guarantees exactly 5 succeed and 15 are rejected with HTTP 409 Conflict (Zero Over-allocation).
                </p>
              </div>

              <button 
                onClick={runConcurrencyChallenge} 
                disabled={concurrencyRunning} 
                className="btn-danger"
                id="run-concurrency-btn"
              >
                {concurrencyRunning ? <RefreshCw className="animate-spin" size={18} /> : <Flame size={18} />}
                Launch 20 Parallel Requests Burst
              </button>
            </div>

            {/* Results Counter */}
            {concurrencyResults && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginTop: '24px' }}>
                <div style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '10px', textAlign: 'center', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-dim)' }}>TOTAL REQUESTS</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800 }}>{concurrencyResults.total}</div>
                </div>
                <div style={{ background: 'rgba(16, 185, 129, 0.1)', padding: '16px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                  <div style={{ fontSize: '0.8rem', color: '#34d399' }}>ACCEPTED (201 CREATED)</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#34d399' }}>{concurrencyResults.successful}</div>
                </div>
                <div style={{ background: 'rgba(244, 63, 94, 0.1)', padding: '16px', borderRadius: '10px', textAlign: 'center', border: '1px solid rgba(244, 63, 94, 0.3)' }}>
                  <div style={{ fontSize: '0.8rem', color: '#fb7185' }}>REJECTED (409 CONFLICT)</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#fb7185' }}>{concurrencyResults.rejected}</div>
                </div>
              </div>
            )}
          </div>

          {/* Thread Cards Grid */}
          {concurrencyResults && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px' }}>
              {concurrencyResults.threads.map(t => (
                <div 
                  key={t.threadId} 
                  className="glass-panel" 
                  style={{ 
                    padding: '14px',
                    borderColor: t.success ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.3)',
                    background: t.success ? 'rgba(16, 185, 129, 0.08)' : 'rgba(244, 63, 94, 0.05)'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)' }}>Thread #{t.threadId}</span>
                    <span className={t.success ? 'badge-up' : 'badge-down'}>HTTP {t.status}</span>
                  </div>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, color: t.success ? '#34d399' : '#fb7185' }}>
                    {t.success ? 'Seat Reserved' : 'Sold Out / Rejected'}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '6px' }}>
                    Latency: {t.timeMs}ms &bull; {t.token ? `Token: ${t.token.slice(0, 10)}...` : 'Zero Over-allocation'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* =========================================================================
          TAB 3: CHALLENGE 2: IDEMPOTENCY LAB (BR3)
         ========================================================================= */}
      {activeTab === 'idempotency' && (
        <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={20} color="#6366f1" /> Idempotency Inspector
            </h2>
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Verifies <strong>Business Rule 3</strong>: Two-Phase cryptographic SHA-256 fingerprinting prevents double-charges.
            </p>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Idempotency-Key</label>
              <input 
                type="text" 
                value={idempotencyKey} 
                onChange={e => setIdempotencyKey(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#38bdf8', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}
              />
            </div>

            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '4px' }}>Charge Amount (INR)</label>
              <input 
                type="number" 
                value={idempotencyAmount} 
                onChange={e => setIdempotencyAmount(Number(e.target.value))}
                style={{ width: '100%', padding: '8px 12px', background: 'rgba(0,0,0,0.3)', border: '1px solid var(--border-subtle)', borderRadius: '6px', color: '#fff', fontSize: '0.85rem' }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <button 
                onClick={() => executeIdempotencyCharge(false)} 
                disabled={idempotencyLoading} 
                className="btn-primary" 
                style={{ width: '100%', justifyContent: 'center' }}
                id="execute-charge-btn"
              >
                Execute / Replay Charge
              </button>

              <button 
                onClick={() => executeIdempotencyCharge(true)} 
                disabled={idempotencyLoading} 
                className="btn-danger" 
                style={{ width: '100%', justifyContent: 'center' }}
                id="tamper-charge-btn"
              >
                Replay with Altered Amount (+₹1,000)
              </button>

              <button 
                onClick={() => setIdempotencyKey(`key-${Math.floor(Date.now() / 1000)}`)} 
                className="btn-secondary" 
                style={{ width: '100%', justifyContent: 'center' }}
              >
                Generate Fresh Key
              </button>
            </div>
          </div>

          {/* Idempotency Log Stream */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '14px' }}>Transaction Replay & Validation Log</h3>
            {idempotencyResults.length === 0 ? (
              <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>No payments executed yet. Click buttons to test.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {idempotencyResults.map((r, i) => (
                  <div key={i} style={{ background: 'rgba(0,0,0,0.35)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className={r.status === 201 ? 'badge-up' : 'badge-down'}>HTTP {r.status}</span>
                        {r.replayed && <span className="badge-up" style={{ color: '#818cf8', borderColor: '#818cf8' }}>X-Idempotent-Replay: true</span>}
                        {r.status === 422 && <span className="badge-down">PAYLOAD MISMATCH REJECTED</span>}
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>{r.timestamp}</span>
                    </div>
                    <div style={{ fontSize: '0.82rem', marginBottom: '4px' }}>
                      <strong>Key:</strong> <code>{r.key}</code> &bull; <strong>Amount:</strong> ₹{r.amount}
                    </div>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                      <strong>SHA-256 Fingerprint:</strong> <code>{r.fingerprint}</code>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 4: CHALLENGE 3C: SAGA ORCHESTRATOR VISUALIZER (BR4)
         ========================================================================= */}
      {activeTab === 'saga' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Cpu size={22} color="#6366f1" /> Distributed Saga Orchestrator & Compensating Rollback (BR4)
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Multi-service state machine coordinating PostgreSQL (<code style={{ color: '#38bdf8' }}>inventory_db</code>, <code style={{ color: '#38bdf8' }}>ticketing_db</code>, <code style={{ color: '#38bdf8' }}>booking_db</code>) and MongoDB (<code style={{ color: '#38bdf8' }}>payment_db</code>) across network partitions.
          </p>

          {/* State Machine Diagram Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '14px', marginBottom: '32px' }}>
            {[
              { step: '1. PENDING', name: 'Saga Initiated', desc: 'Create saga trace record' },
              { step: '2. RESERVED', name: 'Inventory Hold', desc: 'Atomic seat decrement in inventory_db' },
              { step: '3. PAID', name: 'Payment Charge', desc: 'SHA-256 fingerprint charge in payment_db' },
              { step: '4. TICKETED', name: 'PNR Issuance', desc: 'Allocate berths in ticketing_db' },
              { step: '5. CONFIRMED', name: 'AMQP Publish', desc: 'Publish event to seatlock.events' }
            ].map((s, idx) => (
              <div key={idx} style={{ background: 'rgba(0,0,0,0.3)', padding: '16px', borderRadius: '10px', border: '1px solid var(--border-subtle)', position: 'relative' }}>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-dim)', fontWeight: 700 }}>{s.step}</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 700, margin: '4px 0' }}>{s.name}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{s.desc}</div>
              </div>
            ))}
          </div>

          <div style={{ background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(244, 63, 94, 0.3)', borderRadius: '10px', padding: '18px', marginTop: '16px' }}>
            <h4 style={{ color: '#fb7185', fontSize: '0.95rem', fontWeight: 700, marginBottom: '6px' }}>
              Automated Compensating Rollback Invariant:
            </h4>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
              If Payment fails or cards decline, the Orchestrator instantly dispatches <code style={{ color: '#fb7185' }}>POST /api/v1/inventory/release</code>.
              Held seats are automatically restored to the quota pool, and the booking transitions to <code style={{ color: '#fb7185' }}>FAILED_COMPENSATED</code> with zero inventory leakage.
            </p>
          </div>
        </div>
      )}

      {/* =========================================================================
          TAB 5: CHALLENGE 3D: AMQP EVENT BROKER FEED
         ========================================================================= */}
      {activeTab === 'notifications' && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Bell size={20} color="#06b6d4" /> RabbitMQ Topic Exchange Live Stream
              </h2>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                Queue: <code style={{ color: '#22d3ee' }}>booking.notifications</code> bound to exchange <code style={{ color: '#22d3ee' }}>seatlock.events</code>
              </p>
            </div>
            <button className="btn-secondary" onClick={fetchNotifications}>
              <RefreshCw size={14} /> Refresh Logs
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {notifications.length === 0 ? (
              <p style={{ color: 'var(--text-dim)', fontSize: '0.85rem' }}>No notification events received yet. Complete a booking to trigger AMQP events.</p>
            ) : (
              notifications.map((n, i) => (
                <div key={i} style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                      <span className="badge-up" style={{ color: '#38bdf8', borderColor: '#38bdf8' }}>SMS DISPATCHED</span>
                      <strong style={{ fontSize: '0.85rem' }}>Recipient: {n.recipient}</strong>
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-main)', marginTop: '4px' }}>
                      {n.message}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right', fontSize: '0.72rem', color: 'var(--text-dim)' }}>
                    <div>Ref: {n.booking_id}</div>
                    <div>{new Date(n.created_at).toLocaleTimeString()}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

    </div>
  );
}
