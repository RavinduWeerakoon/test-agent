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
