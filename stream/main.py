import asyncio
import json
import random
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str

app = FastAPI(title="Long Streaming SSE Server")

WORD_POOL = [
    "nebula", "quantum", "whisper", "cascade", "echo",
    "serendipity", "velocity", "horizon", "luminescent", "solitude",
    "vortex", "synthesis", "ephemeral", "catalyst", "paradox"
]

async def long_sse_event_generator(user_message: str):
    """
    Streams SSE events for ~70 seconds (140 iterations * 0.5s delay).
    """
    # 1. Send initial start payload
    start_payload = json.dumps({"status": "start", "query": user_message})
    yield f"data: {start_payload}\n\n"

    # 2. Loop for ~70 seconds total (140 steps * 0.5 sec)
    total_steps = 140
    for step in range(total_steps):
        word = random.choice(WORD_POOL)
        
        # Every 10 steps (~5 seconds), send a heartbeat comment to keep the connection alive
        if step % 10 == 0:
            yield ": keep-alive heartbeat\n\n"

        payload = json.dumps({
            "step": step + 1,
            "token": f"{word} "
        })
        yield f"data: {payload}\n\n"
        
        # 0.5s delay per step = ~70 seconds total runtime
        await asyncio.sleep(0.5)

    # 3. Send final done payload
    end_payload = json.dumps({"status": "done"})
    yield f"data: {end_payload}\n\n"

@app.post("/chat")
async def chat(payload: ChatRequest):
    return StreamingResponse(
        long_sse_event_generator(payload.message),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    # Make sure server timeout settings allow long-running connections
    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=120)