import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_issue_pnr_and_berths_success(client: AsyncClient):
    """
    Happy Path:
    Issues unique PNR and allocates specific berths with cryptographic barcodes.
    """
    payload = {
        "booking_id": "book-test-pnr-01",
        "quota_id": "TATKAL-12951-B1",
        "event_name": "Mumbai Tejas Rajdhani Express (#12951)",
        "passengers": [
            {"name": "Rajan Sharma", "berth_preference": "LOWER"},
            {"name": "Priya Sharma", "berth_preference": "MIDDLE"}
        ],
        "category": "RAILWAY_TATKAL"
    }

    res = await client.post("/api/v1/tickets/issue", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "ISSUED"
    assert data["pnr"].startswith("PNR-TATKAL-")
    assert len(data["tickets"]) == 2

    names = {t["passenger_name"] for t in data["tickets"]}
    assert names == {"Rajan Sharma", "Priya Sharma"}
    for t in data["tickets"]:
        assert t["berth_number"].startswith("B1-")
        assert len(t["barcode_token"]) == 24

@pytest.mark.asyncio
async def test_pnr_fulfillment_idempotent_reissue(client: AsyncClient):
    """
    Idempotent Fulfillment:
    Calling issue again with the exact same booking_id returns the existing PNR without re-allocating berths.
    """
    payload = {
        "booking_id": "book-test-idem-02",
        "quota_id": "COLDPLAY-VIP-A1",
        "event_name": "Coldplay Music of the Spheres",
        "passengers": [{"name": "Chris Martin", "berth_preference": "VIP_ARENA"}]
    }

    res1 = await client.post("/api/v1/tickets/issue", json=payload)
    assert res1.status_code == 201
    pnr1 = res1.json()["pnr"]

    # Re-issue with same booking_id
    res2 = await client.post("/api/v1/tickets/issue", json=payload)
    assert res2.status_code == 201
    pnr2 = res2.json()["pnr"]

    assert pnr1 == pnr2, "Expected identical PNR for duplicate booking fulfillment call"

@pytest.mark.asyncio
async def test_compensating_cancellation(client: AsyncClient):
    """
    Compensating Transaction:
    Cancels issued PNR upon upstream saga failure.
    """
    # 1. Issue PNR
    issue_res = await client.post(
        "/api/v1/tickets/issue",
        json={
            "booking_id": "book-test-cancel-03",
            "quota_id": "VOLVO-EXP-99",
            "event_name": "Intercity Volvo Sleeper",
            "passengers": [{"name": "Test Passenger", "berth_preference": "WINDOW"}]
        }
    )
    pnr = issue_res.json()["pnr"]

    # 2. Cancel PNR
    cancel_res = await client.post("/api/v1/tickets/cancel", json={"pnr": pnr})
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "CANCELLED"

    # 3. Verify status in lookup
    lookup_res = await client.get(f"/api/v1/tickets/pnr/{pnr}")
    assert lookup_res.status_code == 200
    assert lookup_res.json()["status"] == "CANCELLED"
