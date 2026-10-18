"""
Live Inventory Service Integration & Challenge 1 Pre-Verification Script
Tests inventory listing, atomic reservation, capacity exhaustion (409),
and compensating release via the API Gateway (Port 8000).
"""
import urllib.request
import urllib.error
import json
import time

GATEWAY_URL = "http://localhost:8000/api/v1/inventory"

def http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Correlation-ID": f"test-inventory-{int(time.time() * 1000)}"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.getcode(), json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))

def http_get(url):
    req = urllib.request.Request(
        url,
        headers={"X-Correlation-ID": f"test-inventory-get-{int(time.time() * 1000)}"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return res.getcode(), json.loads(res.read().decode("utf-8"))

def main():
    print("=" * 70)
    print("SeatLock Phase 2A: Inventory Service Live Integration Test")
    print("=" * 70)

    # 1. Reset inventory to clean seed state (capacity 5)
    print("\n1. Resetting demo inventory to capacity 5...")
    status, reset_res = http_post(f"{GATEWAY_URL}/reset", {})
    print(f"   Status: {status} | Message: {reset_res.get('message')}")
    assert status == 200

    # 2. List all items
    print("\n2. Fetching all items via API Gateway...")
    status, items = http_get(f"{GATEWAY_URL}/items")
    print(f"   Total items found: {len(items)}")
    for item in items:
        q_info = [f"{q['id']} (Available: {q['available_seats']}/{q['total_capacity']})" for q in item["quotas"]]
        print(f"   - {item['title']} [{item['category']}] -> {', '.join(q_info)}")
    assert len(items) == 3

    # 3. Test BR1 & BR2 Happy Path: Reserve 2 Tatkal seats on Train #12951
    print("\n3. Testing BR1/BR2 Atomic Hold (Reserve 2 Tatkal seats on Train #12951)...")
    status, res_hold = http_post(f"{GATEWAY_URL}/reserve", {"quota_id": "TATKAL-12951-B1", "quantity": 2})
    print(f"   Status: {status} | Token: {res_hold.get('reservation_token')}")
    print(f"   Held Quantity: {res_hold.get('quantity')} | Remaining: {res_hold.get('remaining_available')}")
    assert status == 201
    assert res_hold.get("remaining_available") == 3
    token = res_hold.get("reservation_token")

    # 4. Reserve remaining 3 seats to exhaust quota
    print("\n4. Reserving remaining 3 Tatkal seats...")
    status, res_hold2 = http_post(f"{GATEWAY_URL}/reserve", {"quota_id": "TATKAL-12951-B1", "quantity": 3})
    print(f"   Status: {status} | Remaining: {res_hold2.get('remaining_available')}")
    assert status == 201
    assert res_hold2.get("remaining_available") == 0

    # 5. Test BR1 Violation Prevention (Capacity Exhausted -> 409 Conflict)
    print("\n5. Testing BR1 Zero Over-allocation (Attempting to book 1 seat when available=0)...")
    status, err_res = http_post(f"{GATEWAY_URL}/reserve", {"quota_id": "TATKAL-12951-B1", "quantity": 1})
    print(f"   Status: {status} (Expected 409 Conflict)")
    print(f"   Error Code: {err_res.get('code')}")
    print(f"   Error Message: {err_res.get('message')}")
    assert status == 409
    assert err_res.get("code") == "INSUFFICIENT_INVENTORY"

    # 6. Test Compensating Rollback (Release the 2 seats held in step 3)
    print("\n6. Testing Saga Compensating Action (Releasing first 2 seats via token)...")
    status, release_res = http_post(f"{GATEWAY_URL}/release", {"reservation_token": token})
    print(f"   Status: {status} | Message: {release_res.get('message')}")
    print(f"   Released: {release_res.get('released_quantity')} | Current Available: {release_res.get('current_available')}")
    assert status == 200
    assert release_res.get("current_available") == 2

    print("\n" + "=" * 70)
    print("ALL PHASE 2A INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == "__main__":
    main()
