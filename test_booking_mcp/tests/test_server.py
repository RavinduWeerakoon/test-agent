import pytest
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
