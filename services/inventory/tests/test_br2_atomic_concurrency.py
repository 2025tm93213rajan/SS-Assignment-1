import pytest
import asyncio
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_br2_atomic_concurrency_20_requests_for_5_capacity(client: AsyncClient):
    """
    BR2 Atomic Concurrency Protection (Challenge 1 Core Requirement):
    Fires 20 simultaneous parallel requests for a resource with capacity 5.
    Exactly 5 must succeed (HTTP 201) and exactly 15 must be rejected (HTTP 409).
    Final database state must show available = 0, proving zero race condition.
    """
    quota_id = "COLDPLAY-VIP-A1"  # Capacity = 5

    async def send_reservation(req_idx: int):
        return await client.post(
            "/api/v1/inventory/reserve",
            json={"quota_id": quota_id, "quantity": 1, "booking_id": f"test-book-{req_idx}"},
            headers={"X-Correlation-ID": f"concurrency-test-{req_idx}"}
        )

    # Dispatch 20 requests concurrently at the exact same moment
    tasks = [send_reservation(i) for i in range(20)]
    responses = await asyncio.gather(*tasks)

    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)

    print(f"\n[BR2 Concurrency Test Result] Total: 20 | Succeeded (201): {success_count} | Rejected (409): {conflict_count}")

    # Core Assertions:
    assert success_count == 5, f"Expected exactly 5 successes, but got {success_count}"
    assert conflict_count == 15, f"Expected exactly 15 conflicts, but got {conflict_count}"

    # Verify final database state via GET quota
    quota_res = await client.get(f"/api/v1/inventory/quotas/{quota_id}")
    assert quota_res.status_code == 200
    quota_data = quota_res.json()

    assert quota_data["available_seats"] == 0, f"Expected 0 available seats, got {quota_data['available_seats']}"
    assert quota_data["locked_seats"] == 5, f"Expected 5 locked seats, got {quota_data['locked_seats']}"
