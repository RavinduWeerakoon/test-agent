import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, ConfigDict, Field

load_dotenv()

agent_app = None


async def initialize_mcp_agent():
    """Reads environment variables, fetches MCP tools, and builds the agent."""
    raw_urls = os.environ.get("MY_PROXY_URL", "")
    mcp_server_urls = [url.strip() for url in raw_urls.split(",") if url.strip()]
    mcp_api_key = os.environ.get("MY_PROXY_API_KEY", "").strip()

    server_configs: dict[str, dict[str, Any]] = (
        {
            f"mcp_server_{i}": {
                "url": url,
                "transport": "streamable_http",
                "headers": {
                    "API-Key": mcp_api_key,
                    "Authorization": "",
                },
            }
            for i, url in enumerate(mcp_server_urls)
        }
        if mcp_server_urls and mcp_api_key
        else {}
    )

    if not server_configs:
        print("Warning: No MCP server configs generated. Check MY_PROXY_URL and MY_PROXY_API_KEY.")

    mcp_client = MultiServerMCPClient(server_configs)
    tools = await mcp_client.get_tools()
    print(f"Loaded {len(tools)} tool(s) from MCP servers.")

    memory = MemorySaver()
    model = ChatOpenAI(model="gpt-4o", temperature=0)

    # ReAct agent with in-memory thread persistence
    agent = create_react_agent(model, tools, checkpointer=memory)
    return agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_app
    agent_app = await initialize_mcp_agent()
    yield


app = FastAPI(title="Flexible MCP LangGraph Agent", lifespan=lifespan)


# --- Flexible Request / Response Models ---

class FlexibleChatRequest(BaseModel):
    # Allows additional arbitrary metadata in the body without throwing a 422 error
    model_config = ConfigDict(extra="allow")

    message: Optional[str] = Field(default="", description="The main user prompt or query.")
    session_id: Optional[str] = Field(default="default_session", description="Thread ID for history.")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary context data.")


class FlexibleChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    response: str
    session_id: Optional[str] = None


# --- Endpoint ---

@app.post("/chat", response_model=FlexibleChatResponse)
async def chat_endpoint(request: FlexibleChatRequest):
    if not agent_app:
        raise HTTPException(status_code=500, detail="Agent is not initialized.")

    if not request.message:
        raise HTTPException(status_code=400, detail="A 'message' field is required in the body.")

    # Fallback to 'default_session' if session_id is omitted or empty
    session_id = request.session_id or "default_session"
    config = {"configurable": {"thread_id": session_id}}

    # Format user input with any attached context metadata
    input_text = request.message
    if request.context:
        input_text += f"\n\n[Context Data: {request.context}]"

    try:
        # Run agent asynchronously with thread memory
        result = await agent_app.ainvoke(
            {"messages": [HumanMessage(content=input_text)]},
            config=config,
        )

        final_message = result["messages"][-1].content
        return FlexibleChatResponse(response=final_message, session_id=session_id)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent runtime error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)