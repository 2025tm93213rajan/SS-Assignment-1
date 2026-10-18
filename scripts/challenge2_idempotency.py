"""
Challenge 2: Idempotency & Cryptographic Fingerprinting Verification Script
Tests:
1. Sequential Replay: Repeating identical request returns cached result with zero duplicate charge.
2. Payload Alteration Conflict: Reusing same Idempotency-Key with different payload returns HTTP 422.
3. Concurrent Race Arrival: Simultaneous parallel calls with identical key receive identical response
   and produce exactly ONE database record in MongoDB.
"""
import asyncio
import aiohttp
import time
import json
import os
import subprocess

GATEWAY_URL = "http://localhost:8000/api/v1/payments"

async def post_request(session, path, payload, headers):
    url = f"{GATEWAY_URL}{path}"
    start = time.time()
    try:
        async with session.post(url, json=payload, headers=headers) as res:
            duration_ms = round((time.time() - start) * 1000, 2)
            replay_header = res.headers.get("X-Idempotent-Replay") or "false"
            corr_id = res.headers.get("X-Correlation-ID") or "N/A"
            try:
                body = await res.json()
            except Exception:
                body = await res.text()
            return {
                "status_code": res.status,
                "duration_ms": duration_ms,
                "replay_header": replay_header,
                "correlation_id": corr_id,
                "body": body
            }
    except Exception as e:
        return {"status_code": 500, "error": str(e)}

