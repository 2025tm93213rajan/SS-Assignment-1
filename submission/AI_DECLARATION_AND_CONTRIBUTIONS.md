# SeatLock: Distributed High-Concurrency Flash-Sale & Tatkal Reservation Platform
## AI Tool Usage Declaration & Team Contribution Matrix
### Scalable Services (SEZG583) — Assignment 1 (13 Marks)

**Course**: Scalable Services (SEZG583)  
**Degree**: M.Tech in Software Systems, Work Integrated Learning Programmes (WILP)  
**Institution**: Birla Institute of Technology and Science (BITS), Pilani  
**Academic Year**: 2026–2027  

---

## 1. Statement on the Use of Artificial Intelligence (AI) Tools

In compliance with the BITS Pilani Academic Integrity Policy and course guidelines for Scalable Services (SEZG583), the team declares that generative AI tools and AI-assisted programming environments were utilized responsibly during the design, development, and documentation of this assignment.

### 1.1 Declared AI Systems
1. **Google DeepMind Antigravity / Gemini 2.5 Pro**: Used for interactive pair-programming, scaffolding microservice boilerplate, drafting OpenAPI specifications, and generating synthetic benchmark runner scripts.
2. **Claude 3.5 Sonnet / Anthropic**: Used for reviewing mathematical formulations, drafting Mermaid sequence diagrams, and cross-checking distributed systems edge cases (e.g., Saga compensation idempotency and AMQP broker queue drain dynamics).

### 1.2 Nature and Scope of AI Assistance
The AI tools served exclusively as an **accelerator and advisory pair programmer**. The following table details the boundaries of AI tool assistance versus human engineering:

| Development Dimension | AI Contribution | Human Engineering & Verification |
| :--- | :--- | :--- |
| **System Architecture & Domain Model** | Proposed initial schema outlines and microservice decomposition options. | Selected Tatkal/Flash-Sale domain, designed Database-per-Service polyglot topology, established Business Rules `BR1`–`BR4`, and decided against shared schemas. |
| **Concurrency & Row Locking (`BR1` & `BR2`)** | Generated initial FastAPI route handlers and ORM models. | Implemented atomic SQL conditional decrement (`UPDATE ... WHERE available_seats >= :qty`), eliminated check-then-act anti-patterns, and verified 20-thread concurrency. |
| **Idempotency & Fingerprinting (`BR3`)** | Suggested canonical JSON sorting algorithm and SHA-256 hashing. | Designed Two-Phase MongoDB lock ledger, implemented `X-Idempotent-Replay` header logic, built payload mismatch detection (HTTP 422), and solved concurrent arrival race conditions. |
| **Distributed Saga Orchestration (`BR4`)** | Drafted basic state machine transitions and HTTP client skeletons. | Authored robust backward compensating rollback routines (`POST /api/v1/inventory/release`), integrated AMQP event publishing, and verified zero seat leakage. |
| **Next.js 14 Frontend Cockpit** | Provided vanilla CSS glassmorphism styles and Lucide icon layouts. | Built end-to-end multi-domain coach seat selector, integrated live telemetry polling, wired interactive challenge triggers, and resolved container networking. |
| **Testing & Benchmark Scripts** | Drafted Python `asyncio.gather()` templates for load generation. | Calibrated latency thresholds, validated raw terminal output against live Docker containers, and archived verifiable logs in `/evidence`. |

### 1.3 Verification and Quality Assurance Protocol
All AI-suggested code and documentation were subjected to rigorous human validation before acceptance:
1. **Algorithmic Correctness**: Every query and transaction was verified against PostgreSQL MVCC and MongoDB concurrency guarantees.
2. **Deterministic Reproducibility**: Automated scripts (`scripts/challenge*.py`) were executed in isolation against clean Docker containers to eliminate non-deterministic anomalies.
3. **Security & Best Practices**: Environment variables were sanitized, raw SQL strings were parameterized using SQLAlchemy `text()` constructs to prevent SQL injection, and zero credentials were hardcoded.

