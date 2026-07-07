import os
import json
import asyncio
import logging
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

# Configure Logging for Observability
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("agent_api")

# Tools definitions
@tool
def calculator(expression: str) -> str:
    """Useful for when you need to answer questions about math or execute arithmetic calculations.
    Input should be a mathematical expression, e.g. "2342 * 9482" or "(120 + 45) / 5".
    """
    logger.info(f"Calculator tool triggered with expression: '{expression}'")
    try:
        # Clean expression to prevent arbitrary code execution
        allowed_chars = "0123456789+-*/(). "
        cleaned = "".join(c for c in expression if c in allowed_chars)
        if len(cleaned) != len(expression):
            logger.warning(f"Calculator expression contained invalid characters. Cleaned: '{cleaned}'")
            return "Error: Invalid characters in mathematical expression. Only numbers and +, -, *, /, (), and spaces are allowed."
        
        # Safely evaluate mathematical expressions
        val = eval(cleaned, {"__builtins__": None}, {})
        logger.info(f"Calculator evaluation succeeded. Result: {val}")
        return str(val)
    except Exception as e:
        logger.error(f"Calculator evaluation failed: {str(e)}")
        return f"Error: {str(e)}"

@tool
def search_wikipedia(query: str) -> str:
    """Useful for searching Wikipedia for information about people, places, events, history, and general facts.
    Input should be a search query, e.g. "Albert Einstein" or "United Nations".
    """
    import requests
    logger.info(f"Wikipedia search tool triggered with query: '{query}'")
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
        
        logger.info(f"Wikipedia API request: Searching for '{query}'")
        r = requests.get(search_url, params=search_params, headers=headers, timeout=10.0)
        r.raise_for_status()
        search_results = r.json().get("query", {}).get("search", [])
        
        if not search_results:
            logger.info(f"Wikipedia search returned no results for query: '{query}'")
            return f"No Wikipedia pages found for '{query}'."
        
        # Step 2: Get the summary/extract of the top search result
        page_id = search_results[0]["pageid"]
        title = search_results[0]["title"]
        logger.info(f"Wikipedia top result page: '{title}' (ID: {page_id})")
        
        summary_params = {
            "action": "query",
            "prop": "extracts",
            "exintro": 1,
            "explaintext": 1,
            "pageids": page_id,
            "format": "json"
        }
        
        logger.info(f"Wikipedia API request: Fetching intro extract for page ID: {page_id}")
        r = requests.get(search_url, params=summary_params, headers=headers, timeout=10.0)
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        page_data = pages.get(str(page_id), {})
        extract = page_data.get("extract", "No summary extract available.")
        
        logger.info(f"Wikipedia search succeeded. Page '{title}' summary length: {len(extract)}")
        return f"Wikipedia Title: {title}\nSummary: {extract[:1000]}..."
        
    except Exception as e:
        logger.error(f"Wikipedia search failed: {str(e)}")
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
        
        logger.info(f"[Callback] Agent is starting tool call. Name: '{name}' | Inputs: {inputs}")
        tool_call = {
            "name": name,
            "input": inputs,
            "output": None
        }
        self.tool_calls.append(tool_call)
        self._runs[run_id] = tool_call

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        if run_id in self._runs:
            logger.info(f"[Callback] Agent completed tool call. Name: '{self._runs[run_id]['name']}'")
            self._runs[run_id]["output"] = str(output)

def get_model(provider: str, api_key: str):
    """Initializes the chat model based on provider and api_key."""
    logger.info(f"Initializing model provider: '{provider}'")
    if provider == "google":
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            logger.error("Gemini API Key validation failed: missing key")
            raise HTTPException(status_code=400, detail="Gemini API Key is missing. Please configure GEMINI_API_KEY.")
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        logger.info("ChatGoogleGenerativeAI initialized successfully")
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=key, streaming=True, temperature=0.7)
        
    elif provider == "openai":
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            logger.error("OpenAI API Key validation failed: missing key")
            raise HTTPException(status_code=400, detail="OpenAI API Key is missing. Please configure OPENAI_API_KEY.")
            
        from langchain_openai import ChatOpenAI
        logger.info("ChatOpenAI initialized successfully")
        return ChatOpenAI(model="gpt-4o-mini", api_key=key, streaming=True, temperature=0.7)
        
    else:
        logger.error(f"Model initialization failed: Unsupported provider '{provider}'")
        raise HTTPException(status_code=400, detail=f"Unsupported LLM provider: {provider}")

