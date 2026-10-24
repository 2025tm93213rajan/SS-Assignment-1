# Project Session Changelog & Decision Records
## Scalable Services (SEZG583) - Assignment 1

---

### Session Entry: 2026-10-18 (Session 10: Phase 2B Payment Service & Challenge 2 Completed)

#### 1. Implementation Summary (Phase 2B & Challenge 2)
- **Payment Service Full Implementation (`services/payment`)**:
  - Connected Node.js/Express service to MongoDB (`payment_db`) via Mongoose.
  - Implemented **`BR3` (Two-Phase Cryptographic Idempotency with Fingerprinting)**:
    - Canonical JSON body normalization & SHA-256 fingerprinting.
    - Replay cache with `X-Idempotent-Replay: true` header on matching key.
    - Payload mismatch rejection (HTTP 422 Unprocessable Entity) on modified body with identical key.
    - Atomic concurrent lock with polling wait loop (`waitForCompletion`) resolving race condition when multiple requests arrive simultaneously.
  - Added simulated chaos latency (`delay_ms`) and failure modes (`force_failure` or test card `4000-0000-0000-0002` returning HTTP 402 Payment Required).
  - Added endpoints: `POST /charge`, `GET /:id`, `GET /booking/:id`, `POST /chaos`, `POST /reset`.
  - Exported OpenAPI specification to [docs/openapi/payment_service_openapi.json](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs/openapi/payment_service_openapi.json).
- **Unit Test Suite Passed**:
  - `services/payment/tests/test_br3_idempotency.test.js` (5 Jest unit tests passed in 1.1s).
- **Challenge 2 Benchmark Runner Verified**:
  - Executed `scripts/challenge2_idempotency.py`:
    - Test 1 (Sequential Replay): First call 201 Created, second call 201 Created with `X-Idempotent-Replay: true`, exactly 1 MongoDB record.
    - Test 2 (Payload Mismatch): Rejected with HTTP 422 (`IDEMPOTENCY_PAYLOAD_MISMATCH`).
    - Test 3 (Concurrent Simultaneous Race): 10 parallel requests fired at the exact same millisecond; all 10 received status 201 with identical payment ID, and MongoDB persisted exactly 1 payment record.
  - Preserved raw logs in [evidence/challenge-2-idempotency/idempotency_run.log](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-2-idempotency/idempotency_run.log).
  - Authored [evidence/challenge-2-idempotency/README.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-2-idempotency/README.md).

#### 2. Ready for Git Commit
Phase 2B & Challenge 2 are 100% complete and verified. Ready for the user to commit via the provided git instructions.

---

### Session Entry: 2026-10-18 (Session 11: Phase 2C Ticketing & Notification Services & Challenge 3D Completed)

#### 1. Implementation Summary (Phase 2C & Challenge 3D)
- **Ticketing Service Full Implementation (`services/ticketing/`, Port 8005, `ticketing_db`)**:
  - Implemented with Python 3.12, FastAPI, and SQLAlchemy Asyncpg on PostgreSQL `ticketing_db`.
  - Added deterministic berth/seat allocation (Lower, Middle, Upper, VIP), 10-digit Indian Railway format PNR generation (`PNR-TATKAL-XXXXXX`, `PNR-CONCERT-XXXXXX`, `PNR-BUS-XXXXXX`), and SHA-256 digital security barcode issuance.
  - Endpoints: `POST /issue`, `GET /pnr/:pnr`, `GET /booking/:id`, `POST /cancel`, `POST /reset`, `GET /health`.
  - Exported OpenAPI specification to [docs/openapi/ticketing_service_openapi.json](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs/openapi/ticketing_service_openapi.json).
  - Executed automated unit tests (`services/ticketing/tests/test_ticketing.py`): 3/3 passed (PNR issuance, idempotent fulfillment, compensating cancellation).
