# Assignment 1 Instructions, Evaluation Rubric & Quality Guidelines
## Scalable Services (SEZG583) | MTech | 13 Marks

---

## 1. Course Information & Deliverable Deadlines
- **Course**: Scalable Services (SEZG583)
- **Marks**: 13 (Assignment 1 of 2; Assignment 2 carries another 7)
- **Team Size**: 3 Students (including Lead)
- **Submission Requirements**:
  1. GitHub Repository Link (faculty must be able to view and clone)
  2. Design Report (PDF, maximum 15 pages excluding appendices)
  3. Demo Video Link (8 to 10 minutes; live terminals and API calls, all members speak)
  4. Evidence directory (`/evidence`) inside the repository

---

## 2. Evaluation Matrix (13 Marks Breakdown)

| Criteria | Marks | What Evaluators Look For |
| :--- | :---: | :--- |
| **Problem & Decomposition** | **2** | Meaningful application, sound service boundaries, clear data ownership (database-per-service), justified decisions. |
| **Architecture & API Design** | **2** | Clear diagrams, communication choices, OpenAPI quality, error handling, explicit state machines. |
| **Implementation Quality** | **3** | Working services, business rules enforced, input validation, config via environment variables, tests, repository hygiene. |
| **Engineering Challenges** | **3** | Challenges 1, 2, and chosen Challenge 3: correctness, repeatability, honest analysis of limits. |
| **Report, Video & Evidence** | **3** | Clarity, completeness, traceability of claims to evidence in `/evidence`. |

---

## 3. The 5 Mandatory Conditions Checklist
- [x] **Condition (a)**: At least 4 services with distinct business responsibilities (we have 5: Inventory, Booking, Payment, Ticketing, Notification).
- [x] **Condition (b)**: At least one business transaction spanning 3+ services (multi-step Checkout Saga: Booking $\rightarrow$ Inventory $\rightarrow$ Payment $\rightarrow$ Ticketing $\rightarrow$ Notification).
- [x] **Condition (c)**: At least one contended resource that can be over-allocated (Tatkal Train Berths / VIP Concert Seats, capacity $N=5$).
- [x] **Condition (d)**: At least one operation unsafe to repeat (Payment Charge & Ticket Issuance, protected by `Idempotency-Key`).
- [x] **Condition (e)**: At least one dependency that can be slow or fail (Mock Payment Gateway with injected latency and failure modes).

---

## 4. Common Mistakes That Lose Marks
1. Shared database or cross-service queries/joins.
2. Services that are merely CRUD wrappers without distributed transactions.
3. Concurrency handled by check-then-update in code with no locking or atomicity.
4. Idempotency tested only with sequential repeats.
5. Evidence showing only happy paths.
6. Code copied from tutorials that the team cannot explain in the video.
7. A repository that does not run directly from its README.
