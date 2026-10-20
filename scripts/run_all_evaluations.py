#!/usr/bin/env python3
"""
SeatLock Master Evaluation & Challenge Verification Runner
Scalable Services (SEZG583) — Assignment 1 (13 Marks)

Runs all automated test suites and benchmark challenges in sequence:
1. Microservices Pre-Flight Health Check
2. Challenge 1: Concurrency Control & Zero Over-Allocation (BR1, BR2)
3. Challenge 2: Two-Phase Cryptographic Idempotency Ledger (BR3)
4. Challenge 3D: RabbitMQ Event Broker & Consumer Deduplication
5. Challenge 3C: Distributed Saga Orchestration & Compensating Rollback (BR4)
"""

import sys
import subprocess
import time
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def print_banner(title: str):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)

def run_step(step_num: int, title: str, script_rel_path: str) -> bool:
    print_banner(f"STEP {step_num}: {title}")
    script_path = os.path.join(PROJECT_ROOT, script_rel_path)
    start_time = time.time()
    result = subprocess.run([sys.executable, script_path], cwd=PROJECT_ROOT)
    elapsed = time.time() - start_time
    success = (result.returncode == 0)
    status_str = "SUCCESS" if success else "FAILED"
    print(f"\n>>> [STEP {step_num}] {title}: {status_str} (Duration: {elapsed:.2f}s)")
    return success

def main():
    print_banner("SEATLOCK: UNIFIED AUTOMATED EVALUATION SUITE")
    print(f"Project Root : {PROJECT_ROOT}")
    print(f"Python Exec  : {sys.executable}")
    print(f"Timestamp    : {time.strftime('%Y-%m-%d %H:%M:%S')}")

    steps = [
        (1, "Pre-Flight Microservices Health Check", "scripts/verify_phase1_health.py"),
        (2, "Challenge 1: Concurrency & Zero Over-Allocation (BR1 & BR2)", "scripts/challenge1_concurrency.py"),
        (3, "Challenge 2: Two-Phase Cryptographic Idempotency (BR3)", "scripts/challenge2_idempotency.py"),
        (4, "Challenge 3D: RabbitMQ AMQP Broker & Offline Queue Catch-Up", "scripts/challenge3_event_driven.py"),
        (5, "Challenge 3C: Distributed Saga Compensating Rollback (BR4)", "scripts/challenge3_saga_e2e.py"),
    ]

    results = []
    overall_start = time.time()

    for step_num, title, script_rel_path in steps:
        ok = run_step(step_num, title, script_rel_path)
        results.append((step_num, title, ok))

    overall_elapsed = time.time() - overall_start

    print_banner("SEATLOCK EVALUATION SUMMARY & COMPLIANCE MATRIX")
    all_passed = True
    for step_num, title, ok in results:
        status_badge = "[ PASS ]" if ok else "[ FAIL ]"
        if not ok:
            all_passed = False
        print(f"  {status_badge} Step {step_num}: {title}")

    print("-" * 80)
    print(f"Total Execution Time : {overall_elapsed:.2f} seconds")
    if all_passed:
        print("FINAL VERDICT        : 100% COMPLIANT — ALL CHALLENGES PASSED (13/13 MARKS READY)")
        print("Evidence Logs        : Check /evidence and /submission directories")
        sys.exit(0)
    else:
        print("FINAL VERDICT        : SOME STEPS FAILED — Review output logs above")
        sys.exit(1)

if __name__ == "__main__":
    main()
