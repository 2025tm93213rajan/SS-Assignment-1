# "SeatLock" Microservices Architecture & System Design
## Scalable Services (SEZG583) - Assignment 1 Documentation

---

## 1. System Component Diagram (5 Autonomous Microservices)

The following Mermaid diagram visualizes the 5-microservice architecture, API Gateway, polyglot databases, and RabbitMQ broker:

```mermaid
graph TD
    Client["Client / Next.js Dashboard<br/>(:3000)<br/>• Tatkal Train / Concert / Bus"]
    Gateway["API Gateway (:8000)<br/>• Express / Node.js<br/>• Correlation ID Injection<br/>• Redis Rate Limiter"]
    Redis[("Redis (:6379)<br/>• Rate Limit Token Bucket<br/>• Distributed Cache")]

    subgraph Service Mesh
        BookingSvc["1. Booking Service (:8001)<br/>• Python / FastAPI<br/>• Saga Orchestrator"]
        InventorySvc["2. Inventory Service (:8002)<br/>• Python / FastAPI<br/>• Tatkal / Quota Concurrency Engine"]
        PaymentSvc["3. Payment Service (:8003)<br/>• Node.js / Express<br/>• SHA-256 Idempotency Engine"]
        TicketSvc["4. Ticketing Service (:8005)<br/>• Python / FastAPI<br/>• PNR & Berth Allocation"]
        NotifSvc["5. Notification Service (:8004)<br/>• Node.js / Express<br/>• AMQP Offline Catch-up Consumer"]
    end

    subgraph Polyglot Databases
        Postgres1[("PostgreSQL: inventory_db<br/>• User: inventory_user")]
        Postgres2[("PostgreSQL: booking_db<br/>• User: booking_user")]
        Postgres3[("PostgreSQL: ticketing_db<br/>• User: ticketing_user")]
        Mongo1[("MongoDB: payment_db<br/>• Collection: payments, idempotency")]
        Mongo2[("MongoDB: notification_db<br/>• Collection: notification_logs")]
    end

    Broker{{"RabbitMQ Message Broker (:5672)<br/>• Exchange: seatlock.events<br/>• Queue: booking.notifications"}}

    %% Ingress
    Client -->|"HTTP / REST"| Gateway
    Gateway <-->|"Token Check"| Redis

    %% Gateway Routing
    Gateway -->|"REST /api/v1/bookings"| BookingSvc
    Gateway -->|"REST /api/v1/inventory"| InventorySvc
    Gateway -->|"REST /api/v1/payments"| PaymentSvc
    Gateway -->|"REST /api/v1/tickets"| TicketSvc
    Gateway -->|"REST /api/v1/notifications"| NotifSvc

    %% Service to DB Isolation
    InventorySvc <-->|"SQL (Atomic Locks)"| Postgres1
    BookingSvc <-->|"SQL (Saga State)"| Postgres2
    TicketSvc <-->|"SQL (PNR & Berth)"| Postgres3
    PaymentSvc <-->|"Mongoose / BSON"| Mongo1
    NotifSvc <-->|"Mongoose / BSON"| Mongo2

    %% Inter-service Orchestrated Saga
    BookingSvc -->|"1. REST /reserve"| InventorySvc
    BookingSvc -->|"2. REST /charge"| PaymentSvc
    BookingSvc -->|"3. REST /issue-pnr"| TicketSvc
    BookingSvc -.->|"Compensating /release"| InventorySvc

    %% Event Broker
    BookingSvc -->|"Publish: booking.confirmed"| Broker
    Broker -->|"AMQP Consume"| NotifSvc
```

---

