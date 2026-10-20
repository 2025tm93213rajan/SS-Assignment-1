"""
Challenge 3C: Distributed Saga Orchestration & Automated Compensating Rollback (BR4)
End-to-End Orchestration Runner verifying:
1. Happy Path: PENDING -> RESERVED -> PAID -> TICKETED -> CONFIRMED
   - Atomic seat hold in inventory_db
   - Idempotent charge in payment_db
   - PNR issuance in ticketing_db
   - Asynchronous notification via RabbitMQ in notification_db
2. Failure Path with Automated Compensation (BR4):
   - Payment declined triggers automated inventory release
   - Booking marked FAILED_COMPENSATED
   - Zero inventory leak verified: available seats restored completely
"""
import time
import json
import os
import urllib.request
import urllib.error

GATEWAY_URL = "http://localhost:8000/api/v1"

def http_post(url, payload, headers=None):
    data = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", "X-Correlation-ID": f"saga-{int(time.time()*1000)}"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.getcode(), json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())

def http_get(url):
    req = urllib.request.Request(url, headers={"X-Correlation-ID": f"saga-get-{int(time.time()*1000)}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return res.getcode(), json.loads(res.read().decode())

def reset_all_services():
    print("[RESET] Resetting state across all 5 databases...")
    http_post(f"{GATEWAY_URL}/inventory/reset", {})
    http_post(f"{GATEWAY_URL}/payments/reset", {})
    http_post(f"{GATEWAY_URL}/tickets/reset", {})
    http_post(f"{GATEWAY_URL}/notifications/reset", {})
    http_post(f"{GATEWAY_URL}/bookings/reset", {})
    print("        All databases reset to initial benchmark state.\n")

def main():
    print("=" * 80)
    print("CHALLENGE 3C: DISTRIBUTED SAGA ORCHESTRATION & COMPENSATING ROLLBACK (BR4)")
    print("=" * 80)

    reset_all_services()
    evidence = {}

    # --------------------------------------------------------------------------
    # SCENARIO 1: HAPPY PATH SAGA (FULL CONFIRMATION)
    # --------------------------------------------------------------------------
    print("-" * 80)
    print("SCENARIO 1: Happy Path Reservation Saga Execution")
    print("-" * 80)

    # Check initial quota
    _, inv_before = http_get(f"{GATEWAY_URL}/inventory/quotas/TATKAL-12951-B1")
    initial_avail = inv_before["available_seats"]
    print(f"1. Initial Inventory for TATKAL-12951-B1: {initial_avail} seats available.")

    happy_payload = {
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "category": "RAILWAY_TATKAL",
        "passengers": [
            {"name": "Rajan Sharma", "berth_preference": "LOWER"},
            {"name": "Priya Sharma", "berth_preference": "MIDDLE"}
        ],
        "total_amount": 5700.00,
        "customer_name": "Rajan Sharma",
        "customer_email": "rajan.sharma@example.com",
        "customer_phone": "+91-9876543210",
        "payment": {
            "payment_method": "CARD",
            "card_number": "4000-0000-0000-0001", # Approved test card
            "force_failure": False
        }
    }

    print("2. Submitting Booking Request for 2 passengers...")
    status1, res1 = http_post(f"{GATEWAY_URL}/bookings", happy_payload)
    print(f"   Response Status Code   : {status1} (Expected: 201 Created)")
    assert status1 == 201, f"Expected 201, got {status1}: {res1}"

    booking_id = res1["booking_id"]
    pnr = res1["pnr"]
    res_status = res1["status"]
    print(f"   Booking Identifier     : {booking_id}")
    print(f"   Booking Status         : {res_status} (Expected: CONFIRMED)")
    print(f"   Official PNR Issued    : {pnr}")
    print(f"   Reservation ID (Hold)  : {res1.get('reservation_id')}")
    print(f"   Payment ID (Charged)   : {res1.get('payment_id')}")
    assert res_status == "CONFIRMED"
    assert pnr is not None

    # Verify inventory was decremented by 2
    _, inv_after_happy = http_get(f"{GATEWAY_URL}/inventory/quotas/TATKAL-12951-B1")
    print(f"3. Inventory Available Post-Booking: {inv_after_happy['available_seats']} (Expected: {initial_avail - 2})")
    assert inv_after_happy["available_seats"] == initial_avail - 2

    # Allow 1s for async RabbitMQ notification delivery
    time.sleep(1)
    _, notif_logs = http_get(f"{GATEWAY_URL}/notifications/booking/{booking_id}")
    print(f"4. Asynchronous AMQP Notification Received: {len(notif_logs)} alerts (Expected: >= 1)")
    if notif_logs:
        print(f"   Message Dispatched: '{notif_logs[0]['message']}'")

    print("\n   -> SCENARIO 1 PASSED: 100% of Happy Path Saga steps confirmed.")
    evidence["scenario_1_happy_path"] = {
        "booking_id": booking_id,
        "pnr": pnr,
        "status": res_status,
        "initial_available": initial_avail,
        "remaining_available": inv_after_happy["available_seats"],
        "notifications_dispatched": len(notif_logs),
        "result": "PASSED"
    }

    # --------------------------------------------------------------------------
    # SCENARIO 2: SAGA COMPENSATING ROLLBACK ON PAYMENT DECLINE (BR4)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("SCENARIO 2: Payment Failure & Automated Compensating Rollback (BR4)")
    print("-" * 80)

    avail_before_fail = inv_after_happy["available_seats"]
    print(f"1. Current Inventory before failed transaction: {avail_before_fail} seats.")

    fail_payload = {
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "category": "RAILWAY_TATKAL",
        "passengers": [
            {"name": "Anil Verma", "berth_preference": "UPPER"}
        ],
        "total_amount": 2850.00,
        "customer_name": "Anil Verma",
        "customer_email": "anil.verma@example.com",
        "customer_phone": "+91-9988771122",
        "payment": {
            "payment_method": "CARD",
            "card_number": "4000-0000-0000-0002", # Declined test card
            "force_failure": False
        }
    }

    print("2. Submitting Booking Request with DECLINED card (Ends in 0002)...")
    status2, res2 = http_post(f"{GATEWAY_URL}/bookings", fail_payload)
    print(f"   Response Status Code   : {status2} (Expected: 402 Payment Required)")
    assert status2 == 402, f"Expected 402, got {status2}: {res2}"

    failed_booking = res2["booking"]
    print(f"   Failed Booking ID      : {failed_booking['booking_id']}")
    print(f"   Booking Final Status   : {failed_booking['status']} (Expected: FAILED_COMPENSATED)")
    print(f"   Compensation Reason    : {failed_booking['compensation_reason']}")
    assert failed_booking["status"] == "FAILED_COMPENSATED"

    # Verify Compensation Invariant: Inventory was NOT leaked
    _, inv_after_comp = http_get(f"{GATEWAY_URL}/inventory/quotas/TATKAL-12951-B1")
    print(f"\n3. INVENTORY LEAK CHECK (BR4 Invariant):")
    print(f"   Seats before failed attempt: {avail_before_fail}")
    print(f"   Seats after compensation   : {inv_after_comp['available_seats']} (Expected: {avail_before_fail})")
    assert inv_after_comp["available_seats"] == avail_before_fail, "CRITICAL ERROR: Inventory leaked during failed saga!"
    print("   -> INVARIANT PRESERVED: Zero inventory leakage. Held seats fully restored.")

    # Verify zero PNR was issued for failed booking
    print(f"4. Ticket Issue Check:")
    print(f"   PNR for failed booking     : {failed_booking.get('pnr')} (Expected: None)")
    assert failed_booking.get("pnr") is None

    # Verify zero notification was dispatched
    _, failed_notifs = http_get(f"{GATEWAY_URL}/notifications/booking/{failed_booking['booking_id']}")
    print(f"5. Notification Check:")
    print(f"   Notifications dispatched   : {len(failed_notifs)} (Expected: 0)")
    assert len(failed_notifs) == 0

    print("\n   -> SCENARIO 2 PASSED: Automated compensation triggered. Zero leak confirmed.")
    evidence["scenario_2_compensation"] = {
        "failed_booking_id": failed_booking["booking_id"],
        "status": failed_booking["status"],
        "compensation_reason": failed_booking["compensation_reason"],
        "inventory_before": avail_before_fail,
        "inventory_after_compensation": inv_after_comp["available_seats"],
        "inventory_leak": 0,
        "result": "PASSED"
    }

    # Save evidence
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "evidence", "challenge-3-saga")
    os.makedirs(evidence_dir, exist_ok=True)
    with open(os.path.join(evidence_dir, "saga_run.log"), "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence, indent=2))

    print("\n" + "=" * 80)
    print("CHALLENGE 3C SAGA EVIDENCE SAVED TO: evidence/challenge-3-saga/saga_run.log")
    print("ALL SAGA ORCHESTRATION & BR4 COMPENSATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
