# Master Project Plan, Architecture & Execution Blueprint
## Course: Scalable Services (SEZG583) | Assignment 1 (13 Marks)
### Application Name: **SeatLock — Unified High-Concurrency Reservation Platform (Railway Tatkal, Concert Flash-Sales, Intercity Transit)**

---

## 1. Application Overview & Objective

### 1.1 The Domain & Problem Statement
High-demand reservation systems (such as **IRCTC 10:00 AM Tatkal train booking**, **Coldplay stadium flash-sales**, and **holiday Volvo bus routes**) represent the canonical real-world concurrency and reliability challenges in distributed systems:
- Millions of users and bots hit the system at the exact opening second competing for a strictly limited inventory quota (e.g. exactly 5 Tatkal sleeper berths or 5 VIP stadium passes).
- A naive "check-then-update" approach leads to database race conditions, catastrophic over-allocation, and negative inventory.
- Network retries and mobile connection drops cause duplicate payment debits and ghost bookings unless requests are protected by cryptographically verifiable idempotency.
- The business transaction spans multiple autonomous bounded contexts:
  1. Seat / Berth Inventory Management
  2. Booking Saga Orchestration
  3. Payment Gateway & Transaction Ledger
  4. Digital Ticketing, PNR Generation & Seat Assignment
  5. Multi-channel Notification Dispatch
- A failure in payment or ticket generation requires an **Orchestrated Saga with Compensating Rollbacks** to immediately restore the held seats without leaving orphaned reservations or corrupted balances.
- Downstream notification channels (SMS gateways, email servers) experience variable latencies and outages, requiring an asynchronous, durable message broker (**RabbitMQ**) capable of **offline queue catch-up** and **idempotent message handling**.

### 1.2 Academic Objectives
1. Decompose the multi-modal ticketing domain into **5 autonomous microservices** adhering strictly to the **Database-per-Service** pattern with independent databases and credentials.
2. Standardize RESTful HTTP APIs with versioning (`/api/v1/...`), consistent JSON error envelopes, and OpenAPI 3.0 documentation.
3. Solve **Challenge 1 (Mandatory: Concurrency Control)** on contended Tatkal / VIP inventory using database-level atomic conditional updates.
4. Solve **Challenge 2 (Mandatory: Idempotency)** on payment transactions using `Idempotency-Key` headers and SHA-256 canonical payload fingerprinting.
5. Solve **Challenge 3 (Option 3D: Event-Driven Broker + Option 3C: Saga Compensation)** using **RabbitMQ** for durable decoupled messaging (offline consumer catch-up) and an Orchestrated Saga with compensating rollbacks.
6. Provide an enterprise-grade polyglot implementation (Python FastAPI + Node.js Express + PostgreSQL + MongoDB + Redis + RabbitMQ + Next.js Frontend) deployable with a single `docker compose up --build` command, perfectly preparing for **Assignment 2 (Kubernetes/Minikube)**.

---

## 2. Fulfillment of the 5 Mandatory Conditions

