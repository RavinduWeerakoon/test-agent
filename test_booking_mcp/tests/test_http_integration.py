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
