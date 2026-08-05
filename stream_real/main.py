import json
import os
from typing import Annotated, TypedDict

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


class State(TypedDict):
    messages: Annotated[list, add_messages]


llm = ChatOpenAI(model=OPENAI_MODEL, api_key=OPENAI_API_KEY, streaming=True)


async def answer(state: State):
    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}


graph_builder = StateGraph(State)
graph_builder.add_node("answer", answer)
graph_builder.add_edge(START, "answer")
graph_builder.add_edge("answer", END)
graph = graph_builder.compile()


class ChatRequest(BaseModel):
    message: str


app = FastAPI(title="Simple Q&A Streaming Agent")


# ...existing code...
async def sse_event_generator(user_message: str):
    def _extract_text_from_token(token) -> str:
        if token is None:
            return ""
        # Prefer common attributes, fall back to content_blocks or str()
        if hasattr(token, "content"):
            return str(getattr(token, "content") or "")
        if getattr(token, "content_blocks", None):
            try:
                parts = []
                for b in token.content_blocks:
                    if isinstance(b, dict):
                        parts.append(b.get("text") or b.get("content") or str(b))
                    else:
                        parts.append(getattr(b, "text", None) or getattr(b, "content", None) or str(b))
                return "".join(parts)
            except Exception:
                return str(token.content_blocks)
        return str(token)

    # start event
    yield f"event: start\ndata: {json.dumps({'type': 'start', 'query': user_message})}\n\n"

    inputs = {"messages": [HumanMessage(content=user_message)]}
    async for chunk in graph.astream(inputs, stream_mode="messages", version="v2"):
        if chunk["type"] == "messages":
            token, metadata = chunk["data"]
            content = _extract_text_from_token(token)
            payload = {
                "type": "chunk",
                "node": metadata.get("langgraph_node"),
                "content": content,
            }
            yield f"event: message\ndata: {json.dumps(payload)}\n\n"

    # done event
    yield f"event: done\ndata: {json.dumps({'type': 'done'})}\n\n"

@app.post("/chat")
async def chat(payload: ChatRequest):
    return StreamingResponse(
        sse_event_generator(payload.message),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=120)
