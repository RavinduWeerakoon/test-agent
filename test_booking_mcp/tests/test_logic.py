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
