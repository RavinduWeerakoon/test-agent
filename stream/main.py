import asyncio
import json
import random
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Request body model
class ChatRequest(BaseModel):
    message: str

app = FastAPI(title="Dummy SSE Server")

WORD_POOL = [
    "nebula", "quantum", "whisper", "cascade", "echo",
    "serendipity", "velocity", "horizon", "luminescent", "solitude"
]

async def sse_event_generator(user_message: str):
    """
    Simulates token-by-token streaming over SSE protocol.
    Format MUST be 'data: <payload>\n\n' for standard SSE clients.
    """
    # 1. Send an initial starting event
    start_payload = json.dumps({"status": "start", "query": user_message})
    yield f"data: {start_payload}\n\n"
    await asyncio.sleep(0.5)

    # 2. Stream random words/tokens
    num_words = random.randint(5, 10)
    for _ in range(num_words):
        word = random.choice(WORD_POOL)
        payload = json.dumps({"token": f"{word} "})
        
        yield f"data: {payload}\n\n"
        await asyncio.sleep(0.3)  # Delay between tokens

    # 3. Send a completion event
    end_payload = json.dumps({"status": "done"})
    yield f"data: {end_payload}\n\n"

@app.post("/chat")
async def chat(payload: ChatRequest):
    """
    POST SSE Endpoint returning 'text/event-stream'.
    """
    return StreamingResponse(
        sse_event_generator(payload.message),
        media_type="text/event-stream"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)