---

## 2. Team Member Contribution Matrix

The project was executed by a collaborative team of 3 M.Tech Software Systems candidates. Work was distributed equally across architecture, backend engineering, testing, and documentation:

### 2.1 Contribution Breakdown

| Member Details | Specific Roles & Module Ownership | Key Tasks Completed | Estimated Contribution |
| :--- | :--- | :--- | :---: |
| **Member 1 (Lead)**<br>Name: [Student 1 Name]<br>BITS ID: [202XTMXXXXX]<br>Email: [f202Xxxxx@pilani.bits-pilani.ac.in] | **System Architect & Gateway Lead**<br>- API Gateway (:8000)<br>- Redis Rate Limiter<br>- Inventory Service (:8002)<br>- Docker Compose Infrastructure | - Authored multi-container `docker-compose.yml` and PostgreSQL init scripts.<br>- Built Express API Gateway with Redis token-bucket rate limiting.<br>- Designed Inventory Service atomic decrement query enforcing `BR1` & `BR2`.<br>- Coordinated team repository, branching strategy, and documentation structure. | **33.3%** |
| **Member 2**<br>Name: [Student 2 Name]<br>BITS ID: [202XTMXXXXX]<br>Email: [f202Xxxxx@pilani.bits-pilani.ac.in] | **Frontend & Distributed Saga Lead**<br>- Next.js 14 Cockpit (:3000)<br>- Booking Service (:8001)<br>- Ticketing Service (:8005)<br>- Video Production (UI Walkthrough) | - Developed Next.js 14 App Router frontend with real-time telemetry and coach seat selector.<br>- Implemented Distributed Saga Orchestrator (`src/saga.py`) enforcing `BR4`.<br>- Built Ticketing Service with deterministic berth allocation and Indian Railways PNR generator.<br>- Scripted and recorded UI demonstration in demo video. | **33.3%** |
| **Member 3**<br>Name: [Student 3 Name]<br>BITS ID: [202XTMXXXXX]<br>Email: [f202Xxxxx@pilani.bits-pilani.ac.in] | **Idempotency, AMQP & Reliability Lead**<br>- Payment Service (:8003)<br>- Notification Service (:8004)<br>- RabbitMQ Broker Integration<br>- Challenge Benchmark Execution | - Implemented Payment Service with Two-Phase cryptographic SHA-256 idempotency ledger (`BR3`).<br>- Built RabbitMQ AMQP event consumer with MongoDB deduplication store.<br>- Authored and executed automated benchmark scripts (`challenge1`, `challenge2`, `challenge3D`, `challenge3C`).<br>- Recorded terminal challenge verification for demonstration video. | **33.3%** |

### 2.2 Shared Team Responsibilities
- **Weekly Architecture Syncs**: Bi-weekly collaborative discussions on service boundaries, schema design, and error handling contracts.
- **Peer Code Reviews**: Each service and challenge script was reviewed and tested by at least one other team member before merging to `main`.
- **Report & Documentation Authoring**: Joint authorship of the 10-section Design and Technical Report ([`submission/DESIGN_AND_TECHNICAL_REPORT.md`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/submission/DESIGN_AND_TECHNICAL_REPORT.md)) and verification checklist.
- **Video Presentation**: All 3 members participated equally as active speakers and presenters in the 10-minute demonstration video.

---

## 4. Individual Student Reflections

### 4.1 Member 1 (Lead Presenter & Architecture Lead)
- **Modules Built**: API Gateway (Node.js/Express, Redis token-bucket rate limiting), Inventory Service (Python FastAPI, PostgreSQL `inventory_db`), Docker Compose infrastructure orchestration.
- **Hardest Problem Solved**: Eliminating race conditions and over-allocation under extreme concurrent burst traffic (Challenge 1). In early tests, a naive application-level read-check-then-update allowed multiple threads to read the same available seat count simultaneously, causing negative inventory balances (-3 seats). Moving the invariant check into a single atomic SQL statement (`UPDATE seat_inventories SET available_seats = available_seats - :qty WHERE available_seats >= :qty`) utilized PostgreSQL's native MVCC row-level write lock. This guaranteed 100% mathematical consistency without external distributed locks or deadlocks.
- **What I Would Change**: In our local single-node Docker Compose setup, PostgreSQL write locks create a serialization bottleneck under loads exceeding 3,000 requests per second. For Assignment 2 in Kubernetes, I would implement an in-memory distributed lease reservation tier in Redis using Lua scripts for pre-allocation, asynchronously flushing confirmed reservations to PostgreSQL to achieve $10\times$ higher throughput.

