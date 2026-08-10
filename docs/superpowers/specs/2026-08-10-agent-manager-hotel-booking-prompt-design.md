# Hotel-Booking System Prompt for the Agent Manager Agent — Design

**Date:** 2026-08-10
**Location:** `mcp_test/main.py`, `mcp_test/.env`

## Purpose

`mcp_test/main.py` is a LangGraph ReAct agent intended to run as a
**platform-hosted agent inside WSO2 Agent Manager**, connecting to the
hotel-booking MCP server (deployed separately on Railway) through an
Agent Manager MCP proxy, per
[Configure Agent MCP Proxies](https://wso2.github.io/agent-manager/docs/v1.0.0-alpha1/tutorials/configure-agent-mcp-proxies/).

The proxy will be registered under the generic id `my-proxy`, so Agent
Manager injects `MY_PROXY_URL` / `MY_PROXY_API_KEY` at deploy time — the
existing `MultiServerMCPClient` wiring in `main.py` (env vars, `API-Key`
header, `streamable_http` transport) already matches that pattern exactly
and is not changed by this design.

The one gap: the ReAct agent currently has no system prompt, so it has no
idea it's a hotel-booking assistant or how the 5 attached tools
(`search_hotels`, `check_availability`, `book_room`, `cancel_booking`,
`list_bookings`) are meant to be used.

## Change

### `main.py`: add a system prompt

A module-level `SYSTEM_PROMPT: str` constant is added, describing:
- The agent's role as a hotel-booking assistant.
- The 5 available tools and when to use each.
- That all dates must be passed to tools as `YYYY-MM-DD` strings (matches
  the tool server's validation).
- That the agent must ask the user for missing required info (dates,
  guest name, city/hotel) instead of guessing or inventing values.
- That after a successful booking, the agent confirms the hotel, room
  type, dates, and `booking_id` back to the user.
- That tool errors (e.g. "no rooms available", unknown hotel) are
  surfaced to the user in plain language, not as raw exception text.

`create_react_agent(model, tools, checkpointer=memory, prompt=SYSTEM_PROMPT)`
passes it in — this LangGraph version's `create_react_agent` accepts a
`prompt: str | SystemMessage | ...` keyword argument (confirmed against
the installed `langgraph` version), which is turned into the leading
system message on every run.

### `.env`: replace placeholder URLs

`MY_PROXY_URL` currently holds two fake `https://mcp-server-*.example.com/sse`
values (comma-separated, for the old multi-server example). These are
replaced with a single realistic placeholder pointing at the pattern of
the deployed hotel-booking server's `/mcp` path, with a comment noting
that Agent Manager overwrites this value at deploy time — the `.env` file
is only a local-dev fallback.

## Out of Scope

- No change to the MCP connection/auth plumbing (`MultiServerMCPClient`,
  env var names, header names, transport) — already correct for the
  platform-hosted pattern.
- No change to `/chat` request/response handling.
- No change to the hotel-booking MCP server itself (`test_booking_mcp/`).

## Testing Plan

No automated tests exist for `mcp_test/main.py` today and none are added
here (this change is a prompt string + a `.env` placeholder, not testable
business logic). Verification is manual: start the FastAPI app locally
with `MY_PROXY_URL` pointed at the deployed hotel-booking server's `/mcp`
URL, POST a message like "Find me a standard room in Chicago for
2026-10-01 to 2026-10-03" to `/chat`, and confirm the agent calls the
booking tools and responds sensibly rather than asking generic
non-domain questions.
