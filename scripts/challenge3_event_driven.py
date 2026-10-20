"""
Challenge 3D: Event-Driven Architecture, Consumer Idempotency & Offline Catch-up
Demonstrates:
1. Consumer Deduplication: Duplicate messages published with identical event_id are safely acknowledged and discarded without duplicate dispatches.
2. Offline Consumer Catch-up: While the notification service container is stopped, messages buffer in the durable RabbitMQ queue. Upon restarting, the consumer drains the backlog with zero message loss.
"""
import time
import json
import os
import subprocess
import urllib.request
import urllib.error

GATEWAY_NOTIF_URL = "http://localhost:8000/api/v1/notifications"
RABBITMQ_API = "http://localhost:15672/api/queues/%2F/booking.notifications"
RABBIT_AUTH = ("guest", "guest")

def http_post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "X-Correlation-ID": f"ch3d-{int(time.time()*1000)}"}
    )
    with urllib.request.urlopen(req, timeout=5) as res:
        return res.getcode(), json.loads(res.read().decode())

def http_get(url):
    req = urllib.request.Request(url, headers={"X-Correlation-ID": f"ch3d-get-{int(time.time()*1000)}"})
    with urllib.request.urlopen(req, timeout=5) as res:
        return res.getcode(), json.loads(res.read().decode())

def get_rabbitmq_queue_depth():
    import base64
    req = urllib.request.Request(RABBITMQ_API)
    auth_str = base64.b64encode(f"{RABBIT_AUTH[0]}:{RABBIT_AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth_str}")
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            data = json.loads(res.read().decode())
            return {
                "name": data.get("name"),
                "messages": data.get("messages", 0),
                "messages_ready": data.get("messages_ready", 0),
                "messages_unacknowledged": data.get("messages_unacknowledged", 0)
            }
    except Exception as e:
        return {"error": str(e)}

