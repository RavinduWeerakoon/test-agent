import os
import json
import asyncio
from uuid import UUID
from typing import List, Dict, Any, AsyncGenerator
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# LangChain core imports
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.callbacks import AsyncCallbackHandler

# LangGraph import
from langgraph.prebuilt import create_react_agent

# Load environment variables
load_dotenv()

# Tools definitions
@tool
def calculator(expression: str) -> str:
    """Useful for when you need to answer questions about math or execute arithmetic calculations.
    Input should be a mathematical expression, e.g. "2342 * 9482" or "(120 + 45) / 5".
    """
    try:
        # Clean expression to prevent arbitrary code execution
        allowed_chars = "0123456789+-*/(). "
        cleaned = "".join(c for c in expression if c in allowed_chars)
        if len(cleaned) != len(expression):
            return "Error: Invalid characters in mathematical expression. Only numbers and +, -, *, /, (), and spaces are allowed."
        
        # Safely evaluate mathematical expressions
        val = eval(cleaned, {"__builtins__": None}, {})
        return str(val)
    except Exception as e:
        return f"Error: {str(e)}"

@tool
def search_wikipedia(query: str) -> str:
    """Useful for searching Wikipedia for information about people, places, events, history, and general facts.
    Input should be a search query, e.g. "Albert Einstein" or "United Nations".
    """
    import requests
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        # Step 1: Search Wikipedia for pages matching the query
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "format": "json",
            "utf8": 1
        }
        headers = {"User-Agent": "LangChainDemoChatAgent/1.0 (contact@example.com)"}
        
        r = requests.get(search_url, params=search_params, headers=headers, timeout=10.0)
        r.raise_for_status()
        search_results = r.json().get("query", {}).get("search", [])
        
        if not search_results:
            return f"No Wikipedia pages found for '{query}'."
        
        # Step 2: Get the summary/extract of the top search result
        page_id = search_results[0]["pageid"]
        title = search_results[0]["title"]
        
        summary_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "pageids": page_id,
            "format": "json"
        }
        
        r = requests.get(search_url, params=summary_params, headers=headers, timeout=10.0)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        page_data = pages.get(str(page_id), {})
        extract = page_data.get("extract", "No summary extract available.")
        
        return f"Wikipedia Title: {title}\nSummary: {extract[:1000]}..."
        
    except Exception as e:
        return f"Error fetching data from Wikipedia: {str(e)}"

# Setup FastAPI App
app = FastAPI(title="LangGraph Chat Agent API", description="A pure REST API for LangGraph Chat Agent")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatPayload(BaseModel):
    message: str
    history: List[ChatMessage] = Field(default_factory=list)
    provider: str = "google"  # "google" or "openai"
    apiKey: str = ""          # Optional client-side override key
    stream: bool = True       # Enable Server-Sent Events streaming

# Custom Async Callback Handler to track tool invocations during non-streaming runs
class ToolTrackerCallbackHandler(AsyncCallbackHandler):
    def __init__(self):
        self.tool_calls = []
        self._runs = {}

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        name = serialized.get("name", "unknown")
        inputs = input_str
        try:
            inputs = json.loads(input_str)
        except Exception:
            pass
        
        tool_call = {
            "name": name,
            "input": inputs,
            "output": None
        }
        self.tool_calls.append(tool_call)
        self._runs[run_id] = tool_call

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        if run_id in self._runs:
            self._runs[run_id]["output"] = str(output)

def get_model(provider: str, api_key: str):
    """Initializes the chat model based on provider and api_key."""
    if provider == "google":
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="Gemini API Key is missing. Please configure GEMINI_API_KEY.")
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=key, streaming=True, temperature=0.7)
        
    elif provider == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise HTTPException(status_code=400, detail="OpenAI API Key is missing. Please configure OPENAI_API_KEY.")
            
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=key, streaming=True, temperature=0.7)
        
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported LLM provider: {provider}")

