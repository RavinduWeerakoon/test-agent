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
