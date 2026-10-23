"""Front-desk tools for The Saffron Palm Hotel. Each @tool becomes a Live API function."""

import asyncio
import json
import logging
import random
import re
from datetime import date
from pathlib import Path
from typing import Literal

from app.config import today
from app.store import store
from app.tools.registry import ToolError, tool

log = logging.getLogger(__name__)

HOTEL = json.loads((Path(__file__).parent.parent / "data" / "hotel.json").read_text(encoding="utf-8"))
ROOMS: dict[str, dict] = HOTEL["rooms"]

Topic = Literal["check_in_out", "breakfast", "pool", "spa", "wifi", "parking", "airport_transfer", "metro"]
Service = Literal["housekeeping", "room_service", "maintenance", "wake_up_call"]


def parse_stay(check_in: str, check_out: str) -> tuple[date, date]:
    """Validate ISO dates: real dates, not in the past, check-out after check-in."""
    try:
        start, end = date.fromisoformat(check_in), date.fromisoformat(check_out)
    except ValueError:
        raise ToolError("Please give dates as YYYY-MM-DD, for example 2026-10-23.") from None
    if start < today():
        raise ToolError("That check-in date is in the past.")
    if end <= start:
        raise ToolError("Check-out has to be at least one night after check-in.")
    return start, end


def find_room(room_type: str) -> str:
    """Resolve a spoken room name or alias, e.g. 'double', to a room type key."""
    wanted = room_type.strip().lower()
    for name, room in ROOMS.items():
        if wanted == name or wanted in room["aliases"]:
            return name
    raise ToolError(f"We don't have a '{room_type}' room. We offer: {', '.join(ROOMS)}.")


def rooms_left(room_type: str, start: date, end: date) -> int:
    """Inventory minus bookings that overlap the requested nights."""
    taken = sum(
        1
        for b in store.all("bookings")
        if b["room_type"] == room_type
        and date.fromisoformat(b["check_in"]) < end
        and start < date.fromisoformat(b["check_out"])
    )
    return ROOMS[room_type]["inventory"] - taken


@tool(blocking=False)
async def check_availability(check_in: str, check_out: str, guests: int, room_type: str | None = None) -> dict:
    """Check which rooms are free for a stay and what they cost.

    Args:
        check_in: Arrival date, ISO format YYYY-MM-DD.
        check_out: Departure date, ISO format YYYY-MM-DD.
        guests: Number of guests staying in one room.
        room_type: Optional room type the guest asked for, e.g. "double" or "family suite".
    """
    await asyncio.sleep(2)  # Simulate a slow booking system so async calling is visible.
    start, end = parse_stay(check_in, check_out)
    nights = (end - start).days
    names = [find_room(room_type)] if room_type else list(ROOMS)
    options = [
        {"room_type": n, "nightly_rate_aed": ROOMS[n]["rate"], "total_aed": ROOMS[n]["rate"] * nights}
        for n in names
        if ROOMS[n]["capacity"] >= guests and rooms_left(n, start, end) > 0
    ]
    return {"nights": nights, "available": options} if options else {"available": [], "message": "Nothing matches those dates and guests."}


@tool
def make_reservation(guest_name: str, room_type: str, check_in: str, check_out: str, guests: int, phone: str) -> dict:
    """Book a room. Only call this after reading the details back and the guest confirming.

    Args:
        guest_name: Full name of the guest.
        room_type: Room type, e.g. "standard double".
        check_in: Arrival date, ISO format YYYY-MM-DD.
        check_out: Departure date, ISO format YYYY-MM-DD.
        guests: Number of guests.
        phone: Contact phone number.
    """
    if not guest_name.strip():
        raise ToolError("I need the guest's name for the booking.")
    if len(re.sub(r"\D", "", phone)) < 7:
        raise ToolError("That phone number looks too short. Could you repeat it?")
    start, end = parse_stay(check_in, check_out)
    room = find_room(room_type)
    if guests > ROOMS[room]["capacity"]:
        raise ToolError(f"The {room} sleeps at most {ROOMS[room]['capacity']} guests.")
    if rooms_left(room, start, end) <= 0:
        raise ToolError(f"Sorry, the {room} is fully booked for those dates.")
    booking = store.add("bookings", {
        "code": f"SPH-{random.randint(1000, 9999)}",
        "guest_name": guest_name.strip(),
        "room_type": room,
        "check_in": check_in,
        "check_out": check_out,
        "guests": guests,
        "phone": phone,
        "total_aed": ROOMS[room]["rate"] * (end - start).days,
    })
    return {**booking, "payment": "Payment is taken at check-in."}


@tool
def get_hotel_info(topic: Topic) -> dict:
    """Look up hotel facts: check-in and check-out times, breakfast, pool, spa, wifi, parking, airport transfer or the nearest Metro.

    Args:
        topic: The subject the guest asked about.
    """
    if topic not in HOTEL["info"]:
        raise ToolError(f"I can help with: {', '.join(HOTEL['info'])}.")
    return {"info": HOTEL["info"][topic]}


@tool
def request_service(room_number: str, service_type: Service, details: str) -> dict:
    """Log a request for an in-house guest: housekeeping, room service, maintenance or a wake-up call.

    Args:
        room_number: Guest's room number, e.g. "1204" (floor 12, room 04).
        service_type: Kind of service requested.
        details: What exactly is needed, e.g. "two extra towels" or "wake-up at 6:30".
    """
    floor, room = divmod(int(room_number), 100) if room_number.isdigit() else (0, 0)
    if not (1 <= floor <= HOTEL["floors"] and 1 <= room <= HOTEL["rooms_per_floor"]):
        raise ToolError(f"Room {room_number} doesn't exist. Room numbers look like 1204.")
    request = store.add("requests", {
        "ticket": f"REQ-{random.randint(1000, 9999)}",
        "room_number": room_number,
        "service_type": service_type,
        "details": details,
    })
    return {**request, "eta_minutes": 20}


@tool
def transfer_to_human(reason: str) -> dict:
    """Log a callback from a human colleague, after offering one for something you can't answer.

    Args:
        reason: Short summary of what the guest needs.
    """
    log.info("Handoff to human: %s", reason)
    store.add("handoffs", {"reason": reason})
    return {"status": "Callback request logged. You already told the guest; just continue the conversation."}
