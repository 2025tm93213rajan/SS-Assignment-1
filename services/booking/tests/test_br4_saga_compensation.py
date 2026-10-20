import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import Response, Request

orig_post = httpx.AsyncClient.post

@pytest.mark.asyncio
async def test_br4_happy_path_saga(client):
    """
    BR4 Happy Path:
    1. Reserve Inventory (201)
    2. Charge Payment (201)
    3. Issue Ticket & PNR (201)
    4. Publish AMQP Event
    Result: Booking CONFIRMED with PNR and all SUCCESS step logs.
    """
    async def mock_post(self, url, **kwargs):
        url_str = str(url)
        if "/api/v1/bookings" in url_str:
            return await orig_post(self, url, **kwargs)
        req = Request("POST", url)
        if "/api/v1/inventory/reserve" in url_str:
            return Response(201, json={"reservation_id": "res-test-happy-1", "quota_id": "TATKAL-12951-B1", "seats_held": 2}, request=req)
        elif "/api/v1/payments/charge" in url_str:
            return Response(201, json={"status": "CHARGED", "payment_id": "pay-test-happy-2", "amount": 5700.00}, request=req)
        elif "/api/v1/tickets/issue" in url_str:
            return Response(201, json={"status": "ISSUED", "pnr": "PNR-TATKAL-887766", "tickets": []}, request=req)
        return Response(404, request=req)

    payload = {
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "category": "RAILWAY_TATKAL",
        "passengers": [
            {"name": "Rajan Sharma", "berth_preference": "LOWER"},
            {"name": "Priya Sharma", "berth_preference": "MIDDLE"}
        ],
        "total_amount": 5700.00,
        "customer_name": "Rajan Sharma",
        "customer_email": "rajan@example.com",
        "customer_phone": "+91-9876543210"
    }

    with patch("httpx.AsyncClient.post", new=mock_post):
        with patch("src.amqp.event_publisher.publish", new=AsyncMock(return_value=True)):
            res = await client.post("/api/v1/bookings", json=payload)
            assert res.status_code == 201
            data = res.json()

            assert data["status"] == "CONFIRMED"
            assert data["pnr"] == "PNR-TATKAL-887766"
            assert data["reservation_id"] == "res-test-happy-1"
            assert data["payment_id"] == "pay-test-happy-2"
            assert len(data["steps"]) >= 4

            step_names = [s["step_name"] for s in data["steps"]]
            assert "INVENTORY_RESERVE" in step_names
            assert "PAYMENT_CHARGE" in step_names
            assert "TICKETING_ISSUE" in step_names
            assert "EVENT_PUBLISH" in step_names

@pytest.mark.asyncio
async def test_br4_payment_failure_triggers_compensating_inventory_release(client):
    """
    BR4 Compensating Rollback on Payment Failure:
    1. Reserve Inventory (201)
    2. Payment Charge Fails (402 Card Declined)
    -> Orchestrator automatically invokes POST /api/v1/inventory/release
    Result: Booking marked FAILED_COMPENSATED and held inventory returned.
    """
    compensation_called = False
    released_reservation_id = None

    async def mock_post(self, url, **kwargs):
        nonlocal compensation_called, released_reservation_id
        url_str = str(url)
        if "/api/v1/bookings" in url_str:
            return await orig_post(self, url, **kwargs)
        req = Request("POST", url)
        if "/api/v1/inventory/reserve" in url_str:
            return Response(201, json={"reservation_id": "res-hold-to-release", "seats_held": 1}, request=req)
        elif "/api/v1/payments/charge" in url_str:
            return Response(402, json={"status": "DECLINED", "message": "Card declined by issuing bank."}, request=req)
        elif "/api/v1/inventory/release" in url_str:
            compensation_called = True
            released_reservation_id = kwargs.get("json", {}).get("reservation_token") or kwargs.get("json", {}).get("reservation_id")
            return Response(200, json={"status": "RELEASED", "reservation_id": released_reservation_id}, request=req)
        return Response(404, request=req)

    payload = {
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "category": "RAILWAY_TATKAL",
        "passengers": [{"name": "Amit Patel", "berth_preference": "UPPER"}],
        "total_amount": 2850.00,
        "customer_name": "Amit Patel",
        "customer_email": "amit@example.com",
        "customer_phone": "+91-9988776655",
        "payment": {
            "card_number": "4000-0000-0000-0002", # Declined card
            "force_failure": False
        }
    }

    with patch("httpx.AsyncClient.post", new=mock_post):
        res = await client.post("/api/v1/bookings", json=payload)
        assert res.status_code == 402
        data = res.json()

        assert data["status"] == "FAILED"
        assert data["booking"]["status"] == "FAILED_COMPENSATED"
        assert "Payment declined" in data["booking"]["compensation_reason"]
        
        # Verify compensation was called
        assert compensation_called is True
        assert released_reservation_id == "res-hold-to-release"

        # Verify step logs show compensation
        steps = [s["step_name"] for s in data["booking"]["steps"]]
        assert "INVENTORY_RESERVE" in steps
        assert "PAYMENT_CHARGE" in steps
        assert "COMPENSATION_INVENTORY_RELEASE" in steps

