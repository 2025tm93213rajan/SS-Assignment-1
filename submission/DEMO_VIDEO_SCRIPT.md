# SeatLock: Distributed High-Concurrency Flash-Sale & Tatkal Reservation Platform
## Demonstration Video Script & Production Guide
### Scalable Services (SEZG583) — Assignment 1 (13 Marks)

**Course**: Scalable Services (SEZG583) | M.Tech in Software Systems, BITS Pilani  
**Target Video Duration**: 8 to 10 minutes  
**Format**: High-Definition (1080p, 60fps), split-screen (Presenter Camera + Terminal/Browser)  
**Team Roster**:
- **Member 1 (Speaker 1)**: System Architecture, Decomposition & API Gateway
- **Member 2 (Speaker 2)**: Next.js 14 Frontend Cockpit, Multi-Domain User Journey & Saga Workflow
- **Member 3 (Speaker 3)**: Terminal Verification of Core Challenges (Concurrency, Idempotency, AMQP, Saga Rollback) & Wrap-Up

---

## Video Timeline & Stage Map

```
00:00 ─── Member 1: Executive Overview & Problem Context (1:00)
01:00 ─── Member 1: Microservice Decomposition & Polyglot Persistence (2:00)
03:00 ─── Member 2: Live Frontend Cockpit & Multi-Domain Booking Flow (3:00)
06:00 ─── Member 3: Terminal Benchmark — Challenge 1 (Concurrency & Overbooking) (1:00)
07:00 ─── Member 3: Terminal Benchmark — Challenge 2 (Idempotency & Concurrent Race) (1:00)
08:00 ─── Member 3: Terminal Benchmark — Challenge 3D (RabbitMQ Catch-Up) & 3C (Saga Rollback) (1:00)
09:00 ─── Member 1 & Team: Limitations, Reflections & Assignment 2 Roadmap (1:00)
10:00 ─── End of Video
```

---

## Detailed Scene-by-Scene Script

### Scene 1: Introduction & Domain Context (00:00 – 01:00)
**Speaker**: Member 1 (Lead Presenter)  
**Visual**: Full camera on Member 1, transitioning to the title slide showing Course, Team ID, and Project Name: *SeatLock*.

> **Member 1 (Speech)**:  
> *"Hello respected evaluators and professors. Welcome to our presentation and live demonstration of **SeatLock**, our distributed, high-concurrency reservation platform engineered for Scalable Services (SEZG583) Assignment 1.  
> 
> My name is [Member 1 Name], joined by my teammates [Member 2 Name] and [Member 3 Name].  
> 
> High-velocity booking systems—specifically **IRCTC 10:00 AM Railway Tatkal**, **stadium concert flash-sales**, and **intercity sleeper buses**—operate under severe burst contention. When bookings open, thousands of users compete for a tiny handful of seats within milliseconds. Traditional monolithic architectures collapse under these conditions due to overbooking anomalies, double charges on network timeouts, and ghost locks when partial failures occur.  
> 
> To conquer these challenges, we engineered SeatLock: a fully autonomous, polyglot microservices platform built from the ground up to guarantee strict inventory conservation, two-phase cryptographic idempotency, distributed saga orchestration, and decoupled asynchronous event delivery."*

---

### Scene 2: Architectural Decomposition & Polyglot Persistence (01:00 – 03:00)
**Speaker**: Member 1  
**Visual**: Screen share displaying the Mermaid Architecture Diagram and running Docker containers (`docker compose ps`).