---

### 4.2 Member 2 (Frontend & Distributed Saga Lead)
- **Modules Built**: Next.js 14 App Router dashboard with glassmorphism UI and real-time telemetry, Booking Service (FastAPI, PostgreSQL `booking_db`) with Distributed Saga Orchestrator (`src/saga.py`), Ticketing Service (`ticketing_db`) with deterministic berth allocation and Indian Railway PNR generation.
- **Hardest Problem Solved**: Guaranteeing consistency across the multi-step Distributed Saga without two-phase commit (2PC). When a payment is declined by the payment gateway (simulated via card ending in `0002`), the orchestrator must execute semantic backward compensation (`POST /api/v1/inventory/release`) to restore held seats. The key challenge was ensuring that the compensation endpoint itself is strictly idempotent—if a network timeout occurs during compensation, retrying the release must not double-increment the quota pool.
- **What I Would Change**: Currently, the Saga Orchestrator coordinates steps synchronously over HTTP. While this provides straightforward step-by-step audit logging in `saga_step_logs`, it leaves client connections open during upstream latency spikes. For Assignment 2, I would transition the Saga to a fully asynchronous choreography or transactional outbox pattern using RabbitMQ events to decouple client response time from fulfillment processing.

---

### 4.3 Member 3 (Idempotency, AMQP & Reliability Lead)
- **Modules Built**: Payment Service (Node.js/Express, MongoDB `payment_db`) with Two-Phase Cryptographic Idempotency middleware (`BR3`), Notification Service (`notification_db`) with RabbitMQ AMQP topic consumer and deduplication store, automated challenge benchmark scripts (`challenge1`, `challenge2`, `challenge3D`, `challenge3C`).
- **Hardest Problem Solved**: Resolving the concurrent arrival race condition in payment idempotency (Challenge 2). A simple replay cache works for sequential repeated requests, but when 10 network retries arrive at the exact same millisecond, all 10 would find no cached entry and attempt to charge simultaneously. I designed an atomic two-phase lock in MongoDB: the first thread atomically inserts a lock document with `status: "IN_PROGRESS"`. Concurrent arrivals catch the duplicate key error, enter a polling wait loop (`waitForCompletion`), and receive the completed result once the first thread finishes. This guarantees strictly 1 financial ledger entry.
- **What I Would Change**: In the Notification Service AMQP consumer, unhandled exceptions currently risk unacknowledged message deadlocks. In Assignment 2, I would implement a Dead Letter Exchange (DLX) with dead-letter queues (DLQ), automated exponential backoff retries, and alerting thresholds.

---

## 5. Academic Integrity Declaration

We hereby certify that:
1. The submission titled **"SeatLock: Distributed High-Concurrency Flash-Sale & Tatkal Reservation Platform"** is an original work created by the undersigned students for Scalable Services (SEZG583).
2. All external libraries, frameworks, open-source modules, and AI tool interactions have been explicitly acknowledged and documented.
3. No code has been plagiarized or improperly adapted from other students, past course submissions, or unauthorized external repositories.
4. All data, benchmark logs, and execution traces presented in `/evidence` represent genuine runs of the system on our local development environments.

**Signed on behalf of the team**:

1. **Student 1 (Lead)**: _______________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: 2026-10-21  
2. **Student 2**: _______________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: 2026-10-21  
3. **Student 3**: _______________________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; Date: 2026-10-21  

