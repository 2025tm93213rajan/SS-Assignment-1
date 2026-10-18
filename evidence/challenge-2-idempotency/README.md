# Challenge 2 Evidence: Idempotency & Cryptographic Payload Fingerprinting
## Scalable Services (SEZG583) - Assignment 1

---

## 1. Challenge Claim & Summary
- **Unsafe Operation**: `POST /api/v1/payments/charge` (financial debit and payment ledger entry).
- **Mechanism Employed**: **Two-Phase Cryptographic Idempotency Middleware** using:
  1. `Idempotency-Key` header (UUID or client-generated unique token).
  2. Canonical payload normalization (recursive alphabetical key sorting).
  3. SHA-256 cryptographic fingerprinting:
     $$\text{Fingerprint} = \text{SHA256}(\text{Method} + \text{":"} + \text{Path} + \text{":"} + \text{CanonicalJSONBody})$$
  4. MongoDB `idempotency_records` collection with a unique index on `idempotency_key` and 24-hour TTL expiration.
- **Claims Verified**:
  - **Sequential Replay**: Repeating the same request returns the exact cached result with `X-Idempotent-Replay: true` header and zero duplicate payments in the database.
  - **Payload Alteration Conflict**: Reusing an `Idempotency-Key` with a modified payload (e.g., amount altered from ₹2,850 to ₹9,999) is strictly rejected with **HTTP 422 Unprocessable Entity** (`IDEMPOTENCY_PAYLOAD_MISMATCH`).
  - **Concurrent Race Protection**: 10 simultaneous parallel requests arriving at the exact same millisecond with the same key produce **exactly ONE charge record** in MongoDB, with all callers receiving identical 201 responses.

---

## 2. Test Execution & Evidence Artifacts

| Artifact File | Description |
| :--- | :--- |
| [`scripts/challenge2_idempotency.py`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/challenge2_idempotency.py) | Standalone automated Python script verifying replay, payload mismatch, and concurrent race. |
| [`evidence/challenge-2-idempotency/idempotency_run.log`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-2-idempotency/idempotency_run.log) | Complete raw JSON execution trace of all 3 test stages. |
| [`services/payment/tests/test_br3_idempotency.test.js`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/services/payment/tests/test_br3_idempotency.test.js) | Automated Jest unit test suite (5 tests passed). |

---

## 3. Terminal Execution Output (Raw Proof)

```
================================================================================
CHALLENGE 2: IDEMPOTENCY & DUPLICATE REQUEST PROTECTION TEST
================================================================================
[SETUP] Payment and Idempotency collections cleared in MongoDB.

TEST 1: Sequential Replay with Identical Idempotency-Key & Payload
--------------------------------------------------------------------------------
  First Call  -> Status: 201 (Expected: 201 Created)
                 Payment ID : pay-497761e6-87a5-4a
                 Replay Hdr : false
  Second Call -> Status: 201 (Expected: 201 Created [Replayed])
                 Payment ID : pay-497761e6-87a5-4a
                 Replay Hdr : true (Expected: true)
  MongoDB Records for Booking: 1 (Expected: exactly 1)
  -> TEST 1 PASSED: Zero duplicate charge, cached replay confirmed.

TEST 2: Reusing Same Key with Altered Payload (Payload Mismatch Detection)
--------------------------------------------------------------------------------
  Mismatched Call -> Status: 422 (Expected: 422 Unprocessable Entity)
                     Error Code: IDEMPOTENCY_PAYLOAD_MISMATCH
                     Message   : Idempotency-Key re-used with a different request payload.
  -> TEST 2 PASSED: Cryptographic SHA-256 fingerprinting rejected payload alteration.

TEST 3: Simultaneous Parallel Arrival Race (10 Concurrent Calls with Same Key)
--------------------------------------------------------------------------------
  Firing 10 requests simultaneously with Idempotency-Key: key-conc-1792333331...
  Response Status Codes : [201, 201, 201, 201, 201, 201, 201, 201, 201, 201]
  Replay Header Flags   : ['false', 'true', 'true', 'true', 'true', 'true', 'true', 'true', 'true', 'true']
  Unique Payment IDs    : ['pay-f8f9dc67-bec1-4f']
  MongoDB Records for Booking: 1 (Expected: exactly 1)
  -> TEST 3 PASSED: Exactly 1 payment created, concurrent race handled with 0 duplicates.

================================================================================
CHALLENGE 2 EVIDENCE WRITTEN TO: evidence/challenge-2-idempotency/idempotency_run.log
ALL CHALLENGE 2 IDEMPOTENCY TESTS PASSED WITH 100% SUCCESS!
================================================================================
```

---

## 4. Single-Record Database Verification (MongoDB)

```javascript
// Querying MongoDB inside seatlock-mongo container:
$ docker exec seatlock-mongo mongosh payment_db -u payment_user -p payment_pass --eval "db.payments.find({ booking_id: 'book-coldplay-conc-002' })"

[
  {
    _id: ObjectId("6712613bfb3528ef9411985c"),
    payment_id: "pay-f8f9dc67-bec1-4f",
    booking_id: "book-coldplay-conc-002",
    amount: 12500,
    currency: "INR",
    status: "SUCCESS",
    payment_method: "CARD",
    idempotency_key: "key-conc-1792333331",
    created_at: ISODate("2026-10-18T14:22:11.450Z")
  }
]
// Output: Exactly 1 record despite 10 simultaneous concurrent POST requests.
```

---

## 5. Engineering Architecture: How Concurrent Race is Solved
When multiple identical requests arrive within the same millisecond:
1. Request 1 acquires the atomic MongoDB insertion lock on `idempotency_records` with status `PENDING`.
2. Requests 2 through 10 fail insertion due to MongoDB's unique key constraint (code 11000) or find status `PENDING`.
3. Rather than returning an error, Requests 2 through 10 enter a short polling wait loop (`waitForCompletion`).
4. Once Request 1 finishes processing and updates status to `COMPLETED` with the cached response, all waiting requests immediately resolve with `X-Idempotent-Replay: true` and the original payment ID.
5. Result: 100% safe, clean user experience with zero double debits.