> **Member 1 (Speech)**:  
> *"Let us examine the architecture. SeatLock is strictly decomposed into **5 independent microservices**, an **API Gateway**, and a **Next.js 14 frontend**, backed by **4 polyglot data stores**.  
> 
> As you can see in our architecture diagram:
> 1. At the perimeter is our **API Gateway** on port 8000, built with Node.js and Express. It enforces Redis token-bucket rate limiting at 200 requests per minute and injects a unique `X-Correlation-ID` across every downstream request for distributed observability.
> 2. The **Booking Service** on port 8001, built with Python FastAPI and PostgreSQL `booking_db`, acts as our Distributed Saga Orchestrator. It manages the multi-step transaction lifecycle through state transitions.
> 3. The **Inventory Service** on port 8002, with PostgreSQL `inventory_db`, enforces Business Rules 1 and 2—atomic inventory reservations with absolute zero overselling.
> 4. The **Payment Service** on port 8003, built with Node.js and MongoDB `payment_db`, enforces Business Rule 3—cryptographic SHA-256 idempotency and concurrent lock resolution.
> 5. The **Ticketing Service** on port 8005, with PostgreSQL `ticketing_db`, handles deterministic coach and seat allocation, generating official 10-digit PNRs and digital security hashes.
> 6. The **Notification Service** on port 8004, with MongoDB `notification_db`, consumes asynchronous booking events from a durable **RabbitMQ** topic exchange with consumer-side deduplication.
> 
> Crucially, we strictly observe the **Database-per-Service** pattern: zero shared database tables, zero cross-service foreign keys, and zero distributed database deadlocks.  
> 
> Looking at our terminal, a single command—`docker compose up -d`—launches all 11 production-grade containers including PostgreSQL, MongoDB, Redis, and RabbitMQ. All containers are currently healthy and operational.  
> 
> Now, I hand over to [Member 2] to walk you through our Next.js 14 Live Cockpit and full booking lifecycle."*

---

### Scene 3: Live Frontend Cockpit & Multi-Domain User Journey (03:00 – 06:00)
**Speaker**: Member 2  
**Visual**: Screen share showing browser navigating `http://localhost:3000` with dark mode glassmorphism UI, real-time health telemetry bar, domain switcher, interactive coach layout, checkout drawer, and live event feed.

> **Member 2 (Speech)**:  
> *"Thank you, [Member 1]. I am [Member 2], and I am excited to demonstrate the **SeatLock Live Cockpit**, our Next.js 14 dashboard running at port 3000.  
> 
> Notice first the **Telemetry & Observability Bar** at the top. It continuously polls our API Gateway and all microservices. Every service displays real-time health pills and microsecond round-trip latency.  
> 
> SeatLock natively supports three distinct high-demand reservation domains:
> - **IRCTC Railway Tatkal**: Air-Conditioned Coach B1 on Train 12952 (Mumbai Rajdhani Express).
> - **Concert Arena Flash-Sale**: Coldplay Music of the Spheres World Tour, VIP Lounge & Pit Passes.
> - **Intercity Express Bus**: Bangalore to Goa Volvo 9600 Multi-Axle sleeper berths.
> 
> Let's initiate an IRCTC Tatkal booking. As you can see, the coach layout dynamically renders Upper, Middle, and Lower berths. Let's select Seat 10 (Lower Berth) and Seat 11 (Middle Berth). Notice how the pricing drawer dynamically updates to ₹5,700 including GST and superfast tatkal surcharge.  
> 
> When I input our passenger names—'Dr. Rajesh Sharma' and 'Priya Sharma'—and click **'Proceed to Secure Checkout'**, observe what happens under the hood.  
> 
> In real time, the Booking Service coordinates an orchestrated Distributed Saga:
> 1. Step 1: It contacts the Inventory Service, atomically reserving the held seats with a temporary reservation token.
> 2. Step 2: It generates a client-side cryptographic `Idempotency-Key` and submits payment to the Payment Service.
> 3. Step 3: Upon payment success, it requests the Ticketing Service to issue our confirmed Indian Railways PNR: `PNR-TATKAL-827419` along with allocated berths LB-10 and MB-11.
> 4. Step 4: It publishes a `booking.confirmed` event to the RabbitMQ `seatlock.events` exchange.
> 
> Look at the **Live AMQP Event Stream** at the bottom of our dashboard. Within 4 milliseconds, our Notification Service consumed the message and dispatched simulated SMS and Email confirmations.  
> 
> Furthermore, our dashboard contains interactive labs for all three engineering challenges. To see rigorous algorithmic proof and edge-case stress tests, let us hand over to [Member 3] in the terminal."*

