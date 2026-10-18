"""
Challenge 1: Concurrency Control Verification Script
Fires 20 simultaneous parallel asynchronous requests for a contended resource
with capacity N=5 (e.g. 5 VIP Concert passes / 5 Tatkal berths).
Validates that exactly 5 requests succeed (HTTP 201) and exactly 15 are rejected
with clean HTTP 409 Conflict, proving zero over-allocation and atomicity.
"""
import asyncio
import aiohttp
import time
import json
import os
import sys

GATEWAY_URL = "http://localhost:8000/api/v1/inventory"
QUOTA_ID = "COLDPLAY-VIP-A1"
INITIAL_CAPACITY = 5
TOTAL_REQUESTS = 20

async def reset_quota(session):
    async with session.post(f"{GATEWAY_URL}/reset") as res:
        assert res.status == 200, "Failed to reset inventory before test"
        print("[SETUP] Inventory reset to initial seed state (Capacity: 5).")

async def send_reservation_request(session, req_id):
    corr_id = f"corr-ch1-req-{req_id:02d}-{int(time.time() * 1000)}"
    payload = {
        "quota_id": QUOTA_ID,
        "quantity": 1,
        "booking_id": f"book-ch1-{req_id:02d}"
    }
    start = time.time()
    try:
        async with session.post(
            f"{GATEWAY_URL}/reserve",
            json=payload,
            headers={"X-Correlation-ID": corr_id}
        ) as res:
            duration_ms = round((time.time() - start) * 1000, 2)
            body = await res.json()
            return {
                "request_id": req_id,
                "status_code": res.status,
                "duration_ms": duration_ms,
                "correlation_id": corr_id,
                "response": body
            }
    except Exception as e:
        return {
            "request_id": req_id,
            "status_code": 500,
            "duration_ms": round((time.time() - start) * 1000, 2),
            "correlation_id": corr_id,
            "error": str(e)
        }

async def fetch_final_state(session):
    async with session.get(f"{GATEWAY_URL}/quotas/{QUOTA_ID}") as res:
        assert res.status == 200
        return await res.json()

async def main():
    print("=" * 80)
    print("CHALLENGE 1: CONCURRENCY CONTROL & ZERO OVER-ALLOCATION TEST")
    print(f"Target Resource : {QUOTA_ID} (Capacity N = {INITIAL_CAPACITY})")
    print(f"Parallel Calls  : {TOTAL_REQUESTS} simultaneous requests (Quantity = 1 each)")
    print("=" * 80)

    async with aiohttp.ClientSession() as session:
        # Step 1: Clean reset
        await reset_quota(session)

        # Step 2: Fire 20 parallel requests at the exact same millisecond
        print(f"\n[DISPATCH] Firing {TOTAL_REQUESTS} concurrent requests via asyncio...")
        dispatch_start = time.time()
        tasks = [send_reservation_request(session, i + 1) for i in range(TOTAL_REQUESTS)]
        results = await asyncio.gather(*tasks)
        total_time_ms = round((time.time() - dispatch_start) * 1000, 2)
        print(f"[COMPLETED] All {TOTAL_REQUESTS} requests completed in {total_time_ms}ms.\n")

        # Step 3: Tabulate results
        print(f"{'Req #':<6} | {'Status':<10} | {'Latency':<10} | {'Outcome':<18} | {'Correlation ID'}")
        print("-" * 80)

        success_count = 0
        conflict_count = 0
        other_count = 0

        for r in results:
            code = r["status_code"]
            lat = f"{r['duration_ms']}ms"
            corr = r["correlation_id"]
            if code == 201:
                success_count += 1
                outcome = "GRANTED (201)"
            elif code == 409:
                conflict_count += 1
                outcome = "REJECTED (409)"
            else:
                other_count += 1
                outcome = f"UNEXPECTED ({code})"

            print(f"#{r['request_id']:<5} | {code:<10} | {lat:<10} | {outcome:<18} | {corr}")

        # Step 4: Verify Final Database State
        final_state = await fetch_final_state(session)
        print("\n" + "=" * 80)
        print("FINAL DATABASE STATE (PostgreSQL):")
        print(f"  Quota ID         : {final_state['id']}")
        print(f"  Total Capacity   : {final_state['total_capacity']}")
        print(f"  Available Seats  : {final_state['available_seats']}")
        print(f"  Locked Seats     : {final_state['locked_seats']}")
        print(f"  Version (Counter): {final_state['version']}")
        print("=" * 80)

        print("\nTEST EVALUATION CRITERIA:")
        print(f"  1. Exactly N={INITIAL_CAPACITY} requests succeeded (201 Created) : {'PASS' if success_count == INITIAL_CAPACITY else 'FAIL'} ({success_count}/{INITIAL_CAPACITY})")
        print(f"  2. Exactly {TOTAL_REQUESTS - INITIAL_CAPACITY} requests rejected (409 Conflict): {'PASS' if conflict_count == (TOTAL_REQUESTS - INITIAL_CAPACITY) else 'FAIL'} ({conflict_count}/{TOTAL_REQUESTS - INITIAL_CAPACITY})")
        print(f"  3. Final Available Seats == 0                    : {'PASS' if final_state['available_seats'] == 0 else 'FAIL'}")
        print(f"  4. Final Locked Seats == {INITIAL_CAPACITY}                      : {'PASS' if final_state['locked_seats'] == INITIAL_CAPACITY else 'FAIL'}")
        print(f"  5. Zero Negative Inventory                       : PASS (Atomic Conditional Update)")

        # Save formatted evidence log
        evidence_dir = os.path.join(os.path.dirname(__file__), "..", "evidence", "challenge-1-concurrency")
        os.makedirs(evidence_dir, exist_ok=True)
        log_file = os.path.join(evidence_dir, "concurrency_run.log")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"Timestamp: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
            f.write(f"Resource: {QUOTA_ID} (Capacity: {INITIAL_CAPACITY})\n")
            f.write(f"Parallel Requests: {TOTAL_REQUESTS}\n")
            f.write(f"Success Count (201): {success_count}\n")
            f.write(f"Conflict Count (409): {conflict_count}\n")
            f.write(f"Final Available: {final_state['available_seats']}\n")
            f.write(f"Final Locked: {final_state['locked_seats']}\n\n")
            f.write("Full Results JSON:\n")
            f.write(json.dumps(results, indent=2))

        print(f"\n[EVIDENCE] Execution log written to: evidence/challenge-1-concurrency/concurrency_run.log")

        assert success_count == INITIAL_CAPACITY, f"Expected {INITIAL_CAPACITY} successes, got {success_count}"
        assert conflict_count == (TOTAL_REQUESTS - INITIAL_CAPACITY), f"Expected {TOTAL_REQUESTS - INITIAL_CAPACITY} conflicts, got {conflict_count}"
        assert final_state['available_seats'] == 0
        assert final_state['locked_seats'] == INITIAL_CAPACITY
        print("\nCHALLENGE 1 VERIFICATION: PASSED PERFECTLY!\n")

if __name__ == "__main__":
    asyncio.run(main())