def query_mongo_payment_count(booking_id):
    cmd = [
        "docker", "exec", "seatlock-mongo", "mongosh", "payment_db",
        "-u", "payment_user", "-p", "payment_pass", "--quiet",
        "--eval", f'db.payments.countDocuments({{ booking_id: "{booking_id}" }})'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return int(res.stdout.strip().split("\n")[-1])
    except Exception:
        return -1

async def main():
    print("=" * 80)
    print("CHALLENGE 2: IDEMPOTENCY & DUPLICATE REQUEST PROTECTION TEST")
    print("=" * 80)

    evidence_records = {}

    async with aiohttp.ClientSession() as session:
        # Reset collections
        async with session.post(f"{GATEWAY_URL}/reset") as r:
            assert r.status == 200
        print("[SETUP] Payment and Idempotency collections cleared in MongoDB.\n")

        # ----------------------------------------------------------------------
        # TEST 1: SEQUENTIAL REPLAY
        # ----------------------------------------------------------------------
        print("TEST 1: Sequential Replay with Identical Idempotency-Key & Payload")
        print("-" * 80)
        idem_key_1 = f"key-seq-{int(time.time())}"
        payload_1 = {
            "booking_id": "book-tatkal-seq-001",
            "amount": 2850.00,
            "currency": "INR",
            "payment_method": "UPI_GATEWAY"
        }

        # First Call
        call_1 = await post_request(
            session, "/charge", payload_1,
            {"Idempotency-Key": idem_key_1, "X-Correlation-ID": "corr-test1-first"}
        )
        print(f"  First Call  -> Status: {call_1['status_code']} (Expected: 201 Created)")
        print(f"                 Payment ID : {call_1['body'].get('payment_id')}")
        print(f"                 Replay Hdr : {call_1['replay_header']}")
        assert call_1["status_code"] == 201

        # Second Call (Exact Repeat)
        call_2 = await post_request(
            session, "/charge", payload_1,
            {"Idempotency-Key": idem_key_1, "X-Correlation-ID": "corr-test1-repeat"}
        )
        print(f"  Second Call -> Status: {call_2['status_code']} (Expected: 201 Created [Replayed])")
        print(f"                 Payment ID : {call_2['body'].get('payment_id')}")
        print(f"                 Replay Hdr : {call_2['replay_header']} (Expected: true)")
        assert call_2["status_code"] == 201
        assert call_2["replay_header"] == "true"
        assert call_2["body"]["payment_id"] == call_1["body"]["payment_id"]

        # Check DB count
        count_1 = query_mongo_payment_count("book-tatkal-seq-001")
        print(f"  MongoDB Records for Booking: {count_1} (Expected: exactly 1)")
        assert count_1 == 1
        print("  -> TEST 1 PASSED: Zero duplicate charge, cached replay confirmed.\n")

        evidence_records["test_1_sequential"] = {
            "first_call": call_1,
            "second_call": call_2,
            "mongodb_record_count": count_1
        }

        # ----------------------------------------------------------------------
        # TEST 2: PAYLOAD ALTERATION CONFLICT (MISMATCHED BODY)
        # ----------------------------------------------------------------------
        print("TEST 2: Reusing Same Key with Altered Payload (Payload Mismatch Detection)")
        print("-" * 80)
        altered_payload = {
            "booking_id": "book-tatkal-seq-001",
            "amount": 9999.00, # Altered amount!
            "currency": "INR",
            "payment_method": "UPI_GATEWAY"
        }

        call_mismatch = await post_request(
            session, "/charge", altered_payload,
            {"Idempotency-Key": idem_key_1, "X-Correlation-ID": "corr-test2-mismatch"}
        )
        print(f"  Mismatched Call -> Status: {call_mismatch['status_code']} (Expected: 422 Unprocessable Entity)")
        print(f"                     Error Code: {call_mismatch['body'].get('code')}")
        print(f"                     Message   : {call_mismatch['body'].get('message')}")
        assert call_mismatch["status_code"] == 422
        assert call_mismatch["body"]["code"] == "IDEMPOTENCY_PAYLOAD_MISMATCH"
        print("  -> TEST 2 PASSED: Cryptographic SHA-256 fingerprinting rejected payload alteration.\n")

        evidence_records["test_2_mismatch"] = call_mismatch

        # ----------------------------------------------------------------------
        # TEST 3: CONCURRENT SIMULTANEOUS RACE ARRIVAL
        # ----------------------------------------------------------------------
        print("TEST 3: Simultaneous Parallel Arrival Race (10 Concurrent Calls with Same Key)")
        print("-" * 80)
        idem_key_conc = f"key-conc-{int(time.time())}"
        payload_conc = {
            "booking_id": "book-coldplay-conc-002",
            "amount": 12500.00,
            "currency": "INR"
        }

        print(f"  Firing 10 requests simultaneously with Idempotency-Key: {idem_key_conc}...")
        tasks = [
            post_request(
                session, "/charge", payload_conc,
                {"Idempotency-Key": idem_key_conc, "X-Correlation-ID": f"corr-conc-{i+1:02d}"}
            )
            for i in range(10)
        ]
        conc_results = await asyncio.gather(*tasks)

        status_codes = [r["status_code"] for r in conc_results]
        replays = [r["replay_header"] for r in conc_results]
        payment_ids = set(r["body"].get("payment_id") for r in conc_results if isinstance(r.get("body"), dict))

        print(f"  Response Status Codes : {status_codes}")
        print(f"  Replay Header Flags   : {replays}")
        print(f"  Unique Payment IDs    : {list(payment_ids)}")

        # Check DB count
        count_conc = query_mongo_payment_count("book-coldplay-conc-002")
        print(f"  MongoDB Records for Booking: {count_conc} (Expected: exactly 1)")
        assert count_conc == 1
        assert len(payment_ids) == 1
        print("  -> TEST 3 PASSED: Exactly 1 payment created, concurrent race handled with 0 duplicates.\n")

        evidence_records["test_3_concurrent"] = {
            "responses": conc_results,
            "mongodb_record_count": count_conc
        }

    # Save Evidence
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "evidence", "challenge-2-idempotency")
    os.makedirs(evidence_dir, exist_ok=True)
    with open(os.path.join(evidence_dir, "idempotency_run.log"), "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence_records, indent=2))

    print("=" * 80)
    print("CHALLENGE 2 EVIDENCE WRITTEN TO: evidence/challenge-2-idempotency/idempotency_run.log")
    print("ALL CHALLENGE 2 IDEMPOTENCY TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