## 2. Sequence Diagram: Happy Path Multi-Service Saga

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / Next.js Cockpit
    participant GW as API Gateway (:8000)
    participant B as Booking Service (:8001)
    participant I as Inventory Service (:8002)
    participant P as Payment Service (:8003)
    participant T as Ticketing Service (:8005)
    participant Q as RabbitMQ (:5672)
    participant N as Notification Service (:8004)

    User->>GW: POST /api/v1/bookings (Train: #12951 Tatkal, Seats: 2, Idempotency-Key: K-1)
    GW->>GW: Inject X-Correlation-ID: corr-8921-a4
    GW->>B: Forward POST with Correlation ID
    B->>B: Persist Booking state = PENDING in booking_db
    
    %% Step 1: Hold Seats
    B->>I: POST /api/v1/inventory/reserve (quota_id: "TATKAL-12951-B1", qty: 2)
    I->>I: Atomic SQL UPDATE seat_inventories SET available = available - 2 WHERE available >= 2
    I-->>B: 200 OK (Reservation Token, Seats Held)
    B->>B: Update Booking state = RESERVED
    
    %% Step 2: Payment
    B->>P: POST /api/v1/payments/charge (booking_id, amount, Idempotency-Key: K-1)
    P->>P: Check MongoDB idempotency store (Key=K-1, Fingerprint=SHA256)
    P->>P: Process mock payment & save record to payment_db
    P-->>B: 200 OK (payment_id, status: SUCCESS)
    B->>B: Update Booking state = PAID
    
    %% Step 3: Ticket & PNR Issuance
    B->>T: POST /api/v1/tickets/issue (booking_id, passengers, coach: "B1")
    T->>T: Allocate specific berths (B1-21 Lower, B1-22 Middle) & generate PNR
    T-->>B: 201 Created (PNR: "PNR-TATKAL-2026-98124", berths: [21, 22])
    B->>B: Update Booking state = CONFIRMED
    
    %% Step 4: Event Emission
    B->>Q: Publish "booking.confirmed" event to exchange "seatlock.events"
    B-->>GW: 201 Created (Booking details, PNR, berths, status: CONFIRMED)
    GW-->>User: 201 Created
    
    %% Step 5: Asynchronous Consumer
    Q->>N: Consume "booking.confirmed"
    N->>N: Store audit record in notification_db
    N->>N: Send mock SMS (IRCTC PNR update) & Email Pass
```

---

## 3. Sequence Diagram: Failure Path & Compensating Rollback (Saga)

```mermaid
sequenceDiagram
    autonumber
    actor User as Client / Next.js Cockpit
    participant GW as API Gateway (:8000)
    participant B as Booking Service (:8001)
    participant I as Inventory Service (:8002)
    participant P as Payment Service (:8003)

    User->>GW: POST /api/v1/bookings (Seats: 2, Card: Declining/Expired)
    GW->>B: Forward POST with X-Correlation-ID
    B->>B: Persist Booking state = PENDING
    
    %% Step 1: Hold Succeeds
    B->>I: POST /api/v1/inventory/reserve (quota_id: "TATKAL-12951-B1", qty: 2)
    I->>I: Atomic decrement (available: 5 -> 3)
    I-->>B: 200 OK (Hold granted)
    B->>B: Update Booking state = RESERVED
    
    %% Step 2: Payment Fails
    B->>P: POST /api/v1/payments/charge
    P-->>B: 402 Payment Required (Card Declined) / 504 Timeout
    B->>B: Catch error, initiate Saga Compensation!
    
    %% Step 3: Compensating Action
    B->>I: POST /api/v1/inventory/release (quota_id: "TATKAL-12951-B1", qty: 2)
    I->>I: Atomic restore (available: 3 -> 5 restored)
    I-->>B: 200 OK (Seats released back to quota)
    
    B->>B: Update Booking state = FAILED_COMPENSATED
    B-->>GW: 422 Unprocessable Entity (Payment failed, Tatkal seats released)
    GW-->>User: 422 Unprocessable Entity
```

---

## 4. Uniform Error Response Schema

```json
{
  "status": "error",
  "code": "INSUFFICIENT_INVENTORY",
  "message": "Only 3 seats remaining in Tatkal quota; requested 5 seats.",
  "correlation_id": "corr-8921-a4",
  "service": "inventory-service",
  "timestamp": "2026-10-18T11:35:00Z",
  "details": {
    "quota_id": "TATKAL-12951-B1",
    "requested": 5,
    "available": 3
  }
}
```
