import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_br1_successful_reservation(client: AsyncClient):
    """
    BR1 Happy Path:
    Reserving seats within available capacity succeeds with HTTP 201
    and decrements remaining available seats.
    """
    response = await client.post(
        "/api/v1/inventory/reserve",
        json={"quota_id": "TATKAL-12951-B1", "quantity": 2}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "RESERVED"
    assert data["quantity"] == 2
    assert data["remaining_available"] == 3
    assert "reservation_token" in data

@pytest.mark.asyncio
async def test_br1_zero_overallocation_prevention(client: AsyncClient):
    """
    BR1 Violation Prevention:
    When requested quantity exceeds available capacity, request is immediately
    rejected with HTTP 409 Conflict, preserving business data integrity.
    """
    # 1. Exhaust all 5 seats
    res1 = await client.post(
        "/api/v1/inventory/reserve",
        json={"quota_id": "TATKAL-12951-B1", "quantity": 5}
    )
    assert res1.status_code == 201
    assert res1.json()["remaining_available"] == 0

    # 2. Attempt to book 1 more seat when capacity is 0
    res2 = await client.post(
        "/api/v1/inventory/reserve",
        json={"quota_id": "TATKAL-12951-B1", "quantity": 1}
    )
    assert res2.status_code == 409
    err = res2.json()
    assert err["code"] == "INSUFFICIENT_INVENTORY"
    assert err["details"]["available"] == 0
    assert err["details"]["requested"] == 1

@pytest.mark.asyncio
async def test_br1_cannot_reserve_more_than_initial_capacity(client: AsyncClient):
    """
    BR1 Initial Bound:
    Requesting 6 seats on a quota with capacity 5 is immediately rejected.
    """
    res = await client.post(
        "/api/v1/inventory/reserve",
        json={"quota_id": "TATKAL-12951-B1", "quantity": 6}
    )
    assert res.status_code == 409
    err = res.json()
    assert err["code"] == "INSUFFICIENT_INVENTORY"
    assert err["details"]["available"] == 5
    assert err["details"]["requested"] == 6