@pytest.mark.asyncio
async def test_br4_ticketing_failure_triggers_compensation(client):
    """
    BR4 Compensating Rollback on Ticketing Failure:
    1. Reserve Inventory (201)
    2. Payment Charge (201)
    3. Ticketing Issue Fails (500 Internal Error)
    -> Orchestrator automatically releases inventory.
    Result: Booking marked FAILED_COMPENSATED.
    """
    compensation_called = False

    async def mock_post(self, url, **kwargs):
        nonlocal compensation_called
        url_str = str(url)
        if "/api/v1/bookings" in url_str:
            return await orig_post(self, url, **kwargs)
        req = Request("POST", url)
        if "/api/v1/inventory/reserve" in url_str:
            return Response(201, json={"reservation_id": "res-hold-for-tkt-fail"}, request=req)
        elif "/api/v1/payments/charge" in url_str:
            return Response(201, json={"status": "CHARGED", "payment_id": "pay-ok-123"}, request=req)
        elif "/api/v1/tickets/issue" in url_str:
            return Response(500, json={"message": "Ticketing fulfillment database timeout."}, request=req)
        elif "/api/v1/inventory/release" in url_str:
            compensation_called = True
            return Response(200, json={"status": "RELEASED"}, request=req)
        return Response(404, request=req)

    payload = {
        "quota_id": "CONCERT-COLDPLAY-VIP",
        "event_name": "Coldplay Music of the Spheres VIP",
        "category": "CONCERT_EVENT",
        "passengers": [{"name": "Neha Gupta"}],
        "total_amount": 12500.00,
        "customer_name": "Neha Gupta",
        "customer_email": "neha@example.com",
        "customer_phone": "+91-9123456780"
    }

    with patch("httpx.AsyncClient.post", new=mock_post):
        res = await client.post("/api/v1/bookings", json=payload)
        assert res.status_code == 500
        data = res.json()

        assert data["booking"]["status"] == "FAILED_COMPENSATED"
        assert compensation_called is True

@pytest.mark.asyncio
async def test_br4_inventory_exhausted_rejects_without_payment(client):
    """
    BR4 Zero Over-Allocation (BR1 Pre-condition):
    When inventory is sold out (409 Conflict), the Saga halts immediately at Step 1.
    Payment and Ticketing steps are NEVER executed.
    """
    payment_called = False

    async def mock_post(self, url, **kwargs):
        nonlocal payment_called
        url_str = str(url)
        if "/api/v1/bookings" in url_str:
            return await orig_post(self, url, **kwargs)
        req = Request("POST", url)
        if "/api/v1/inventory/reserve" in url_str:
            return Response(409, json={"code": "INSUFFICIENT_INVENTORY", "message": "Only 0 seats available."}, request=req)
        elif "/api/v1/payments/charge" in url_str:
            payment_called = True
            return Response(201, json={}, request=req)
        return Response(404, request=req)

    payload = {
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "passengers": [{"name": "Late Passenger"}],
        "total_amount": 2850.00,
        "customer_name": "Late Passenger",
        "customer_email": "late@example.com",
        "customer_phone": "+91-9000000000"
    }

    with patch("httpx.AsyncClient.post", new=mock_post):
        res = await client.post("/api/v1/bookings", json=payload)
        assert res.status_code == 409
        data = res.json()

        assert data["booking"]["status"] == "FAILED_INVENTORY"
        assert payment_called is False
