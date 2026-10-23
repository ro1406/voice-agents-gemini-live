from datetime import date

import pytest

from app.store import Store
from app.tools import call, hotel
from app.tools.registry import ToolError, ToolRegistry

TODAY = date(2026, 10, 18)


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    """Fixed date, empty store on disk in tmp, and no 2 s delay."""
    monkeypatch.setattr(hotel, "today", lambda: TODAY)
    monkeypatch.setattr(hotel, "store", Store(tmp_path / "bookings.json"))

    async def no_sleep(_):
        return None

    monkeypatch.setattr(hotel.asyncio, "sleep", no_sleep)


def book(**overrides) -> dict:
    details = dict(guest_name="Omar Al Mansoori", room_type="double", check_in="2026-10-23",
                   check_out="2026-10-24", guests=2, phone="+971 50 123 4567")
    return hotel.make_reservation(**{**details, **overrides})


async def test_check_availability_lists_matching_rooms():
    result = await hotel.check_availability("2026-10-23", "2026-10-25", 2, "double")
    assert result == {"nights": 2, "available": [
        {"room_type": "standard double", "nightly_rate_aed": 650, "total_aed": 1300}]}


async def test_check_availability_filters_by_capacity():
    result = await hotel.check_availability("2026-10-23", "2026-10-24", 4)
    assert [r["room_type"] for r in result["available"]] == ["family suite"]


@pytest.mark.parametrize("check_in, check_out, error", [
    ("23/10/2026", "2026-10-24", "YYYY-MM-DD"),
    ("2026-10-01", "2026-10-02", "in the past"),
    ("2026-10-24", "2026-10-23", "at least one night"),
    ("2026-10-24", "2026-10-24", "at least one night"),
])
async def test_check_availability_rejects_bad_dates(check_in, check_out, error):
    with pytest.raises(ToolError, match=error):
        await hotel.check_availability(check_in, check_out, 2)


async def test_check_availability_rejects_unknown_room():
    with pytest.raises(ToolError, match="We offer: standard double"):
        await hotel.check_availability("2026-10-23", "2026-10-24", 2, "treehouse")


async def test_sold_out_after_inventory_is_booked():
    for _ in range(2):
        book(room_type="family suite")
    result = await hotel.check_availability("2026-10-23", "2026-10-24", 2, "suite")
    assert result["available"] == []
    with pytest.raises(ToolError, match="fully booked"):
        book(room_type="family suite")


def test_make_reservation_saves_booking():
    booking = book()
    assert booking["code"].startswith("SPH-") and len(booking["code"]) == 8
    assert booking["room_type"] == "standard double"
    assert booking["total_aed"] == 650
    assert "check-in" in booking["payment"]
    assert hotel.store.all("bookings")[0]["code"] == booking["code"]


@pytest.mark.parametrize("overrides, error", [
    ({"guest_name": "  "}, "name"),
    ({"phone": "123"}, "phone number"),
    ({"guests": 3}, "at most 2 guests"),
    ({"room_type": "igloo"}, "don't have"),
    ({"check_out": "2026-10-22"}, "at least one night"),
])
def test_make_reservation_validation(overrides, error):
    with pytest.raises(ToolError, match=error):
        book(**overrides)


def test_get_hotel_info():
    assert "3 PM" in hotel.get_hotel_info("check_in_out")["info"]
    with pytest.raises(ToolError, match="I can help with"):
        hotel.get_hotel_info("casino")


def test_request_service():
    request = hotel.request_service("1204", "housekeeping", "two extra towels")
    assert request["ticket"].startswith("REQ-") and request["eta_minutes"] == 20
    assert hotel.store.all("requests")[0]["details"] == "two extra towels"


@pytest.mark.parametrize("room", ["9999", "1299", "12a", "0005"])
def test_request_service_rejects_unknown_room(room):
    with pytest.raises(ToolError, match="doesn't exist"):
        hotel.request_service(room, "maintenance", "AC is noisy")


def test_transfer_to_human():
    assert "Callback request logged" in hotel.transfer_to_human("billing dispute")["status"]
    assert hotel.store.all("handoffs") == [{"reason": "billing dispute"}]


def test_end_call_is_registered_and_returns_status():
    assert call.end_call() == {"status": "Call ended."}
    assert "end_call" in ToolRegistry(("app.tools.hotel", "app.tools.call")).tools
