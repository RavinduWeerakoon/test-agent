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


async def sse_event_generator(user_message: str):
    yield f"data: {json.dumps({'status': 'start', 'query': user_message})}\n\n"

    inputs = {"messages": [HumanMessage(content=user_message)]}
    async for message_chunk, _metadata in graph.astream(inputs, stream_mode="messages"):
        if message_chunk.content:
            yield f"data: {json.dumps({'response': message_chunk.content})}\n\n"

    yield f"data: {json.dumps({'status': 'done'})}\n\n"


@app.post("/chat")
async def chat(payload: ChatRequest):
    return StreamingResponse(
        sse_event_generator(payload.message),
        media_type="text/event-stream",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, timeout_keep_alive=120)
