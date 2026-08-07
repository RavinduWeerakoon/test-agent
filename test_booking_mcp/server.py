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