def query_mongo_notif_count(event_id):
    cmd = [
        "docker", "exec", "seatlock-mongo", "mongosh", "notification_db",
        "-u", "notif_user", "-p", "notif_pass", "--quiet",
        "--eval", f'db.notification_logs.countDocuments({{ event_id: "{event_id}" }})'
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return int(res.stdout.strip().split("\n")[-1])
    except Exception:
        return -1

def publish_directly_to_rabbitmq(routing_key, payload):
    import base64
    publish_api = "http://localhost:15672/api/exchanges/%2F/seatlock.events/publish"
    req = urllib.request.Request(publish_api)
    auth_str = base64.b64encode(f"{RABBIT_AUTH[0]}:{RABBIT_AUTH[1]}".encode()).decode()
    req.add_header("Authorization", f"Basic {auth_str}")
    req.add_header("Content-Type", "application/json")
    
    body = {
        "properties": {
            "delivery_mode": 2, # Persistent
            "correlation_id": payload.get("correlation_id", "ch3d-offline")
        },
        "routing_key": routing_key,
        "payload": json.dumps(payload),
        "payload_encoding": "string"
    }
    data = json.dumps(body).encode()
    with urllib.request.urlopen(req, data=data, timeout=5) as res:
        return json.loads(res.read().decode())

def main():
    print("=" * 80)
    print("CHALLENGE 3D: EVENT-DRIVEN BROKER FLOW, DEDUPLICATION & OFFLINE CATCH-UP")
    print("=" * 80)

    evidence_records = {}

    # 1. Reset collections
    print("\n[SETUP] Resetting Notification collections in MongoDB...")
    http_post(f"{GATEWAY_NOTIF_URL}/reset", {})
    print("        Notification logs and processed events cleared.")

    # --------------------------------------------------------------------------
    # PART 1: CONSUMER-SIDE DEDUPLICATION (IDEMPOTENT CONSUMER)
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("PART 1: Consumer Idempotency & Duplicate Message Handling")
    print("-" * 80)

    duplicate_event_id = f"evt-dup-test-{int(time.time())}"
    dup_payload = {
        "event_id": duplicate_event_id,
        "booking_id": "book-tatkal-dup-99",
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "category": "RAILWAY_TATKAL",
        "pnr": "PNR-TATKAL-992211",
        "customer_phone": "+91-9988776655"
    }

    print(f"1. Publishing first instance of event: '{duplicate_event_id}'...")
    http_post(f"{GATEWAY_NOTIF_URL}/publish-test", dup_payload)
    time.sleep(1) # Allow consumer to process

    count1 = query_mongo_notif_count(duplicate_event_id)
    print(f"   MongoDB notification count after 1st message: {count1} (Expected: 1)")
    assert count1 == 1

    print(f"2. Publishing DUPLICATE message with identical event_id: '{duplicate_event_id}'...")
    http_post(f"{GATEWAY_NOTIF_URL}/publish-test", dup_payload)
    time.sleep(1)

    count2 = query_mongo_notif_count(duplicate_event_id)
    print(f"   MongoDB notification count after duplicate message: {count2} (Expected: exactly 1)")
    assert count2 == 1
    print("   -> PART 1 PASSED: Duplicate message safely discarded. Zero duplicate dispatches.")

    evidence_records["part_1_deduplication"] = {
        "event_id": duplicate_event_id,
        "first_delivery_count": count1,
        "second_delivery_count": count2,
        "result": "PASSED"
    }

    # --------------------------------------------------------------------------
    # PART 2: OFFLINE CONSUMER CATCH-UP
    # --------------------------------------------------------------------------
    print("\n" + "-" * 80)
    print("PART 2: Offline Consumer Catch-up Verification")
    print("-" * 80)

    print("1. Stopping notification-service container to simulate consumer outage...")
    subprocess.run(["docker", "compose", "stop", "notification-service"], check=True)
    time.sleep(2)
    print("   notification-service is now STOPPED (DOWN).")

    # Verify queue depth before publish
    q_state_before = get_rabbitmq_queue_depth()
    print(f"   Queue status before publish: {q_state_before['messages_ready']} messages waiting.")

    # Publish 3 distinct events while consumer is offline
    print("\n2. Publishing 3 booking events while consumer is OFFLINE...")
    offline_events = [
        {
            "event_id": f"evt-offline-01-{int(time.time())}",
            "booking_id": "book-offline-01",
            "pnr": "PNR-TATKAL-554433",
            "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
            "category": "RAILWAY_TATKAL",
            "customer_phone": "+91-9111111111"
        },
        {
            "event_id": f"evt-offline-02-{int(time.time())}",
            "booking_id": "book-offline-02",
            "pnr": "PNR-CONCERT-778899",
            "event_name": "Coldplay Music of the Spheres VIP",
            "category": "CONCERT_EVENT",
            "customer_phone": "+91-9222222222"
        },
        {
            "event_id": f"evt-offline-03-{int(time.time())}",
            "booking_id": "book-offline-03",
            "pnr": "PNR-BUS-990011",
            "event_name": "Intercity Volvo Luxury Sleeper",
            "category": "EXPRESS_BUS",
            "customer_phone": "+91-9333333333"
        }
    ]

    for ev in offline_events:
        res = publish_directly_to_rabbitmq("booking.confirmed", ev)
        print(f"   - Published event: '{ev['event_id']}' (PNR: {ev['pnr']}) -> RabbitMQ routed: {res.get('routed')}")

    time.sleep(1)

    # Verify messages are buffered in RabbitMQ (polling up to 10s for stats emitter)
    q_state_buffered = None
    for attempt in range(15):
        q_state_buffered = get_rabbitmq_queue_depth()
        if q_state_buffered.get("messages_ready") == 3:
            break
        time.sleep(1)

    print(f"\n3. RabbitMQ Management API Queue Depth Check:")
    print(f"   Queue Name                 : {q_state_buffered.get('name')}")
    print(f"   Messages Ready in Queue     : {q_state_buffered.get('messages_ready')} (Expected: 3)")
    print(f"   Messages Unacknowledged    : {q_state_buffered.get('messages_unacknowledged')}")
    assert q_state_buffered.get("messages_ready") == 3, f"Expected 3 buffered messages, got {q_state_buffered.get('messages_ready')}"

    # Restart consumer container
    print("\n4. Restarting notification-service container (Consumer recovering)...")
    subprocess.run(["docker", "compose", "start", "notification-service"], check=True)
    print("   Waiting 5 seconds for consumer to reconnect and drain the queue...")
    time.sleep(5)

    # Verify queue is drained (polling up to 10s)
    q_state_after = None
    for attempt in range(15):
        q_state_after = get_rabbitmq_queue_depth()
        if q_state_after.get("messages_ready") == 0:
            break
        time.sleep(1)

    print(f"\n5. RabbitMQ Management API Queue Depth Check Post-Recovery:")
    print(f"   Messages Ready in Queue     : {q_state_after.get('messages_ready')} (Expected: 0 - Drained)")
    assert q_state_after.get("messages_ready") == 0

    # Verify all 3 events are saved in MongoDB
    print("\n6. Verifying MongoDB delivery records for buffered events:")
    for ev in offline_events:
        c = query_mongo_notif_count(ev["event_id"])
        print(f"   - Event '{ev['event_id']}': Delivered Count = {c} (Expected: 1)")
        assert c == 1

    print("\n   -> PART 2 PASSED: 100% of offline buffered messages processed upon restart. Zero loss.")

    evidence_records["part_2_offline_catchup"] = {
        "buffered_messages": q_state_buffered.get("messages_ready"),
        "drained_messages": q_state_after.get("messages_ready"),
        "events_verified": [e["event_id"] for e in offline_events],
        "result": "PASSED"
    }

    # Save Evidence
    evidence_dir = os.path.join(os.path.dirname(__file__), "..", "evidence", "challenge-3-event-driven")
    os.makedirs(evidence_dir, exist_ok=True)
    with open(os.path.join(evidence_dir, "event_driven_run.log"), "w", encoding="utf-8") as f:
        f.write(json.dumps(evidence_records, indent=2))

    print("\n" + "=" * 80)
    print("CHALLENGE 3D EVIDENCE WRITTEN TO: evidence/challenge-3-event-driven/event_driven_run.log")
    print("ALL CHALLENGE 3D EVENT-DRIVEN TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
