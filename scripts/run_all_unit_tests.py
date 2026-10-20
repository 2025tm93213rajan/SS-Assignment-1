#!/usr/bin/env python3
"""
SeatLock Automated Unit Test Runner
Scalable Services (SEZG583) — Assignment 1

Executes automated unit tests across all microservices inside Docker containers:
1. Inventory Service (pytest: BR1, BR2)
2. Payment Service (jest: BR3)
3. Ticketing Service (pytest: PNR, berth allocation)
4. Booking Service (pytest: BR4 Saga compensation)
"""

import subprocess
import sys
import time

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def run_test_suite(service_name: str, test_cmd: list[str]) -> bool:
    print(f"\n[RUNNING] Executing unit tests for {service_name}...")
    start_time = time.time()
    result = subprocess.run(test_cmd)
    elapsed = time.time() - start_time
    success = (result.returncode == 0)
    status_str = "PASSED" if success else "FAILED"
    print(f"[RESULT] {service_name}: {status_str} in {elapsed:.2f}s")
    return success

def main():
    print_banner("SEATLOCK: AUTOMATED UNIT TEST SUITE")
    print(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    test_suites = [
        ("Inventory Service (BR1 & BR2 Bounds)", ["docker", "compose", "exec", "-T", "inventory-service", "pytest", "-v"]),
        ("Payment Service (BR3 Idempotency & SHA-256)", ["docker", "compose", "exec", "-T", "payment-service", "npm", "test"]),
        ("Ticketing Service (Berth & PNR Fulfillment)", ["docker", "compose", "exec", "-T", "ticketing-service", "pytest", "-v"]),
        ("Booking Service (BR4 Saga Rollback)", ["docker", "compose", "exec", "-T", "booking-service", "pytest", "-v"]),
    ]

    results = []
    overall_start = time.time()

    for name, cmd in test_suites:
        ok = run_test_suite(name, cmd)
        results.append((name, ok))

    overall_elapsed = time.time() - overall_start

    print_banner("UNIT TEST SUMMARY REPORT")
    all_passed = True
    for name, ok in results:
        status_badge = "[ PASS ]" if ok else "[ FAIL ]"
        if not ok:
            all_passed = False
        print(f"  {status_badge} {name}")

    print("-" * 80)
    print(f"Total Test Time: {overall_elapsed:.2f} seconds")
    if all_passed:
        print("ALL UNIT TEST SUITES PASSED (100% SUCCESS RATE)")
        sys.exit(0)
    else:
        print("SOME TEST SUITES FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