---

### Scene 4: Terminal Verification — Challenge 1 (Concurrency & Overbooking) (06:00 – 07:00)
**Speaker**: Member 3  
**Visual**: Full-screen split terminal. Top pane: live execution of `python scripts/challenge1_concurrency.py`. Bottom pane: `docker compose logs -f inventory-service`.

> **Member 3 (Speech)**:  
> *"Thank you, [Member 2]. I am [Member 3], and I will now prove our system's correctness and resilience under adversarial conditions directly in the terminal.  
> 
> We begin with **Challenge 1: Concurrency and Race Condition Elimination**.  
> The business rule `BR1` mandates that available inventory must never drop below zero, and `BR2` dictates that when $M$ concurrent threads contest $N$ seats ($M > N$), exactly $N$ succeed and $M-N$ are rejected with HTTP 409 Conflict.  
> 
> Let us run our automated benchmark: `python scripts/challenge1_concurrency.py`.  
> 
> Watch the terminal output:
> - The script resets the Tatkal quota to exactly 5 seats.
> - Using Python's `asyncio` and `httpx`, it launches **20 concurrent threads simultaneously** using `asyncio.gather()`. All 20 requests hit the Inventory Service at the exact same millisecond.
> - As expected: **Exactly 5 requests receive HTTP 201 Created**, successfully acquiring reservation tokens.
> - **The remaining 15 requests receive HTTP 409 Conflict** with error code `INSUFFICIENT_INVENTORY`.
> - A final query verifies the remaining balance is exactly 0. Zero seats overbooked, zero race conditions, 100% mathematical consistency."*

---

### Scene 5: Terminal Verification — Challenge 2 (Idempotency & Concurrent Race) (07:00 – 08:00)
**Speaker**: Member 3  
**Visual**: Terminal executing `python scripts/challenge2_idempotency.py`.

> **Member 3 (Speech)**:  
> *"Next is **Challenge 2: High-Fidelity Idempotency and Duplicate Charge Immunity** enforcing Business Rule `BR3`.  
> 
> In distributed payment processing, network drops often cause clients to retry, risking duplicate debits. We implemented a two-phase idempotency mechanism using canonical JSON body normalization and SHA-256 fingerprinting stored in MongoDB.  
> 
> Let us execute `python scripts/challenge2_idempotency.py`:
> 1. **Test 1 (Sequential Replay)**: We send a payment charge for ₹5,700 with key `demo-key-001`. The charge succeeds with HTTP 201. We immediately repeat the exact same request with the same key. The Payment Service detects the existing fingerprint, skips card charging, and returns the cached response with the HTTP header `X-Idempotent-Replay: true`. MongoDB verifies exactly 1 financial ledger record was created.
> 2. **Test 2 (Payload Tampering Mismatch)**: We reuse `demo-key-001` but alter the payment amount from ₹5,700 to ₹10,000. Because the SHA-256 payload hash differs, the service rejects the request immediately with **HTTP 422 Unprocessable Entity** and error code `IDEMPOTENCY_PAYLOAD_MISMATCH`.
> 3. **Test 3 (Concurrent Simultaneous Race)**: What happens if 10 network retries arrive at the exact same millisecond? We fire 10 simultaneous threads with the same key. The MongoDB atomic lock holds 9 threads while the first completes. All 10 threads receive HTTP 201, returning the exact same charge ID, and the database contains **strictly 1 payment record**. Zero duplicate charges."*

---

### Scene 6: Terminal Verification — Challenge 3D & 3C (AMQP Catch-Up & Saga Rollback) (08:00 – 09:00)
**Speaker**: Member 3  
**Visual**: Split terminal showing `challenge3_event_driven.py` (Challenge 3D) and `challenge3_saga_e2e.py` (Challenge 3C).

