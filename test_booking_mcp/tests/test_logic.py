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
