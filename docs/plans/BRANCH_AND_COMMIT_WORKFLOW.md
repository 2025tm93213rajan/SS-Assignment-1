# Git Branching & Conventional Commit Workflow Guide
## Scalable Services (SEZG583) - Assignment 1

---

## 1. Branching Strategy

To maintain a clean, professional git history for faculty review and to allow clear attribution across the **3 team members**:
- **`main`**: Production-ready, stable codebase where only fully tested features and phases are merged.
- **`feat/<module-name>`**: Dedicated feature branches for developing individual microservices, infrastructure, or sagas.
- **`test/<challenge-name>`**: Dedicated branches for test suites, concurrency benchmarks, and challenge verification scripts.
- **`docs/<topic>`**: Documentation updates, diagrams, and submission reports.

---

## 2. Conventional Commit Guidelines

Every commit must follow the [Conventional Commits v1.0.0](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short imperative summary>

<detailed multi-line description explaining WHY and WHAT changed>

- Bullet points of key modifications
- Traceability to Assignment Requirements / Business Rules
```

### Commit Types:
- `feat`: A new microservice, endpoint, infrastructure setup, or business logic feature.
- `test`: Unit tests, integration tests, or challenge validation scripts.
- `docs`: Documentation, architecture diagrams, guidelines, or report drafts.
- `fix`: Bug fix, error handling correction, or race condition patch.
- `refactor`: Code restructuring without behavioral changes.
- `chore`: Dependency updates, build configs, or workspace maintenance.

---

## 3. Phase-by-Phase Branch & Commit Mapping

### Phase 1: Infrastructure & Service Scaffolding (Current Step)
- **Branch Name**: `feat/phase1-infrastructure-scaffolding`
- **Commit Header**: `feat(infra): scaffold polyglot docker infrastructure and 5 microservices`
- **Commit Body**:
  ```
  Set up multi-container Docker Compose ecosystem with isolated databases,
  message broker, in-memory cache, API gateway, and 5 microservice skeletons.

  - Configured PostgreSQL 16 with automated multi-database init script
    (inventory_db, booking_db, ticketing_db) ensuring Database-per-Service.
  - Configured MongoDB 7 with automated init script (payment_db, notification_db).
  - Configured Redis 7 and RabbitMQ 3.13 with Management Web UI.
  - Scaffolded 5 autonomous microservices with GET /health and X-Correlation-ID:
    * services/inventory (Python/FastAPI, Port 8002)
    * services/booking (Python/FastAPI, Port 8001)
    * services/payment (Node.js/Express, Port 8003)
    * services/ticketing (Python/FastAPI, Port 8005)
    * services/notification (Node.js/Express, Port 8004)
  - Implemented API Gateway (Node.js/Express, Port 8000) with Redis rate limiting.
  - Created automated health verification script (scripts/verify_phase1_health.py).
  - Traceable to Assignment 1 Mandatory Requirements & Linkage to Assignment 2.
  ```

---

### Phase 2A: Inventory Service & Concurrency (BR1, BR2, Challenge 1)
- **Branch Name**: `feat/inventory-concurrency-br1-br2`
- **Suggested Owner**: Member 2
- **Commit Header**: `feat(inventory): implement atomic seat allocation and conditional updates`
- **Commit Body**:
  ```
  Implement Tatkal and concert quota inventory engine with database-level
  atomic conditional updates to prevent race conditions.

  - Implemented BR1 (Zero Over-allocation) and BR2 (Atomic Conditional Updates).
  - Added PostgreSQL tables: trips_events, quotas, seat_inventories.
  - Implemented reserve and release REST endpoints with error schemas.
  - Added unit test suite for BR1 and BR2.
  ```

---

### Phase 2B: Payment Service & Idempotency (BR3, Challenge 2)
- **Branch Name**: `feat/payment-idempotency-br3`
- **Suggested Owner**: Member 3
- **Commit Header**: `feat(payment): implement SHA-256 fingerprint idempotency and mock gateway`
- **Commit Body**:
  ```
  Implement payment charge processing with two-phase SHA-256 payload
  fingerprinting and replay cache protection.

  - Implemented BR3 (Strict Two-Phase Idempotency with Fingerprinting).
  - Handled sequential replay (200 OK), payload mismatch conflict (422),
    and concurrent simultaneous race arrivals.
  - Added configurable chaos latency and failure mode toggles.
  - Added unit test suite for BR3.
  ```

---

### Phase 2C: Ticketing & Notification Services (Challenge 3D)
- **Branch Name**: `feat/ticketing-notification-amqp`
- **Suggested Owner**: Member 3
- **Commit Header**: `feat(notif): implement rabbitmq consumer with offline catch-up and PNR fulfillment`
- **Commit Body**:
  ```
  Implement digital ticket PNR issuance and asynchronous RabbitMQ event
  consumer with durable offline catch-up capabilities.

  - Added ticketing-service PNR generation and berth uniqueness constraints.
  - Added notification-service AMQP consumer listening to seatlock.events.
  - Handled consumer-side idempotency via processed_events MongoDB collection.
  - Satisfies Challenge 3D (Event-Driven Broker Flow).
  ```

---

### Phase 2D: Booking Service Saga Orchestration (BR4, Challenge 3C)
- **Branch Name**: `feat/booking-saga-orchestrator`
- **Suggested Owner**: Member 1 (Lead)
- **Commit Header**: `feat(booking): implement multi-service checkout saga with compensating rollback`
- **Commit Body**:
  ```
  Implement distributed Saga state machine coordinating Inventory, Payment,
  Ticketing, and Notification dispatch.

  - Implemented BR4 (Saga Compensating Rollback on Downstream Failure).
  - Added state transitions: PENDING -> RESERVED -> PAID -> TICKETED -> CONFIRMED.
  - Automated compensating release call to Inventory Service on payment failure.
  - Added unit test suite for BR4.
  ```

---

### Phase 3: Next.js Frontend Live Dashboard
- **Branch Name**: `feat/frontend-live-cockpit`
- **Suggested Owner**: Member 1
- **Commit Header**: `feat(frontend): build interactive stress-test and reservation cockpit`

---

### Phase 4: Automated Challenge Runners & Evidence Harvesting
- **Branch Name**: `test/challenges-evidence-suite`
- **Suggested Owner**: All Members
- **Commit Header**: `test(challenges): execute concurrency, idempotency and saga test runners`

---

### Phase 5: Submission Documentation & Report
- **Branch Name**: `docs/submission-report-and-video-script`
- **Suggested Owner**: All Members
- **Commit Header**: `docs(submission): finalize design report markdown, video script and checklist`