> **Member 3 (Speech)**:  
> *"Now we demonstrate our selected **Challenge 3: Distributed Coordination & Resilience**. We implemented both Challenge 3D (Event-Driven Broker) and Challenge 3C (Compensating Saga Rollback).  
> 
> First, **Challenge 3D (AMQP Broker & Offline Queue Catch-Up)**:
> In `scripts/challenge3_event_driven.py`, we test consumer-side deduplication. Sending the same event twice results in the second message being acknowledged and safely discarded.  
> Next, we execute `docker compose stop notification-service` to simulate a complete notification infrastructure outage. While offline, we publish 3 booking events to RabbitMQ. RabbitMQ buffers these in a durable queue. We now restart the container: within 3 seconds, the worker reconnects, drains all 3 buffered messages, and persists them to MongoDB with **zero message loss**.  
> 
> Finally, **Challenge 3C (Distributed Saga Rollback - `BR4`)**:
> Let us run `python scripts/challenge3_saga_e2e.py`.  
> - In Scenario 1, the happy path succeeds, confirming the booking.
> - In Scenario 2, we simulate payment failure by using test card ending in `0002` (which returns HTTP 402 Payment Required).
> - Watch the terminal logs closely: The Booking Orchestrator catches the payment decline, immediately issues a compensating HTTP call `POST /api/v1/inventory/release`, and transitions the booking to `FAILED_COMPENSATED`.
> - The terminal prints the before and after inventory: Available seats remained exactly 3. **Zero seats leaked, zero ghost locks created**."*

---

### Scene 7: Evaluation Summary, Limitations & Assignment 2 Roadmap (09:00 – 10:00)
**Speaker**: Member 1 (with Member 2 and Member 3 on screen)  
**Visual**: Summary slide displaying assignment rubric checklist and Assignment 2 Minikube roadmap.

> **Member 1 (Speech)**:  
> *"To conclude our demonstration:
> SeatLock completely satisfies all 5 mandatory conditions and all four assignment challenges:
> - 5 independently deployable microservices plus API Gateway and Next.js frontend.
> - 4 polyglot data stores with strict Database-per-Service ownership.
> - High-concurrency row locking with zero overbooking under 20 parallel threads.
> - Two-phase cryptographic idempotency with concurrent collision protection.
> - Durable RabbitMQ event decoupling with offline catch-up.
> - Distributed Saga orchestrator with automated compensating rollbacks.
> 
> **Current Limitations & Lessons Learned**:
> In local Docker Compose, services share a local bridge network and single host CPU cores. Under extreme sustained loads beyond 5,000 requests per second, the single PostgreSQL instance becomes a write-lock bottleneck.
> 
> **Roadmap for Assignment 2**:
> In Assignment 2, we will migrate SeatLock to **Kubernetes on Minikube**:
> 1. Packaging all services as Helm charts with Horizontal Pod Autoscalers (HPA).
> 2. Introducing Redis-based distributed lease locks for inventory pre-allocation.
> 3. Deploying Prometheus and Grafana for automated SLO tracking and canary rollouts.
> 
> Complete source code, OpenAPI specs, and raw terminal evidence logs are committed in our repository under `/evidence` and `/submission`.  
> 
> Thank you for your time and guidance."*

---

## Production & Recording Checklist for Video Submissions

| Item | Requirement | Verification Status |
| :--- | :--- | :---: |
| **Duration** | 8:00 to 10:00 minutes total. | Verified (Script timed at ~9:15 min at 135 wpm). |
| **All Members Speak** | Member 1 (Architecture), Member 2 (UI/Saga), Member 3 (Challenges). | Confirmed in script allocation. |
| **Live Terminals** | Real execution of scripts against live Docker containers. | Scripts: `challenge1_concurrency.py`, `challenge2_idempotency.py`, `challenge3_event_driven.py`, `challenge3_saga_e2e.py`. |
| **Video Platform** | Hosted on YouTube (Unlisted) or Google Drive with institutional BITS sharing permissions. | Ready for URL insertion in submission form. |
