# Hotel Booking MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a hotel-booking MCP server in `test_booking_mcp/` that exposes 5 tools (`search_hotels`, `check_availability`, `book_room`, `cancel_booking`, `list_bookings`) over streamable HTTP at `/mcp`, backed by in-memory mock data.

**Architecture:** A `fastmcp.FastMCP` instance registers thin tool wrappers that delegate to pure, independently-testable functions in `logic.py`, which operate on in-memory data/state in `models.py`. `mcp.http_app(path="/mcp")` is mounted into a `FastAPI` app (with FastAPI's lifespan wired to the MCP app's lifespan) and served with uvicorn.

**Tech Stack:** Python 3.14, `fastmcp` 3.4.6, `fastapi` 0.139.2, `uvicorn` 0.51.0, `pytest` + `pytest-asyncio` for tests. Reuses the repo's existing `./env` virtualenv — no new venv.

## Global Constraints

- Server lives entirely under `test_booking_mcp/` (spec's chosen directory — an empty placeholder dir already exists).
- No authentication, no `.env` file, no external database — in-memory mock data only, reset on process restart.
- MCP endpoint must be reachable at path `/mcp` via streamable-HTTP transport.
- Dates are `YYYY-MM-DD` strings; a `check_out <= check_in` request must raise a clear error, as must an unknown `hotel_id`/`room_type`, booking with no availability, or cancelling a nonexistent/already-cancelled booking.
- Reuse the repo's `./env` venv (`./env/bin/python`, `./env/bin/pip`) for all installs and test runs — do not create a new venv.

---

## File Structure

- `test_booking_mcp/models.py` — mock hotel data (`Hotel`, `RoomType` dataclasses, `HOTELS` list), booking storage (`Booking` dataclass, `BOOKINGS` dict, `next_booking_id()`), and a `reset_state()` test helper.
- `test_booking_mcp/logic.py` — pure business-logic functions (`search_hotels`, `check_availability`, `book_room`, `cancel_booking`, `list_bookings`) plus private validation/lookup helpers. No FastMCP/FastAPI imports here — this file is unit-testable in isolation.
- `test_booking_mcp/server.py` — FastMCP tool registration (thin wrappers around `logic.py`), FastAPI app + mount, uvicorn entrypoint.
- `test_booking_mcp/conftest.py` — puts `test_booking_mcp/` on `sys.path` so plain `import models` / `import logic` / `import server` work from `tests/`; autouse fixture resets in-memory state between tests.
- `test_booking_mcp/pytest.ini` — `asyncio_mode = auto` so async test functions run without extra decorators.
- `test_booking_mcp/tests/test_models.py`, `test_logic.py`, `test_server.py`, `test_http_integration.py` — the test suite.
- `test_booking_mcp/requirements.txt` — `fastmcp==3.4.6`, `fastapi==0.139.2`, `uvicorn==0.51.0`, `pytest`, `pytest-asyncio`.

---

### Task 1: Project scaffolding and data models

**Files:**
- Create: `test_booking_mcp/requirements.txt`
- Create: `test_booking_mcp/pytest.ini`
- Create: `test_booking_mcp/conftest.py`
- Create: `test_booking_mcp/models.py`
- Test: `test_booking_mcp/tests/test_models.py`

**Interfaces:**
- Produces (used by Task 2+): `models.Hotel(id: str, name: str, city: str, room_types: list[RoomType])`, `models.RoomType(name: str, price_per_night: float, total_rooms: int)`, `models.Booking(id: str, hotel_id: str, room_type: str, guest_name: str, check_in: str, check_out: str, status: str)`, `models.HOTELS: list[Hotel]`, `models.BOOKINGS: dict[str, Booking]`, `models.next_booking_id() -> str`, `models.reset_state() -> None`.

- [ ] **Step 1: Scaffold the project directory and install test dependencies**

```bash
mkdir -p test_booking_mcp/tests
touch test_booking_mcp/tests/__init__.py
./env/bin/pip install pytest pytest-asyncio
```

- [ ] **Step 2: Write `requirements.txt` and `pytest.ini`**

`test_booking_mcp/requirements.txt`:
```
fastmcp==3.4.6
fastapi==0.139.2
uvicorn==0.51.0
pytest
pytest-asyncio
```

`test_booking_mcp/pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 3: Write `conftest.py`**

`test_booking_mcp/conftest.py`:
```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest

import models


@pytest.fixture(autouse=True)
def _reset_bookings():
    models.reset_state()
    yield
    models.reset_state()
```

- [ ] **Step 4: Write the failing test for models**

`test_booking_mcp/tests/test_models.py`:
```python
import models


def test_hotels_have_positive_room_types():
    assert len(models.HOTELS) >= 4
    for hotel in models.HOTELS:
        assert hotel.id and hotel.name and hotel.city
        assert hotel.room_types
        for rt in hotel.room_types:
            assert rt.total_rooms > 0
            assert rt.price_per_night > 0


def test_hotel_ids_are_unique():
    ids = [h.id for h in models.HOTELS]
    assert len(ids) == len(set(ids))


def test_next_booking_id_increments():
    first = models.next_booking_id()
    second = models.next_booking_id()
    assert first == "b1"
    assert second == "b2"


def test_reset_state_clears_bookings_and_counter():
    models.BOOKINGS["b1"] = models.Booking(
        id="b1",
        hotel_id="h1",
        room_type="Standard",
        guest_name="Alice",
        check_in="2026-09-01",
        check_out="2026-09-03",
        status="confirmed",
    )
    models.next_booking_id()

    models.reset_state()

    assert models.BOOKINGS == {}
    assert models.next_booking_id() == "b1"
```

- [ ] **Step 5: Run the test to verify it fails**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models'` (the file doesn't exist yet).

- [ ] **Step 6: Write `models.py`**

`test_booking_mcp/models.py`:
```python
from dataclasses import dataclass
from itertools import count


@dataclass(frozen=True)
class RoomType:
    name: str
    price_per_night: float
    total_rooms: int


@dataclass(frozen=True)
class Hotel:
    id: str
    name: str
    city: str
    room_types: list[RoomType]


@dataclass
class Booking:
    id: str
    hotel_id: str
    room_type: str
    guest_name: str
    check_in: str
    check_out: str
    status: str


HOTELS: list[Hotel] = [
    Hotel(
        id="h1",
        name="Grand Central Hotel",
        city="New York",
        room_types=[
            RoomType(name="Standard", price_per_night=150.0, total_rooms=10),
            RoomType(name="Deluxe", price_per_night=250.0, total_rooms=5),
        ],
    ),
    Hotel(
        id="h2",
        name="Bay View Inn",
        city="San Francisco",
        room_types=[
            RoomType(name="Standard", price_per_night=180.0, total_rooms=8),
            RoomType(name="Suite", price_per_night=320.0, total_rooms=3),
        ],
    ),
    Hotel(
        id="h3",
        name="Lakeside Lodge",
        city="Chicago",
        room_types=[
            RoomType(name="Standard", price_per_night=120.0, total_rooms=12),
        ],
    ),
    Hotel(
        id="h4",
        name="Sunset Resort",
        city="Los Angeles",
        room_types=[
            RoomType(name="Standard", price_per_night=200.0, total_rooms=6),
            RoomType(name="Deluxe", price_per_night=300.0, total_rooms=4),
            RoomType(name="Suite", price_per_night=450.0, total_rooms=2),
        ],
    ),
]

BOOKINGS: dict[str, Booking] = {}
_booking_id_counter = count(1)


def next_booking_id() -> str:
    return f"b{next(_booking_id_counter)}"


def reset_state() -> None:
    """Test helper: clear bookings and reset the id counter to b1."""
    global _booking_id_counter
    BOOKINGS.clear()
    _booking_id_counter = count(1)
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 8: Commit**

```bash
git add test_booking_mcp/requirements.txt test_booking_mcp/pytest.ini test_booking_mcp/conftest.py test_booking_mcp/models.py test_booking_mcp/tests/__init__.py test_booking_mcp/tests/test_models.py
git commit -m "feat: add hotel booking mock data models"
```

---

### Task 2: Search and availability logic

**Files:**
- Create: `test_booking_mcp/logic.py`
- Test: `test_booking_mcp/tests/test_logic.py`

**Interfaces:**
- Consumes: `models.HOTELS`, `models.Hotel`, `models.RoomType`, `models.BOOKINGS`, `models.Booking` (from Task 1).
- Produces (used by Task 3 and Task 4): `logic.search_hotels(city: str | None = None) -> list[dict]`, `logic.check_availability(hotel_id: str, room_type: str, check_in: str, check_out: str) -> dict`. Also produces internal helpers reused by Task 3: `logic._parse_date(value: str, field_name: str) -> date`, `logic._validate_date_range(check_in: str, check_out: str) -> tuple[date, date]`, `logic._find_hotel(hotel_id: str) -> models.Hotel`, `logic._find_room_type(hotel: models.Hotel, room_type: str) -> models.RoomType`, `logic._rooms_booked(hotel_id: str, room_type: str, check_in: date, check_out: date) -> int`. All raise `ValueError` with a descriptive message on invalid input.

- [ ] **Step 1: Write the failing tests**

`test_booking_mcp/tests/test_logic.py`:
```python
import pytest

import logic
import models


def test_search_hotels_returns_all_by_default():
    results = logic.search_hotels()
    assert len(results) == len(models.HOTELS)
    assert {"id", "name", "city", "room_types"} <= results[0].keys()


def test_search_hotels_filters_by_city_case_insensitive():
    results = logic.search_hotels(city="chicago")
    assert len(results) == 1
    assert results[0]["city"] == "Chicago"


def test_search_hotels_unknown_city_returns_empty():
    assert logic.search_hotels(city="Nowhere") == []


def test_check_availability_full_when_no_bookings():
    result = logic.check_availability(
        hotel_id="h3", room_type="Standard", check_in="2026-09-01", check_out="2026-09-03"
    )
    assert result["available_rooms"] == 12
    assert result["is_available"] is True


def test_check_availability_unknown_hotel_raises():
    with pytest.raises(ValueError, match="Unknown hotel_id"):
        logic.check_availability(
            hotel_id="nope", room_type="Standard", check_in="2026-09-01", check_out="2026-09-03"
        )


def test_check_availability_unknown_room_type_raises():
    with pytest.raises(ValueError, match="Unknown room_type"):
        logic.check_availability(
            hotel_id="h3", room_type="Penthouse", check_in="2026-09-01", check_out="2026-09-03"
        )


def test_check_availability_invalid_date_raises():
    with pytest.raises(ValueError, match="Invalid 'check_in'"):
        logic.check_availability(
            hotel_id="h3", room_type="Standard", check_in="not-a-date", check_out="2026-09-03"
        )


def test_check_availability_checkout_before_checkin_raises():
    with pytest.raises(ValueError, match="must be after"):
        logic.check_availability(
            hotel_id="h3", room_type="Standard", check_in="2026-09-05", check_out="2026-09-01"
        )


def test_check_availability_accounts_for_existing_confirmed_bookings():
    models.BOOKINGS["b1"] = models.Booking(
        id="b1",
        hotel_id="h3",
        room_type="Standard",
        guest_name="Alice",
        check_in="2026-09-01",
        check_out="2026-09-05",
        status="confirmed",
    )
    result = logic.check_availability(
        hotel_id="h3", room_type="Standard", check_in="2026-09-02", check_out="2026-09-03"
    )
    assert result["available_rooms"] == 11


def test_check_availability_ignores_cancelled_bookings():
    models.BOOKINGS["b1"] = models.Booking(
        id="b1",
        hotel_id="h3",
        room_type="Standard",
        guest_name="Alice",
        check_in="2026-09-01",
        check_out="2026-09-05",
        status="cancelled",
    )
    result = logic.check_availability(
        hotel_id="h3", room_type="Standard", check_in="2026-09-02", check_out="2026-09-03"
    )
    assert result["available_rooms"] == 12


def test_check_availability_ignores_non_overlapping_bookings():
    models.BOOKINGS["b1"] = models.Booking(
        id="b1",
        hotel_id="h3",
        room_type="Standard",
        guest_name="Alice",
        check_in="2026-09-01",
        check_out="2026-09-02",
        status="confirmed",
    )
    result = logic.check_availability(
        hotel_id="h3", room_type="Standard", check_in="2026-09-02", check_out="2026-09-03"
    )
    assert result["available_rooms"] == 12
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_logic.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'logic'`.

- [ ] **Step 3: Write `logic.py` (search and availability portion)**

`test_booking_mcp/logic.py`:
```python
from datetime import date

import models


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field_name!r}: {value!r} is not a valid YYYY-MM-DD date")


def _validate_date_range(check_in: str, check_out: str) -> tuple[date, date]:
    check_in_date = _parse_date(check_in, "check_in")
    check_out_date = _parse_date(check_out, "check_out")
    if check_out_date <= check_in_date:
        raise ValueError(f"check_out ({check_out}) must be after check_in ({check_in})")
    return check_in_date, check_out_date


def _find_hotel(hotel_id: str) -> models.Hotel:
    for hotel in models.HOTELS:
        if hotel.id == hotel_id:
            return hotel
    raise ValueError(f"Unknown hotel_id: {hotel_id!r}")


def _find_room_type(hotel: models.Hotel, room_type: str) -> models.RoomType:
    for rt in hotel.room_types:
        if rt.name.lower() == room_type.lower():
            return rt
    raise ValueError(f"Unknown room_type {room_type!r} for hotel {hotel.id!r}")


def _dates_overlap(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start < b_end and b_start < a_end


def _rooms_booked(hotel_id: str, room_type: str, check_in: date, check_out: date) -> int:
    booked = 0
    for booking in models.BOOKINGS.values():
        if booking.status != "confirmed":
            continue
        if booking.hotel_id != hotel_id or booking.room_type.lower() != room_type.lower():
            continue
        b_start = date.fromisoformat(booking.check_in)
        b_end = date.fromisoformat(booking.check_out)
        if _dates_overlap(check_in, check_out, b_start, b_end):
            booked += 1
    return booked


def search_hotels(city: str | None = None) -> list[dict]:
    hotels = models.HOTELS
    if city:
        hotels = [h for h in hotels if h.city.lower() == city.lower()]
    return [
        {
            "id": h.id,
            "name": h.name,
            "city": h.city,
            "room_types": [
                {
                    "name": rt.name,
                    "price_per_night": rt.price_per_night,
                    "total_rooms": rt.total_rooms,
                }
                for rt in h.room_types
            ],
        }
        for h in hotels
    ]


def check_availability(hotel_id: str, room_type: str, check_in: str, check_out: str) -> dict:
    hotel = _find_hotel(hotel_id)
    rt = _find_room_type(hotel, room_type)
    check_in_date, check_out_date = _validate_date_range(check_in, check_out)
    booked = _rooms_booked(hotel_id, rt.name, check_in_date, check_out_date)
    available = rt.total_rooms - booked
    return {
        "hotel_id": hotel_id,
        "room_type": rt.name,
        "check_in": check_in,
        "check_out": check_out,
        "available_rooms": available,
        "is_available": available > 0,
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_logic.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add test_booking_mcp/logic.py test_booking_mcp/tests/test_logic.py
git commit -m "feat: add hotel search and availability logic"
```

---

### Task 3: Booking mutation logic

**Files:**
- Modify: `test_booking_mcp/logic.py` (append)
- Modify: `test_booking_mcp/tests/test_logic.py` (append)

**Interfaces:**
- Consumes: `logic._find_hotel`, `logic._find_room_type`, `logic._validate_date_range`, `logic._rooms_booked` (Task 2); `models.BOOKINGS`, `models.Booking`, `models.next_booking_id()` (Task 1).
- Produces (used by Task 4): `logic.book_room(hotel_id: str, room_type: str, guest_name: str, check_in: str, check_out: str) -> dict`, `logic.cancel_booking(booking_id: str) -> dict`, `logic.list_bookings(guest_name: str | None = None) -> list[dict]`.

- [ ] **Step 1: Append the failing tests**

Append to `test_booking_mcp/tests/test_logic.py`:
```python
def test_book_room_success_returns_confirmation():
    result = logic.book_room(
        hotel_id="h3",
        room_type="Standard",
        guest_name="Bob",
        check_in="2026-09-01",
        check_out="2026-09-03",
    )
    assert result["status"] == "confirmed"
    assert result["booking_id"] == "b1"
    assert result["hotel_name"] == "Lakeside Lodge"
    assert models.BOOKINGS["b1"].guest_name == "Bob"


def test_book_room_unknown_hotel_raises():
    with pytest.raises(ValueError, match="Unknown hotel_id"):
        logic.book_room(
            hotel_id="nope",
            room_type="Standard",
            guest_name="Bob",
            check_in="2026-09-01",
            check_out="2026-09-03",
        )


def test_book_room_raises_when_fully_booked():
    for i in range(12):
        models.BOOKINGS[f"pre{i}"] = models.Booking(
            id=f"pre{i}",
            hotel_id="h3",
            room_type="Standard",
            guest_name=f"Guest{i}",
            check_in="2026-09-01",
            check_out="2026-09-03",
            status="confirmed",
        )
    with pytest.raises(ValueError, match="No Standard rooms available"):
        logic.book_room(
            hotel_id="h3",
            room_type="Standard",
            guest_name="LateGuest",
            check_in="2026-09-01",
            check_out="2026-09-03",
        )


def test_cancel_booking_success():
    booking = logic.book_room(
        hotel_id="h3",
        room_type="Standard",
        guest_name="Carol",
        check_in="2026-09-01",
        check_out="2026-09-03",
    )
    result = logic.cancel_booking(booking["booking_id"])
    assert result["status"] == "cancelled"
    assert models.BOOKINGS[booking["booking_id"]].status == "cancelled"


def test_cancel_booking_unknown_id_raises():
    with pytest.raises(ValueError, match="Unknown booking_id"):
        logic.cancel_booking("does-not-exist")


def test_cancel_booking_already_cancelled_raises():
    booking = logic.book_room(
        hotel_id="h3",
        room_type="Standard",
        guest_name="Dana",
        check_in="2026-09-01",
        check_out="2026-09-03",
    )
    logic.cancel_booking(booking["booking_id"])
    with pytest.raises(ValueError, match="already cancelled"):
        logic.cancel_booking(booking["booking_id"])


def test_list_bookings_returns_all_by_default():
    logic.book_room(
        hotel_id="h3", room_type="Standard", guest_name="Erin", check_in="2026-09-01", check_out="2026-09-02"
    )
    logic.book_room(
        hotel_id="h1", room_type="Standard", guest_name="Frank", check_in="2026-09-01", check_out="2026-09-02"
    )
    assert len(logic.list_bookings()) == 2


def test_list_bookings_filters_by_guest_name_case_insensitive():
    logic.book_room(
        hotel_id="h3", room_type="Standard", guest_name="Erin", check_in="2026-09-01", check_out="2026-09-02"
    )
    logic.book_room(
        hotel_id="h1", room_type="Standard", guest_name="Frank", check_in="2026-09-01", check_out="2026-09-02"
    )
    results = logic.list_bookings(guest_name="erin")
    assert len(results) == 1
    assert results[0]["guest_name"] == "Erin"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_logic.py -v`
Expected: the 8 new tests FAIL with `AttributeError: module 'logic' has no attribute 'book_room'` (or `cancel_booking`/`list_bookings`).

- [ ] **Step 3: Append booking mutation functions to `logic.py`**

Append to `test_booking_mcp/logic.py`:
```python
def book_room(hotel_id: str, room_type: str, guest_name: str, check_in: str, check_out: str) -> dict:
    hotel = _find_hotel(hotel_id)
    rt = _find_room_type(hotel, room_type)
    check_in_date, check_out_date = _validate_date_range(check_in, check_out)
    booked = _rooms_booked(hotel_id, rt.name, check_in_date, check_out_date)
    if booked >= rt.total_rooms:
        raise ValueError(
            f"No {rt.name} rooms available at {hotel.name} for {check_in} to {check_out}"
        )
    booking_id = models.next_booking_id()
    models.BOOKINGS[booking_id] = models.Booking(
        id=booking_id,
        hotel_id=hotel_id,
        room_type=rt.name,
        guest_name=guest_name,
        check_in=check_in,
        check_out=check_out,
        status="confirmed",
    )
    return {
        "booking_id": booking_id,
        "hotel_id": hotel_id,
        "hotel_name": hotel.name,
        "room_type": rt.name,
        "guest_name": guest_name,
        "check_in": check_in,
        "check_out": check_out,
        "status": "confirmed",
    }


def cancel_booking(booking_id: str) -> dict:
    booking = models.BOOKINGS.get(booking_id)
    if booking is None:
        raise ValueError(f"Unknown booking_id: {booking_id!r}")
    if booking.status == "cancelled":
        raise ValueError(f"Booking {booking_id!r} is already cancelled")
    booking.status = "cancelled"
    return {"booking_id": booking_id, "status": "cancelled"}


def list_bookings(guest_name: str | None = None) -> list[dict]:
    bookings = models.BOOKINGS.values()
    if guest_name:
        bookings = [b for b in bookings if b.guest_name.lower() == guest_name.lower()]
    return [
        {
            "booking_id": b.id,
            "hotel_id": b.hotel_id,
            "room_type": b.room_type,
            "guest_name": b.guest_name,
            "check_in": b.check_in,
            "check_out": b.check_out,
            "status": b.status,
        }
        for b in bookings
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_logic.py -v`
Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git add test_booking_mcp/logic.py test_booking_mcp/tests/test_logic.py
git commit -m "feat: add booking creation, cancellation, and listing logic"
```

---

### Task 4: FastMCP server wiring and in-memory integration tests

**Files:**
- Create: `test_booking_mcp/server.py`
- Test: `test_booking_mcp/tests/test_server.py`

**Interfaces:**
- Consumes: `logic.search_hotels`, `logic.check_availability`, `logic.book_room`, `logic.cancel_booking`, `logic.list_bookings` (Task 2/3).
- Produces (used by Task 5): `server.mcp` (the `FastMCP` instance, importable for the in-memory `Client`), `server.app` (the `FastAPI` app), `PORT` env var read at process start (default `8000`).

- [ ] **Step 1: Write the failing integration tests**

`test_booking_mcp/tests/test_server.py`:
```python
from fastmcp import Client
from fastmcp.exceptions import ToolError

import server


async def test_lists_all_five_tools():
    async with Client(server.mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == {
            "search_hotels",
            "check_availability",
            "book_room",
            "cancel_booking",
            "list_bookings",
        }


async def test_full_happy_path_through_mcp_tools():
    async with Client(server.mcp) as client:
        hotels = (await client.call_tool("search_hotels", {"city": "New York"})).data
        assert len(hotels) == 1
        hotel_id = hotels[0]["id"]

        availability = (
            await client.call_tool(
                "check_availability",
                {
                    "hotel_id": hotel_id,
                    "room_type": "Standard",
                    "check_in": "2026-11-01",
                    "check_out": "2026-11-03",
                },
            )
        ).data
        assert availability["is_available"] is True

        booking = (
            await client.call_tool(
                "book_room",
                {
                    "hotel_id": hotel_id,
                    "room_type": "Standard",
                    "guest_name": "Grace",
                    "check_in": "2026-11-01",
                    "check_out": "2026-11-03",
                },
            )
        ).data
        booking_id = booking["booking_id"]
        assert booking["status"] == "confirmed"

        listed = (await client.call_tool("list_bookings", {"guest_name": "Grace"})).data
        assert any(b["booking_id"] == booking_id for b in listed)

        cancelled = (await client.call_tool("cancel_booking", {"booking_id": booking_id})).data
        assert cancelled["status"] == "cancelled"


async def test_book_room_unknown_hotel_surfaces_as_tool_error():
    async with Client(server.mcp) as client:
        with pytest.raises(ToolError, match="Unknown hotel_id"):
            await client.call_tool(
                "book_room",
                {
                    "hotel_id": "nope",
                    "room_type": "Standard",
                    "guest_name": "Heidi",
                    "check_in": "2026-11-01",
                    "check_out": "2026-11-03",
                },
            )
```

Add the missing `pytest` import at the top of the file:
```python
import pytest
```
(full import block at the top of `test_server.py` is `import pytest`, `from fastmcp import Client`, `from fastmcp.exceptions import ToolError`, `import server`)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_server.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`.

- [ ] **Step 3: Write `server.py`**

`test_booking_mcp/server.py`:
```python
import os

from fastapi import FastAPI
from fastmcp import FastMCP

import logic

mcp = FastMCP("Hotel Booking")


@mcp.tool
def search_hotels(city: str | None = None) -> list[dict]:
    """Search hotels, optionally filtered by city."""
    return logic.search_hotels(city)


@mcp.tool
def check_availability(hotel_id: str, room_type: str, check_in: str, check_out: str) -> dict:
    """Check room availability for a hotel and room type over a date range (YYYY-MM-DD)."""
    return logic.check_availability(hotel_id, room_type, check_in, check_out)


@mcp.tool
def book_room(hotel_id: str, room_type: str, guest_name: str, check_in: str, check_out: str) -> dict:
    """Book a room for a guest over a date range (YYYY-MM-DD)."""
    return logic.book_room(hotel_id, room_type, guest_name, check_in, check_out)


@mcp.tool
def cancel_booking(booking_id: str) -> dict:
    """Cancel an existing booking by its booking_id."""
    return logic.cancel_booking(booking_id)


@mcp.tool
def list_bookings(guest_name: str | None = None) -> list[dict]:
    """List bookings, optionally filtered by guest_name."""
    return logic.list_bookings(guest_name)


mcp_app = mcp.http_app(path="/mcp")
app = FastAPI(title="Hotel Booking MCP Server", lifespan=mcp_app.lifespan)
app.mount("/", mcp_app)


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_server.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full test suite so far**

Run: `./env/bin/python -m pytest test_booking_mcp/tests -v`
Expected: all tests across `test_models.py`, `test_logic.py`, `test_server.py` pass.

- [ ] **Step 6: Commit**

```bash
git add test_booking_mcp/server.py test_booking_mcp/tests/test_server.py
git commit -m "feat: wire FastMCP tools into a FastAPI app exposing /mcp"
```

---

### Task 5: Live HTTP smoke test

**Files:**
- Test: `test_booking_mcp/tests/test_http_integration.py`

**Interfaces:**
- Consumes: `test_booking_mcp/server.py` run as a subprocess (`PORT` env var, `/mcp` path) — no code-level interface, this task exercises the real process over HTTP.

- [ ] **Step 1: Write the live-server integration test**

`test_booking_mcp/tests/test_http_integration.py`:
```python
import os
import socket
import subprocess
import sys
import time

import pytest
from fastmcp import Client

PORT = 8791
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(TESTS_DIR)


def _wait_for_port(host: str, port: int, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    raise TimeoutError(f"Server did not start listening on {host}:{port} within {timeout}s")


@pytest.fixture(scope="module")
def live_server_url():
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=SERVER_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        _wait_for_port("127.0.0.1", PORT)
        yield f"http://127.0.0.1:{PORT}/mcp"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


async def test_full_booking_flow_over_real_http_server(live_server_url):
    async with Client(live_server_url) as client:
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert {
            "search_hotels",
            "check_availability",
            "book_room",
            "cancel_booking",
            "list_bookings",
        } <= tool_names

        hotels = (await client.call_tool("search_hotels", {"city": "Chicago"})).data
        assert len(hotels) == 1
        hotel_id = hotels[0]["id"]

        availability = (
            await client.call_tool(
                "check_availability",
                {
                    "hotel_id": hotel_id,
                    "room_type": "Standard",
                    "check_in": "2026-10-01",
                    "check_out": "2026-10-03",
                },
            )
        ).data
        assert availability["is_available"] is True

        booking = (
            await client.call_tool(
                "book_room",
                {
                    "hotel_id": hotel_id,
                    "room_type": "Standard",
                    "guest_name": "Dana",
                    "check_in": "2026-10-01",
                    "check_out": "2026-10-03",
                },
            )
        ).data
        booking_id = booking["booking_id"]
        assert booking["status"] == "confirmed"

        bookings = (await client.call_tool("list_bookings", {"guest_name": "Dana"})).data
        assert any(b["booking_id"] == booking_id for b in bookings)

        cancelled = (await client.call_tool("cancel_booking", {"booking_id": booking_id})).data
        assert cancelled["status"] == "cancelled"

        bookings_after_cancel = (await client.call_tool("list_bookings", {"guest_name": "Dana"})).data
        matching = [b for b in bookings_after_cancel if b["booking_id"] == booking_id]
        assert matching and matching[0]["status"] == "cancelled"
```

- [ ] **Step 2: Run the test**

Run: `./env/bin/python -m pytest test_booking_mcp/tests/test_http_integration.py -v -s`
Expected: 1 passed. The test starts a real `uvicorn` process on port 8791, drives all 5 tools over actual HTTP against `/mcp`, then tears the process down.

- [ ] **Step 3: Run the entire test suite one final time**

Run: `./env/bin/python -m pytest test_booking_mcp/tests -v`
Expected: every test across all four test files passes.

- [ ] **Step 4: Commit**

```bash
git add test_booking_mcp/tests/test_http_integration.py
git commit -m "test: add live HTTP smoke test for the /mcp endpoint"
```