async def stream_agent_events(payload: ChatPayload) -> AsyncGenerator[str, None]:
    try:
        llm = get_model(payload.provider, payload.apiKey)
        tools = [calculator, search_wikipedia]
        
        system_instruction = ("You are Antigravity, a highly capable AI assistant equipped with tools to help answer users' queries. "
                              "You must use tools whenever you need factual, real-time, or mathematical validation. "
                              "Provide rich, beautiful markdown formatting in your final response including lists, code snippets, bold text, and tables if useful. "
                              "If you use a tool, explain how you got the result based on the tool's output.")
        
        # Initialize LangGraph Agent
        agent_executor = create_react_agent(llm, tools, prompt=system_instruction)
        
        # Build messages list representing dialogue state
        messages = []
        for msg in payload.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=payload.message))
                
        async for event in agent_executor.astream_events(
            {"messages": messages}, 
            version="v2"
        ):
            kind = event["event"]
            
            # Streaming LLM tokens
            if kind == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if hasattr(chunk, "content") and chunk.content:
                    if not hasattr(chunk, "tool_call_chunks") or not chunk.tool_call_chunks:
                        raw_content = chunk.content
                        if isinstance(raw_content, list):
                            text_parts = []
                            for part in raw_content:
                                if isinstance(part, str):
                                    text_parts.append(part)
                                elif isinstance(part, dict) and "text" in part:
                                    text_parts.append(part["text"])
                            text_content = "".join(text_parts)
                        else:
                            text_content = str(raw_content)
                        yield f"data: {json.dumps({'type': 'token', 'content': text_content})}\n\n"
            
            # Tool invocation start
            elif kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'name': event['name'], 'input': event['data'].get('input')})}\n\n"
                
            # Tool invocation completion
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'name': event['name'], 'output': str(event['data'].get('output'))})}\n\n"
                
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        err_msg = str(e)
        yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"

async def run_agent_sync(payload: ChatPayload) -> Dict[str, Any]:
    llm = get_model(payload.provider, payload.apiKey)
    tools = [calculator, search_wikipedia]
    
    system_instruction = ("You are Antigravity, a highly capable AI assistant equipped with tools to help answer users' queries. "
                          "You must use tools whenever you need factual, real-time, or mathematical validation. "
                          "Provide rich, beautiful markdown formatting in your final response including lists, code snippets, bold text, and tables if useful. "
                          "If you use a tool, explain how you got the result based on the tool's output.")
                          
    agent_executor = create_react_agent(llm, tools, prompt=system_instruction)
    
    messages = []
    for msg in payload.history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=payload.message))
            
    tracker = ToolTrackerCallbackHandler()
    
    result = await agent_executor.ainvoke(
        {"messages": messages},
        config={"callbacks": [tracker]}
    )
    
    last_msg = result["messages"][-1]
    output_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    
    return {
        "content": output_content,
        "tool_calls": tracker.tool_calls
    }

@app.post("/chat")
async def chat_endpoint(payload: ChatPayload):
    try:
        _ = get_model(payload.provider, payload.apiKey)
    except HTTPException as e:
        detail = e.detail
        if payload.stream:
            return StreamingResponse(
                (f"data: {json.dumps({'type': 'error', 'message': detail})}\n\n" for _ in range(1)),
                media_type="text/event-stream"
            )
        raise e
    except Exception as e:
        err_msg = str(e)
        if payload.stream:
            return StreamingResponse(
                (f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n" for _ in range(1)),
                media_type="text/event-stream"
            )
        raise HTTPException(status_code=500, detail=err_msg)
        
    if payload.stream:
        return StreamingResponse(stream_agent_events(payload), media_type="text/event-stream")
    else:
        response_data = await run_agent_sync(payload)
        return response_data

@app.get("/config")
def get_config():
    """Returns which global environment API keys are loaded."""
    return {
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "openai_configured": bool(os.getenv("OPENAI_API_KEY"))
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 3000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