- **Notification Service Full Implementation (`services/notification/`, Port 8004, `notification_db`)**:
  - Connected Node.js/Express service to RabbitMQ topic exchange `seatlock.events` and durable queue `booking.notifications`.
  - Implemented consumer-side deduplication store (`processed_events` collection with 7-day TTL index) ensuring "at-least-once" AMQP redeliveries do not generate duplicate SMS/email alerts.
  - Endpoints: `GET /logs`, `GET /booking/:id`, `POST /publish-test`, `POST /reset`, `GET /health`.
  - Exported OpenAPI specification to [docs/openapi/notification_service_openapi.json](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs/openapi/notification_service_openapi.json).
- **Challenge 3D (Event-Driven Broker, Deduplication & Offline Catch-Up) Verified**:
  - Automated benchmark runner: [scripts/challenge3_event_driven.py](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/challenge3_event_driven.py).
  - **Part 1 (Consumer Deduplication)**: Duplicate event with identical `event_id` acknowledged and discarded; exactly 1 delivery record in MongoDB.
  - **Part 2 (Offline Queue Catch-Up)**: `notification-service` container stopped, 3 booking events published to RabbitMQ exchange and buffered in queue. Container restarted; queue drained from 3 to 0 within 5 seconds, all 3 events delivered to MongoDB with 0% message loss.
  - Evidence generated:
    - [evidence/challenge-3-event-driven/event_driven_run.log](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-3-event-driven/event_driven_run.log)
    - [evidence/challenge-3-event-driven/README.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-3-event-driven/README.md) with Mermaid sequence architecture diagram.

#### 2. Ready for Git Commit
Phase 2C is 100% complete and fully verified.

---

### Session Entry: 2026-10-20 (Session 12: Phase 2D Booking Service, Saga Orchestrator & Challenge 3C Completed)

#### 1. Implementation Summary (Phase 2D & Challenge 3C)
- **Booking Service Full Implementation (`services/booking/`, Port 8001, `booking_db`)**:
  - Implemented with Python 3.12, FastAPI, SQLAlchemy 2.0 Asyncpg on PostgreSQL `booking_db`, and `aio-pika` AMQP publisher.
  - Implemented **Distributed Saga Orchestrator (`src/saga.py`)**:
    - **Saga State Machine**: `PENDING` $\rightarrow$ `RESERVED` $\rightarrow$ `PAID` $\rightarrow$ `TICKETED` $\rightarrow$ `CONFIRMED`.
    - Coordinates calls to Inventory Service (`reserve`), Payment Service (`charge` with Idempotency Key), Ticketing Service (`issue`), and RabbitMQ exchange `seatlock.events`.
  - Implemented **`BR4` (Automated Saga Compensating Rollback)**:
    - If payment declines (e.g. Card ends in 0002) or upstream fails, orchestrator automatically triggers compensating transaction `POST /api/v1/inventory/release` to restore held seats to the quota pool.
    - Transitions booking status to `FAILED_COMPENSATED` with complete audit trail in `saga_step_logs`.
  - Added endpoints: `POST /api/v1/bookings`, `GET /api/v1/bookings/:id`, `GET /api/v1/bookings`, `POST /api/v1/bookings/:id/cancel`, `POST /api/v1/bookings/reset`, `GET /health`.
  - Exported OpenAPI specification to [docs/openapi/booking_service_openapi.json](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs/openapi/booking_service_openapi.json).
- **Unit Tests Passed**:
  - `services/booking/tests/test_br4_saga_compensation.py` (4/4 passed in 0.80s: Happy path saga, payment failure compensation, ticketing failure compensation, inventory depleted rejection).
