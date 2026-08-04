import os
from contextlib import asynccontextmanager
from typing import Any, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Global agent variable
agent_app = None


async def initialize_mcp_agent():
    """Reads environment variables, fetches MCP tools, and initializes the LangGraph agent."""
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

    # Initialize model and create ReAct graph
    model = ChatOpenAI(model="gpt-4o", temperature=0)
    agent = create_react_agent(model, tools)
    return agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager to initialize the MCP tools on startup."""
    global agent_app
    agent_app = await initialize_mcp_agent()
    yield
    # Cleanup code can go here if needed


app = FastAPI(title="LangGraph MCP Agent API", lifespan=lifespan)


# --- Request/Response Models ---

class MessageItem(BaseModel):
    role: str = Field(..., description="Role of the sender: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Content of the message")

class ChatRequest(BaseModel):
    message: Optional[str] = Field(None, description="Single prompt message")
    history: Optional[List[MessageItem]] = Field(
        default=None, 
        description="Optional conversation history including past user/assistant messages"
    )

class ChatResponse(BaseModel):
    response: str
    thread_id: Optional[str] = None


# --- Endpoint ---

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    if not agent_app:
        raise HTTPException(status_code=500, detail="Agent is not initialized.")

    # Convert request messages to LangChain message formats
    messages = []
    
    if request.history:
        for item in request.history:
            if item.role == "user":
                messages.append(HumanMessage(content=item.content))
            elif item.role == "assistant":
                messages.append(AIMessage(content=item.content))
            elif item.role == "system":
                messages.append(SystemMessage(content=item.content))

    if request.message:
        messages.append(HumanMessage(content=request.message))

    if not messages:
        raise HTTPException(status_code=400, detail="Either 'message' or 'history' must be provided.")

    try:
        # Invoke the LangGraph agent asynchronously
        result = await agent_app.ainvoke({"messages": messages})
        
        # Extract the final AI message
        final_message = result["messages"][-1].content
        return ChatResponse(response=final_message)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)