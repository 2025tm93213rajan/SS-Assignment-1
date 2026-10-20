# Automated Unit Test Suite & Traceability Evidence
## Scalable Services (SEZG583) — Assignment 1

This directory contains the test execution records, test mappings, and verification proof for all microservices in the **SeatLock** platform.

---

## 1. Test Suite Architecture & Command

The entire unit test suite across all services can be executed with a single command from the root directory:

```bash
python scripts/run_all_unit_tests.py
```

This runs isolated containerized unit tests via `docker compose exec`:
- **Inventory Service**: `pytest -v` inside `inventory-service` container
- **Payment Service**: `npm test` (Jest) inside `payment-service` container
- **Ticketing Service**: `pytest -v` inside `ticketing-service` container
- **Booking Service**: `pytest -v` inside `booking-service` container

---

## 2. Business Rules & Unit Test Mapping Matrix

| Business Rule | Service | Test File & Function | What is Tested | Test Result |
| :---: | :--- | :--- | :--- | :---: |
| **`BR1`** | `inventory-service` | `tests/test_br1_inventory_bound.py`<br>- `test_br1_successful_reservation`<br>- `test_br1_zero_overallocation_prevention`<br>- `test_br1_cannot_reserve_more_than_initial_capacity` | Verifies that available inventory is decremented accurately and that requests exceeding capacity are strictly rejected with HTTP 409 Conflict. Proves $A \ge 0$ invariant. | **PASSED** (0.60s) |
| **`BR2`** | `inventory-service` | `tests/test_br2_atomic_concurrency.py`<br>- `test_br2_atomic_concurrency_20_requests_for_5_capacity` | Fires 20 concurrent asyncio tasks against 5 seats using atomic conditional SQL (`WHERE available >= :qty`). Confirms exactly 5 succeed (201) and 15 fail (409). | **PASSED** |
| **`BR3`** | `payment-service` | `tests/test_br3_idempotency.test.js`<br>- `BR3.1: Missing Idempotency-Key returns 400`<br>- `BR3.2: First call charges and creates 1 record`<br>- `BR3.3: Replay returns cached response with X-Idempotent-Replay`<br>- `BR3.4: Reusing key with altered payload returns 422`<br>- `BR3.5: Downstream failure simulation returns 402` | Validates Two-Phase Cryptographic Idempotency with canonical JSON normalization, SHA-256 fingerprinting, replay caching, and body mismatch protection. | **PASSED** (1.31s) |
| **`BR4`** | `booking-service` | `tests/test_br4_saga_compensation.py`<br>- `test_br4_happy_path_saga`<br>- `test_br4_payment_failure_triggers_compensating_inventory_release`<br>- `test_br4_ticketing_failure_triggers_compensation`<br>- `test_br4_inventory_exhausted_rejects_without_payment` | Validates Distributed Saga Orchestrator. When payment fails (card ends in `0002`), automatically triggers compensating inventory release `POST /api/v1/inventory/release`, marking booking `FAILED_COMPENSATED` with 0 inventory leakage. | **PASSED** (1.17s) |
| **Fulfillment** | `ticketing-service` | `tests/test_ticketing.py`<br>- `test_issue_pnr_and_berths_success`<br>- `test_pnr_fulfillment_idempotent_reissue`<br>- `test_compensating_cancellation` | Verifies deterministic berth allocation, 10-digit Indian Railway PNR format, and digital security barcode generation. | **PASSED** (0.46s) |

---

## 3. Test Execution Summary

- **Total Unit Tests Executed**: 16 tests across 4 test suites
- **Passed**: 16 / 16 (100% Success Rate)
- **Failed**: 0
- **Total Execution Time**: ~13.7 seconds
- **Raw Execution Log**: [`unit_tests_run.log`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/tests/unit_tests_run.log)
