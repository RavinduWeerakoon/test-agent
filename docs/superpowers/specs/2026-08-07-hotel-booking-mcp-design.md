# Hotel Booking MCP Server — Design

**Date:** 2026-08-07
**Location:** `test_booking_mcp/`

## Purpose

A standalone MCP server exposing hotel-booking tools over streamable HTTP at
`/mcp`, built with FastMCP mounted into FastAPI. Backed by in-memory mock
data — no external database, no auth. Intended as a local test/demo server,
following the pattern of the other `*_mcp*`/`stream*` test directories in
this repo.

## Architecture

- `fastmcp.FastMCP` instance defines the tools below via `@mcp.tool`.
- `mcp.http_app(path="/mcp")` produces a Starlette ASGI app using the
  streamable-HTTP transport.
- That app is mounted into a `FastAPI` app, with FastAPI's `lifespan`
  wired to the MCP app's lifespan (required for streamable-HTTP session
  management).
- Result: running the FastAPI app with uvicorn exposes the MCP endpoint at
  `http://host:port/mcp`.
- No authentication layer, no `.env` file — nothing secret or configurable
  is required.

## Data Model (in-memory, `models.py`)

- `HOTELS`: a fixed list of ~4 mock hotels. Each entry has `id`, `name`,
  `city`, and a list of room `types` (`name`, `price_per_night`,
  `total_rooms`).
- `BOOKINGS`: a dict keyed by a generated `booking_id`, storing `hotel_id`,
  `room_type`, `guest_name`, `check_in`, `check_out`, and `status`
  (`confirmed` / `cancelled`).
- Availability for a given hotel + room type + date range is computed by
  counting existing non-cancelled bookings for that hotel+room type whose
  date range overlaps the requested range, and comparing against
  `total_rooms` for that room type.
- Dates are plain `YYYY-MM-DD` strings, parsed with
  `datetime.date.fromisoformat`. A request where `check_out <= check_in`
  is rejected with a clear error.

## Tools (`server.py`)

1. **`search_hotels(city: str | None = None)`**
   Returns all hotels, optionally filtered by city (case-insensitive
   match), including their room types and prices.

2. **`check_availability(hotel_id: str, room_type: str, check_in: str, check_out: str)`**
   Returns whether rooms of that type are free for the given date range,
   and how many.

3. **`book_room(hotel_id: str, room_type: str, guest_name: str, check_in: str, check_out: str)`**
   Validates the hotel/room type exist and that availability is non-zero
   for the range, then creates a booking and returns a confirmation
   including the new `booking_id`.

4. **`cancel_booking(booking_id: str)`**
   Marks a booking `cancelled`. Errors if the booking doesn't exist or is
   already cancelled.

5. **`list_bookings(guest_name: str | None = None)`**
   Lists bookings, optionally filtered by guest name (case-insensitive).

## Error Handling

Tools raise on:
- Unknown `hotel_id` or `room_type`.
- Invalid date strings or `check_out <= check_in`.
- Booking with no availability.
- Cancelling a nonexistent or already-cancelled booking.

FastMCP surfaces these as tool errors back to the calling MCP client.

## Files

- `test_booking_mcp/models.py` — mock hotel data, booking store,
  availability logic.
- `test_booking_mcp/server.py` — FastMCP tool definitions, FastAPI/uvicorn
  wiring, `if __name__ == "__main__"` entrypoint on port 8000.
- `test_booking_mcp/requirements.txt` — records `fastmcp`, `fastapi`,
  `uvicorn` (already installed in the repo's `./env` venv, which this
  server reuses — no new venv created).

## Out of Scope

- Persistence across restarts (SQLite/external DB).
- Authentication/authorization.
- Payment, pricing calculation across multiple nights, or real hotel data
  integration.

## Testing Plan

Start the server locally, then exercise each tool once via an MCP client
(e.g. a short FastMCP client script or `curl` against `/mcp`):
search a city, check availability, book a room, list bookings (confirm it
appears), cancel it, list bookings again (confirm status is `cancelled`).