async def stream_agent_events(payload: ChatPayload) -> AsyncGenerator[str, None]:
    logger.info(f"Starting streaming event generation session for message: '{payload.message[:50]}...'")
    try:
        llm = get_model(payload.provider, payload.apiKey)
        tools = [calculator, search_wikipedia]
        
        system_instruction = ("You are Antigravity, a highly capable AI assistant equipped with tools to help answer users' queries. "
                              "You must use tools whenever you need factual, real-time, or mathematical validation. "
                              "Provide rich, beautiful markdown formatting in your final response including lists, code snippets, bold text, and tables if useful. "
                              "If you use a tool, explain how you got the result based on the tool's output.")
        
        # Initialize LangGraph Agent
        logger.info("Compiling LangGraph react agent")
        agent_executor = create_react_agent(llm, tools, prompt=system_instruction)
        
        # Build messages list representing dialogue state
        messages = []
        for msg in payload.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))
        messages.append(HumanMessage(content=payload.message))
                
        logger.info(f"Invoking astream_events on LangGraph agent. Messages length: {len(messages)}")
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
                tool_name = event['name']
                logger.info(f"[Stream Event] Agent started tool: '{tool_name}'")
                yield f"data: {json.dumps({'type': 'tool_start', 'name': tool_name, 'input': event['data'].get('input')})}\n\n"
                
            # Tool invocation completion
            elif kind == "on_tool_end":
                tool_name = event['name']
                logger.info(f"[Stream Event] Agent completed tool: '{tool_name}'")
                yield f"data: {json.dumps({'type': 'tool_end', 'name': tool_name, 'output': str(event['data'].get('output'))})}\n\n"
                
        logger.info("Finished streaming events successfully")
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
        
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Error encountered during stream generation: {err_msg}", exc_info=True)
        yield f"data: {json.dumps({'type': 'error', 'message': err_msg})}\n\n"

async def run_agent_sync(payload: ChatPayload) -> Dict[str, Any]:
    logger.info(f"Starting non-streaming sync session for message: '{payload.message[:50]}...'")
    llm = get_model(payload.provider, payload.apiKey)
    tools = [calculator, search_wikipedia]
    
    system_instruction = ("You are Antigravity, a highly capable AI assistant equipped with tools to help answer users' queries. "
                          "You must use tools whenever you need factual, real-time, or mathematical validation. "
                          "Provide rich, beautiful markdown formatting in your final response including lists, code snippets, bold text, and tables if useful. "
                          "If you use a tool, explain how you got the result based on the tool's output.")
                          
    logger.info("Compiling LangGraph react agent (sync execution)")
    agent_executor = create_react_agent(llm, tools, prompt=system_instruction)
    
    messages = []
    for msg in payload.history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=payload.message))
            
    tracker = ToolTrackerCallbackHandler()
    
    logger.info(f"Invoking ainvoke on LangGraph agent. Messages length: {len(messages)}")
    result = await agent_executor.ainvoke(
        {"messages": messages},
        config={"callbacks": [tracker]}
    )
    
    last_msg = result["messages"][-1]
    output_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    
    logger.info(f"Non-streaming sync session completed. Final answer length: {len(output_content)} chars | Tool calls: {len(tracker.tool_calls)}")
    return {
        "content": output_content,
        "tool_calls": tracker.tool_calls
    }

@app.post("/chat")
async def chat_endpoint(payload: ChatPayload):
    logger.info(f"POST /chat endpoint called - Provider: '{payload.provider}' | Stream: {payload.stream}")
    try:
        # Validate model selection and key setup
        _ = get_model(payload.provider, payload.apiKey)
    except HTTPException as e:
        detail = e.detail
        logger.warning(f"HTTPException validation error in chat_endpoint: '{detail}'")
        if payload.stream:
            return StreamingResponse(
                (f"data: {json.dumps({'type': 'error', 'message': detail})}\n\n" for _ in range(1)),
                media_type="text/event-stream"
            )
        raise e
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Internal validation error in chat_endpoint: '{err_msg}'", exc_info=True)
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
    logger.info("GET /config endpoint called")
    gemini_ready = bool(os.getenv("GEMINI_API_KEY"))
    openai_ready = bool(os.getenv("OPENAI_API_KEY"))
    logger.info(f"Config query response - Gemini configured: {gemini_ready} | OpenAI configured: {openai_ready}")
    return {
        "gemini_configured": gemini_ready,
        "openai_configured": openai_ready
    }

if __name__ == "__main__":
    import uvicorn
    # Use environment PORT or default to 3000
    port = int(os.getenv("PORT", 3000))
    logger.info(f"Starting server in manual mode. Port: {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
