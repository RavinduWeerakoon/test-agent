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