- **Challenge 3C End-to-End Orchestration Runner Verified**:
  - Executed [scripts/challenge3_saga_e2e.py](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/challenge3_saga_e2e.py):
    - **Scenario 1 (Happy Path)**: 2 seats reserved, ₹5,700 charged, PNR issued (`PNR-TATKAL-934319`), AMQP message published to RabbitMQ, SMS delivered in MongoDB, booking `CONFIRMED`. Available seats decremented from 5 to 3.
    - **Scenario 2 (Payment Decline Rollback - BR4)**: Declined card returned HTTP 402, booking marked `FAILED_COMPENSATED`, inventory released back to pool. **Zero inventory leakage verified (available seats remained exactly 3)**.
  - Raw evidence log preserved at [evidence/challenge-3-saga/saga_run.log](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-3-saga/saga_run.log).
  - Authored architectural evidence report at [evidence/challenge-3-saga/README.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-3-saga/README.md).
- **System Health**:
  - All 6 microservices operational and healthy (200 UP verified via `scripts/verify_phase1_health.py`).

#### 2. Ready for Git Commit
Phase 2D is 100% complete and verified. Ready for user commit.

---

### Session Entry: 2026-10-21 (Session 13: Phase 3 Next.js Live Dashboard Cockpit Completed)

#### 1. Implementation Summary (Phase 3 Frontend Cockpit)
- **Next.js 14 Web Application (`frontend/`, Port 3000)**:
  - Scaffolding with React 18, Next.js 14 (App Router), Vanilla CSS Design System, and Lucide-React icons.
  - Configured `frontend/Dockerfile` and integrated `seatlock-frontend` into `docker-compose.yml` for unified single-command system boot (`docker compose up -d`).
  - Implemented rich dark-mode aesthetics with glassmorphism (`backdrop-filter: blur(16px)`), vivid accents (indigo, cyan, emerald, rose, amber), and Google Fonts (Inter, JetBrains Mono).
- **Core Dashboard Capabilities**:
  1. **Telemetry & Observability Bar**: Real-time health pills and latency badges for all 6 microservices (Gateway, Booking, Inventory, Payment, Ticketing, Notification) and polyglot data stores (PostgreSQL, MongoDB, Redis, RabbitMQ).
  2. **Multi-Domain Live Reservation Arena**:
     - *IRCTC Railway Tatkal (10:00 AM Rush)*: Live Coach B1 layout with Lower, Middle, and Upper berths.
     - *Concert Flash-Sale*: Coldplay World Tour VIP lounge & pit passes.
     - *Intercity Bus Sleeper*: Bangalore to Goa Volvo 9600 multi-axle berths.
     - Interactive seat selection with instant total price calculation and passenger form.
  3. **Challenge 1 Concurrency Arena**:
     - One-click trigger firing 20 simultaneous parallel requests against available seats.
     - Real-time thread outcome grid displaying exactly 5 accepted (201) and 15 rejected (409) with 0 over-allocation.
  4. **Challenge 2 Idempotency Lab**:
     - Interactive payment execution, replay inspector with `X-Idempotent-Replay: true` badge, and payload alteration detection (HTTP 422 mismatch alert).
  5. **Challenge 3C Saga Orchestrator Visualizer**:
     - Animated 5-step transaction timeline with toggle for "Simulate Payment Decline", visually demonstrating automated compensating inventory release with zero leak.
  6. **Challenge 3D AMQP Event Stream**:
     - Live RabbitMQ message feed from `seatlock.events` showing passenger SMS dispatches and deduplication records.
- **Verification**:
  - Production build compiled successfully (`npm run build`).
  - Container `seatlock-frontend` running healthy on `http://localhost:3000` (HTTP 200 OK verified).
  - All 6 backend services + infra healthy (HTTP 200 UP verified).

#### 2. Ready for Git Commit
Phase 3 is 100% complete and verified. Ready for user commit.

---

### Session Entry: 2026-10-21 (Session 14: Phase 4 Final Submission Deliverables & Documentation Completed)