| # | Mandatory Condition (Assignment Spec) | How "SeatLock" Fulfills It |
| :-: | :--- | :--- |
| **a** | **$\ge 4$ services with distinct business responsibilities** | **5 Decoupled Microservices**:<br>1. `inventory-service` (Seats, Berths, Quotas)<br>2. `booking-service` (Saga Orchestration, Order Lifecycle)<br>3. `payment-service` (Mock Gateway, Idempotency Ledger)<br>4. `ticketing-service` (PNR Generation, Seat Allocation, Barcodes)<br>5. `notification-service` (RabbitMQ Consumer, Delivery Audit)<br>*(Plus API Gateway & Next.js Frontend Cockpit)* |
| **b** | **Transaction spanning $\ge 3$ services** | **Multi-Modal Checkout Saga**: Client $\rightarrow$ Booking Service $\rightarrow$ Inventory Service (atomic hold) $\rightarrow$ Payment Service (idempotent charge) $\rightarrow$ Ticketing Service (PNR & Berth issue) $\rightarrow$ RabbitMQ Broker $\rightarrow$ Notification Service (dispatch SMS/Email). |
| **c** | **Contended resource that can be over-allocated** | **Tatkal Quota / VIP Seat Inventory**: Capacity $N = 5$ seats (e.g. 5 AC-3 Tier Tatkal Berths on Train #12951 or 5 VIP Stadium Seats). 20 parallel requests fired at the exact same millisecond will compete for these 5 seats. Exactly 5 must succeed; 15 must receive HTTP 409 Conflict. |
| **d** | **Operation unsafe to repeat** | **Payment Charge & Ticket Issuance**: Must never double-charge cards or double-issue PNR passes when users hit retry or network packets duplicate. Protected by `Idempotency-Key`. |
| **e** | **Dependency that can be slow or fail** | **Mock Payment Gateway & Banking Network**: Built-in configurable latency (`PAYMENT_DELAY_MS`) and chaos failure modes (`PAYMENT_CHAOS_MODE=true` or test cards) to simulate 504 timeouts and 402 card failures, triggering saga rollbacks. |

---

## 3. Polyglot Microservices Breakdown & Tech Stacks

```
                                  +------------------------------------+
                                  |     Next.js 14 Frontend (:3000)    |
                                  |  - Live Tatkal / Concert Cockpit   |
                                  +-----------------+------------------+
                                                    |
                                                    | HTTP REST (Port 8000)
                                                    v
                                  +------------------------------------+
                                  |    API Gateway (Node.js/Express)   |
                                  |  - X-Correlation-ID Injection      |
                                  |  - Redis Rate Limiter              |
                                  +----+------------+-------------+----+
                                       |            |             |
                 +---------------------+            |             +---------------------+
                 |                                  |                                   |
                 v                                  v                                   v
  +-------------------------------+  +-------------------------------+  +-------------------------------+
  | 1. Booking Service (:8001)    |  | 2. Inventory Service (:8002)  |  | 3. Payment Service (:8003)    |
  |    - Python 3.12 / FastAPI    |  |    - Python 3.12 / FastAPI    |  |    - Node.js 22 / Express     |
  |    - DB: PostgreSQL (booking) |  |    - DB: PostgreSQL (inventory|  |    - DB: MongoDB (payment_db) |
  |    - Role: Saga Orchestrator  |  |    - Role: Atomic Row Locks   |  |    - Role: Idempotency Ledger |
  +---------------+---------------+  +---------------+---------------+  +---------------+---------------+
                  |                                  ^                                  |
                  | Inter-service HTTP (Hold / Release)                                 |
                  +----------------------------------+                                  |
                  |                                                                     |
                  | HTTP (Issue PNR)                                                    | AMQP Event:
                  v                                                                     | "booking.confirmed"
  +-------------------------------+                                                     v
  | 4. Ticketing Service (:8005)  |                                     +-------------------------------+
  |    - Python 3.12 / FastAPI    |                                     |    RabbitMQ Broker (:5672)    |
  |    - DB: PostgreSQL (tickets) |                                     |    Exchange: seatlock.events  |
  |    - Role: PNR & Seat Assign  |                                     +---------------+---------------+
  +-------------------------------+                                                     |
                                                                                        | AMQP Consume
                                                                                        v
                                                                        +-------------------------------+
                                                                        | 5. Notification Service(:8004)|
                                                                        |    - Node.js 22 / Express     |
                                                                        |    - DB: MongoDB (notif_db)   |
                                                                        |    - Role: AMQP Catch-Up      |
                                                                        +-------------------------------+
```

### 3.1 Service Details & Rationale

#### 1. Inventory Service
- **Directory**: `services/inventory/` (Port `8002`)
- **Runtime**: Python 3.12 + FastAPI + SQLAlchemy Async + asyncpg
- **Database**: PostgreSQL (`inventory_db`, User: `inventory_user`, Password: `inventory_pass`)
- **Data Owned**: `trips_events` (Train routes, Concerts, Bus runs), `quotas` (Tatkal, General, VIP), `seat_inventories`.
- **Role**: High-speed concurrency engine. Enforces atomic conditional updates:
  ```sql
  UPDATE seat_inventories 
  SET available = available - :qty, version = version + 1 
  WHERE quota_id = :quota_id AND available >= :qty;
  ```

#### 2. Booking Service (Saga Orchestrator)
- **Directory**: `services/booking/` (Port `8001`)
- **Runtime**: Python 3.12 + FastAPI + httpx + pydantic
- **Database**: PostgreSQL (`booking_db`, User: `booking_user`, Password: `booking_pass`)
- **Data Owned**: `bookings`, `booking_passengers`, `saga_steps`.
- **Role**: Coordinates the distributed checkout transaction. Executes:
  `PENDING` $\rightarrow$ `RESERVED` $\rightarrow$ `PAID` $\rightarrow$ `TICKETED` $\rightarrow$ `CONFIRMED`.
  If payment or ticketing fails, initiates compensating rollback (`POST /api/v1/inventory/release`) and marks booking `FAILED_COMPENSATED`.

#### 3. Payment Service
- **Directory**: `services/payment/` (Port `8003`)
- **Runtime**: Node.js 22 + Express + Mongoose
- **Database**: MongoDB (`payment_db`, User: `payment_user`, Password: `payment_pass`)
- **Data Owned**: `payments`, `idempotency_records`.
- **Role**: Mock payment gateway with cryptographic SHA-256 fingerprinting for strict idempotency. Configurable latency and failure toggles for chaos testing.

#### 4. Ticketing Fulfillment Service
- **Directory**: `services/ticketing/` (Port `8005`)
- **Runtime**: Python 3.12 + FastAPI + SQLAlchemy Async + asyncpg
- **Database**: PostgreSQL (`ticketing_db`, User: `ticketing_user`, Password: `ticketing_pass`)
- **Data Owned**: `issued_tickets`, `pnr_records`, `allocated_berths`.
- **Role**: Distinct business capability: Generates unique digital PNRs (e.g., `PNR-TATKAL-2026-98124`), assigns specific berths (Lower / Middle / Upper / Window), and generates barcode tokens. Enforces unique berth allocation constraints.

#### 5. Notification Service
- **Directory**: `services/notification/` (Port `8004`)
- **Runtime**: Node.js 22 + Express + amqplib
- **Database**: MongoDB (`notification_db`, User: `notif_user`, Password: `notif_pass`)
- **Data Owned**: `notification_logs`, `processed_event_ids`.
- **Role**: Asynchronous event consumer. Listens on RabbitMQ queue `booking.notifications`. Implements consumer-side idempotency and offline catch-up.

#### 6. API Gateway & Redis
- **Directory**: `gateway/` (Port `8000`)
- **Runtime**: Node.js + Express + http-proxy-middleware + ioredis
- **Role**: Centralized ingress, distributed `X-Correlation-ID` generation/forwarding, and Redis token-bucket rate limiting.

#### 7. Next.js Frontend Dashboard (Interactive Cockpit)
- **Directory**: `frontend/` (Port `3000`)
- **Runtime**: Next.js 14 / React + Glassmorphism Styling
- **Role**: Live visual demonstration for the 8–10 minute evaluation video:
  - Multi-mode switcher: 🚆 **Railway Tatkal Express** / 🎸 **Concert Flash-Sale** / 🚌 **Intercity Bus**.
  - One-click "Fire 20 Concurrent Bookings" stress visualizer.
  - Idempotency replay inspector.
  - RabbitMQ "Kill & Revive Consumer" catch-up demo.
  - Live Saga execution state progression.

---

## 4. Traceable Business Rules (`BR1` to `BR4`)

| Rule ID | Name | Formal Specification | Traceable Code Location | Automated Unit Test |
| :---: | :--- | :--- | :--- | :--- |
| **BR1** | Zero Over-allocation | An event/train quota allocation must never exceed total capacity. If available seats $< \text{requested}$, request must be rejected with HTTP 409 Conflict. | `services/inventory/src/services/allocation.py` | `services/inventory/tests/test_br1_inventory_bound.py` |
| **BR2** | Atomic Conditional Update | Seat decrement must be executed in a single atomic SQL statement at the DB engine level (`WHERE available >= :qty`). Plain in-memory check-then-set is strictly forbidden. | `services/inventory/src/repository/seat_repo.py` | `services/inventory/tests/test_br2_atomic_concurrency.py` |
| **BR3** | Two-Phase Idempotency with Fingerprinting | Requests with matching `Idempotency-Key` and matching SHA-256 fingerprint must replay the previous response. If the payload differs, reject with HTTP 422 Unprocessable Entity. | `services/payment/src/middleware/idempotency.js` | `services/payment/tests/test_br3_idempotency.test.js` |
| **BR4** | Saga Compensating Rollback | If payment processing or ticket issuance fails, the orchestrator MUST call `POST /api/v1/inventory/release`, restore seats, and mark booking as `FAILED_COMPENSATED`. | `services/booking/src/saga/coordinator.py` | `services/booking/tests/test_br4_saga_compensation.py` |

---

## 5. Engineering Challenges & Evidence Strategy

### 5.1 Challenge 1: Concurrency Control (Mandatory)
* **Contended Resource**: 5 AC-3 Tier Tatkal seats on Train #12951.
* **Test Script**: `scripts/challenge1_concurrency.py`
* **Execution**: Fires 20 simultaneous asynchronous HTTP requests using `asyncio` at the exact same millisecond.
* **Expected Outcome**: Exactly 5 requests return `HTTP 201 Created`; exactly 15 requests return `HTTP 409 Conflict`. Final database inventory is exactly 0. Zero negative inventory.
* **Evidence Saved to**: `evidence/challenge-1-concurrency/`.

### 5.2 Challenge 2: Idempotency (Mandatory)
* **Unsafe Operation**: `POST /api/v1/payments/charge`
* **Test Script**: `scripts/challenge2_idempotency.py`
* **Execution**: Demonstrates sequential replay (`X-Idempotent-Replay: true`), payload alteration conflict (HTTP 422), and concurrent simultaneous arrivals with zero duplicate charges.
* **Evidence Saved to**: `evidence/challenge-2-idempotency/`.

### 5.3 Challenge 3: Choice 3D (RabbitMQ Broker) + 3C (Saga Rollback)
* **Flow**:
  1. *Saga Compensation (3C)*: Force payment failure; show automatic release of held Tatkal berths.
  2. *RabbitMQ Offline Catch-Up (3D)*: Stop `notification-service`, place 3 bookings (messages queue safely in RabbitMQ), restart `notification-service`, and verify all 3 notifications are processed without loss.
* **Test Script**: `scripts/challenge3_event_driven.py`
* **Evidence Saved to**: `evidence/challenge-3-event-driven/`.

---

## 6. Division of Responsibilities (3 Team Members)

- **Member 1 (Lead)**: System Architecture, Booking Service (Saga Coordinator), API Gateway, End-to-End Flow.
- **Member 2**: Inventory Service (Contended Resource, Concurrency Control, Atomic SQL updates), Ticketing Fulfillment Service (PNR & Berth allocation), Challenge 1 Scripts.
- **Member 3**: Payment Service (Idempotency Engine, Mock Gateway), Notification Service (RabbitMQ Consumer), Challenge 2 & Challenge 3D Scripts.

---

## 7. Granular Phase-Wise Implementation Roadmap & Final Status

- **Phase 1: Infrastructure & Data Setup (Pure Docker Compose)** — `[100% COMPLETED]`
  - Single `docker-compose.yml` orchestrating:
    - PostgreSQL (with initialization script creating `inventory_db`, `booking_db`, `ticketing_db`).
    - MongoDB (housing `payment_db`, `notification_db`).
    - Redis (rate limiting & locks).
    - RabbitMQ (event broker with management UI).
    - API Gateway (Node.js/Express with Redis rate limiting).
- **Phase 2: Microservices Implementation & Business Rules** — `[100% COMPLETED]`
  - Implemented `inventory-service` (`BR1`, `BR2` atomic conditional decrement, 4/4 pytest passed).
  - Implemented `payment-service` (`BR3`, two-phase cryptographic idempotency with SHA-256 fingerprinting, 5/5 jest passed).
  - Implemented `ticketing-service` (PNR & Berth allocation, digital security barcode, 3/3 pytest passed).
  - Implemented `notification-service` (RabbitMQ topic consumer, consumer deduplication store, 100% delivered).
  - Implemented `booking-service` (`BR4`, Distributed Saga Orchestrator, automated compensating rollback, 4/4 pytest passed).
- **Phase 3: Next.js Frontend Dashboard (Interactive Cockpit)** — `[100% COMPLETED]`
  - Live seat map for Tatkal / Concerts / Bus, 20-thread concurrency button, idempotency tester, broker catch-up demo, and live telemetry bar running on `:3000`.
- **Phase 4: Automated Challenge Scripts & Evidence Harvesting** — `[100% COMPLETED]`
  - Executed `challenge1_concurrency.py`, `challenge2_idempotency.py`, `challenge3_event_driven.py`, and `challenge3_saga_e2e.py`.
  - Populated all evidence directories under `/evidence`.
- **Phase 5: Submission Deliverables & Unified Evaluation Suite** — `[100% COMPLETED]`
  - Master Academic Design Report: [`submission/DESIGN_AND_TECHNICAL_REPORT.md`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/DESIGN_AND_TECHNICAL_REPORT.md)
  - 8-to-10 Minute Presentation Script: [`submission/DEMO_VIDEO_SCRIPT.md`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/DEMO_VIDEO_SCRIPT.md)
  - Rubric Compliance Matrix: [`submission/SUBMISSION_CHECKLIST.md`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/SUBMISSION_CHECKLIST.md)
  - AI Usage & Contribution Statement: [`submission/AI_DECLARATION_AND_CONTRIBUTIONS.md`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/AI_DECLARATION_AND_CONTRIBUTIONS.md)
  - Master Evaluation Runner: [`scripts/run_all_evaluations.py`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/run_all_evaluations.py) (All 5 steps passing in 38s)
  - Unit Test Runner: [`scripts/run_all_unit_tests.py`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/run_all_unit_tests.py) (All 4 microservice suites passing in 13.7s)

