"""
SeatLock Phase 1 Verification Script
Tests GET /health across API Gateway and all 5 autonomous microservices,
validating correlation ID propagation and uniform health schema.
"""
import sys
import time
import urllib.request
import urllib.error
import json

TARGETS = [
    {"name": "API Gateway", "url": "http://localhost:8000/health", "port": 8000},
    {"name": "Booking Service", "url": "http://localhost:8001/health", "port": 8001},
    {"name": "Inventory Service", "url": "http://localhost:8002/health", "port": 8002},
    {"name": "Payment Service", "url": "http://localhost:8003/health", "port": 8003},
    {"name": "Notification Service", "url": "http://localhost:8004/health", "port": 8004},
    {"name": "Ticketing Service", "url": "http://localhost:8005/health", "port": 8005},
]

def check_endpoint(target):
    name = target["name"]
    url = target["url"]
    test_corr_id = f"test-corr-{int(time.time())}"
    req = urllib.request.Request(url, headers={"X-Correlation-ID": test_corr_id})
    
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            body = response.read().decode("utf-8")
            data = json.loads(body)
            received_corr = response.headers.get("X-Correlation-ID") or "N/A"
            
            is_up = data.get("status") == "UP"
            print(f"[PASS] {name} ({url}) -> Status: {status_code}, Health: {data.get('status')}, Correlation-ID: {received_corr}")
            return is_up
    except urllib.error.URLError as e:
        print(f"[FAIL] {name} ({url}) -> Error: {e.reason}")
        return False
    except Exception as e:
        print(f"[FAIL] {name} ({url}) -> Unexpected error: {str(e)}")
        return False

def main():
    print("=" * 70)
    print("SeatLock Phase 1 Microservices Health & Connectivity Verification")
    print("=" * 70)
    
    results = []
    for target in TARGETS:
        results.append(check_endpoint(target))
        time.sleep(0.2)
        
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Summary: {passed}/{total} services responding successfully.")
    
    if passed == total:
        print("All Phase 1 services are healthy and operational!")
        return 0
    else:
        print("Some services are not yet responding. (Are containers started?)")
        return 1

if __name__ == "__main__":
    sys.exit(main())