#### 1. Implementation Summary (Phase 4 Deliverables)
- **Academic Design & Technical Report ([submission/DESIGN_AND_TECHNICAL_REPORT.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/DESIGN_AND_TECHNICAL_REPORT.md))**:
  - Full 10-section formal academic paper (581 lines, 40.5 KB) covering problem definition, domain context (IRCTC Tatkal, Concert Arena, Sleeper Bus), microservice boundaries, Database-per-Service ownership, Core Business Rules (`BR1`–`BR4`), API design, challenge analyses (1, 2, 3D, 3C), limitations, and Assignment 2 Kubernetes roadmap.
  - Complete with Mermaid sequence diagrams, state machines, math formulations, and traceability matrices.
- **Video Production & Demonstration Script ([submission/DEMO_VIDEO_SCRIPT.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/DEMO_VIDEO_SCRIPT.md))**:
  - Structured 8-to-10 minute presentation divided equally across 3 team members.
  - Detailed scene-by-scene script with exact dialogue, on-screen actions, split-screen guidance, and terminal benchmarks for all challenges.
- **Submission & Evaluation Checklist ([submission/SUBMISSION_CHECKLIST.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/SUBMISSION_CHECKLIST.md))**:
  - Complete verification matrix matching Section 9 of the Assignment 1 specification.
  - Formally documents 100% compliance across all 5 mandatory conditions, 4 polyglot data stores, 4 business rules, and 4 engineering challenges.
- **AI Tool Usage Declaration & Team Contributions ([submission/AI_DECLARATION_AND_CONTRIBUTIONS.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/AI_DECLARATION_AND_CONTRIBUTIONS.md))**:
  - Formal declaration conforming to BITS Pilani Academic Integrity standards detailing AI pair programming boundaries versus human engineering.
  - Equal 33.3% contribution distribution matrix across all 3 team members with specific module ownership.
- **Master Root Readme ([README.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/README.md))**:
  - Executive-ready master document with single-command quick start (`docker compose up -d`), architecture topology, service port mappings, automated benchmark execution instructions, unit tests, API reference, and direct links to all submission deliverables.

#### 2. Ready for Git Commit
Phase 4 is 100% complete and verified. Ready for user commit.

---

### Session Entry: 2026-10-21 (Session 15: Phase 5 Unified Evaluation Suite & Project Closeout Completed)

#### 1. Implementation Summary (Phase 5 & Final Closeout)
- **Master Evaluation Runner ([scripts/run_all_evaluations.py](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/run_all_evaluations.py))**:
  - Implemented unified benchmark automation script that executes all steps in sequence:
    1. Pre-flight health verification across all 6 services (HTTP 200 UP).
    2. Challenge 1: 20-thread concurrency benchmark (5 granted, 15 rejected with 409, 0 overbooked).
    3. Challenge 2: Cryptographic idempotency, replay caching (`X-Idempotent-Replay`), 422 tamper detection, and 10-thread simultaneous race.
    4. Challenge 3D: RabbitMQ broker consumer deduplication and offline container queue catch-up with 0% loss.
    5. Challenge 3C: Distributed Saga Orchestrator payment failure compensating rollback with zero seat leakage.
  - Successfully executed: All 5 steps passed with 100% compliance in 38.18s.
- **Microservices Unit Test Runner ([scripts/run_all_unit_tests.py](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/run_all_unit_tests.py))**:
  - Automated test orchestrator running unit tests across all services via `docker compose exec`:
    - Inventory Service (pytest: 4/4 passed).
    - Payment Service (jest: 5/5 passed).
    - Ticketing Service (pytest: 3/3 passed).
    - Booking Service (pytest: 4/4 passed).
  - 100% test pass rate across 16 unit tests in 13.72s.
- **Roadmap & Master Plan Synchronization ([docs/plans/MASTER_PROJECT_PLAN.md](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/docs/plans/MASTER_PROJECT_PLAN.md))**:
  - Synchronized and marked all 5 project phases as 100% COMPLETED.

#### 2. Ready for Git Commit
Phase 5 is 100% complete and verified. Ready for user commit.
