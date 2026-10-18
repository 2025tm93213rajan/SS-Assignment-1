# Challenge 1 Evidence: Concurrency Control & Atomic Resource Allocation
## Scalable Services (SEZG583) - Assignment 1

---

## 1. Challenge Claim & Summary
- **Contended Resource**: Concert VIP passes (`COLDPLAY-VIP-A1`) and IRCTC Tatkal train berths (`TATKAL-12951-B1`) with fixed capacity $N = 5$.
- **Mechanism Employed**: **Database-Level Atomic Conditional Updates** with row-level transaction safety in PostgreSQL:
  ```sql
  UPDATE seat_inventories
  SET 
      available = available - :qty,
      locked = locked + :qty,
      version = version + 1,
      updated_at = NOW()
  WHERE quota_id = :quota_id AND available >= :qty
  RETURNING quota_id, total_capacity, available, locked, version;
  ```
- **Claim**: When 20 parallel requests compete simultaneously at the exact same millisecond for capacity $N = 5$, **exactly 5 requests succeed (HTTP 201 Created)** and **exactly 15 requests are rejected with a clean HTTP 409 Conflict error**. Zero negative inventory and zero data corruption occur.

---

## 2. Test Execution & Evidence Artifacts

| Artifact File | Description |
| :--- | :--- |
| [`scripts/challenge1_concurrency.py`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/scripts/challenge1_concurrency.py) | Standalone reproducible Python script firing 20 parallel requests via `asyncio`. |
| [`evidence/challenge-1-concurrency/concurrency_run.log`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/evidence/challenge-1-concurrency/concurrency_run.log) | Complete timestamped output and JSON response logs from the 20-thread execution. |
| [`services/inventory/tests/test_br2_atomic_concurrency.py`](file:///c:/BITS/Sem%203/SS/Assignments/SS-Assignment-1/services/inventory/tests/test_br2_atomic_concurrency.py) | Automated Pytest unit test suite for atomic conditional updates. |

---

## 3. Terminal Execution Output (Raw Proof)

```
================================================================================
CHALLENGE 1: CONCURRENCY CONTROL & ZERO OVER-ALLOCATION TEST
Target Resource : COLDPLAY-VIP-A1 (Capacity N = 5)
Parallel Calls  : 20 simultaneous requests (Quantity = 1 each)
================================================================================
[SETUP] Inventory reset to initial seed state (Capacity: 5).

[DISPATCH] Firing 20 concurrent requests via asyncio...
[COMPLETED] All 20 requests completed in 180.31ms.

Req #  | Status     | Latency    | Outcome            | Correlation ID
--------------------------------------------------------------------------------
#1     | 201        | 138.47ms   | GRANTED (201)      | corr-ch1-req-01-1792305762458
#2     | 201        | 123.69ms   | GRANTED (201)      | corr-ch1-req-02-1792305762459
#3     | 409        | 165.18ms   | REJECTED (409)     | corr-ch1-req-03-1792305762459
#4     | 201        | 87.64ms    | GRANTED (201)      | corr-ch1-req-04-1792305762460
#5     | 409        | 163.4ms    | REJECTED (409)     | corr-ch1-req-05-1792305762460
#6     | 409        | 151.78ms   | REJECTED (409)     | corr-ch1-req-06-1792305762460
#7     | 409        | 161.26ms   | REJECTED (409)     | corr-ch1-req-07-1792305762460
#8     | 409        | 157.95ms   | REJECTED (409)     | corr-ch1-req-08-1792305762460
#9     | 409        | 167.2ms    | REJECTED (409)     | corr-ch1-req-09-1792305762460
#10    | 409        | 155.83ms   | REJECTED (409)     | corr-ch1-req-10-1792305762461
#11    | 201        | 144.24ms   | GRANTED (201)      | corr-ch1-req-11-1792305762461
#12    | 409        | 170.52ms   | REJECTED (409)     | corr-ch1-req-12-1792305762461
#13    | 409        | 153.68ms   | REJECTED (409)     | corr-ch1-req-13-1792305762461
#14    | 409        | 169.42ms   | REJECTED (409)     | corr-ch1-req-14-1792305762461
#15    | 201        | 139.36ms   | GRANTED (201)      | corr-ch1-req-15-1792305762461
#16    | 409        | 174.27ms   | REJECTED (409)     | corr-ch1-req-16-1792305762461
#17    | 409        | 148.02ms   | REJECTED (409)     | corr-ch1-req-17-1792305762461
#18    | 409        | 175.96ms   | REJECTED (409)     | corr-ch1-req-18-1792305762461
#19    | 409        | 172.12ms   | REJECTED (409)     | corr-ch1-req-19-1792305762461
#20    | 409        | 145.85ms   | REJECTED (409)     | corr-ch1-req-20-1792305762461

================================================================================
FINAL DATABASE STATE (PostgreSQL):
  Quota ID         : COLDPLAY-VIP-A1
  Total Capacity   : 5
  Available Seats  : 0
  Locked Seats     : 5
  Version (Counter): 6
================================================================================
```

---

## 4. Why Plain Check-Then-Update Fails (Engineering Analysis)

### The Anti-Pattern (Check-Then-Set in Application Code)
A naive microservice implementation typically does:
```python
# ANTI-PATTERN: DO NOT USE IN PRODUCTION
available = db.query("SELECT available FROM seat_inventories WHERE quota_id = :id")
if available >= requested_qty:
    time.sleep(0.001)  # Context switch / I/O lag
    db.execute("UPDATE seat_inventories SET available = available - :qty WHERE quota_id = :id")
```

### Why It Fails Under Concurrency:
1. **Time-of-Check to Time-of-Use (TOCTOU) Race Condition**:
   - Suppose capacity = 1.
   - Request A and Request B both execute `SELECT available` concurrently. Both read `available = 1`.
   - Both proceed into the `if available >= 1:` block.
   - Both execute the decrement statement.
   - **Result**: `available` drops to `-1`. Two tickets were issued for 1 seat! This creates catastrophic over-allocation, customer disputes, and data corruption.
2. **Database Isolation Levels**:
   - Under standard PostgreSQL `READ COMMITTED`, `SELECT` does not acquire row locks.
   - Even under `REPEATABLE READ`, concurrent updates fail with serialization errors rather than handling conditional logic atomically.

### Our Solution (Atomic Conditional Decrement):
By shifting the predicate check directly into the `WHERE` clause of an atomic `UPDATE` (`WHERE available >= :qty`):
- PostgreSQL acquires an exclusive row lock (`RowExclusiveLock`) immediately before modifying the row.
- The condition `available >= :qty` is evaluated at the instant the lock is held.
- If true, the row is updated and returned in a single round-trip.
- If false, exactly 0 rows are affected, immediately rejecting all over-allocations with HTTP 409.
- No application-level locks or distributed synchronization primitives (like Redlock) are required, resulting in sub-millisecond latencies under massive concurrency.
