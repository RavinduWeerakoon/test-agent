import os
import json
import requests
import sys
from dotenv import load_dotenv

# Load local environment variables if available
load_dotenv()

port = os.getenv("PORT", "3000")
BASE_URL = f"http://localhost:{port}"

def get_provider_and_key():
    """Resolves provider and key from environment variables."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if gemini_key:
        return "google", gemini_key
    elif openai_key:
        return "openai", openai_key
    else:
        print("[!] Warning: Neither GEMINI_API_KEY nor OPENAI_API_KEY found in env or .env file.")
        print("[!] Requests will fail unless keys are configured.")
        return "google", ""

def check_config():
    print(f"\n--- Checking API Configuration at {BASE_URL}/config ---")
    try:
        response = requests.get(f"{BASE_URL}/config")
        print(f"Status Code: {response.status_code}")
        print(f"Body: {response.text}")
        return response.json()
    except Exception as e:
        print(f"Connection failed: {str(e)}")
        sys.exit(1)

def run_non_streaming_chat(provider, api_key):
    print(f"\n--- Running Non-Streaming Chat Request (Provider: {provider}) ---")
    
    payload = {
        "message": "What is (145 + 355) * 12?",
        "history": [],
        "provider": provider,
        "apiKey": api_key,
        "stream": False
    }
    
    print(f"Query: {payload['message']}")
    print("Waiting for response...")
    
    try:
        response = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30.0)
        
        if response.status_code != 200:
            print(f"Error ({response.status_code}): {response.text}")
            return
            
        data = response.json()
        print("\n[Tool Calls Executed]")
        tool_calls = data.get("tool_calls", [])
        if not tool_calls:
            print("No tools were called.")
        else:
            for idx, tc in enumerate(tool_calls, 1):
                print(f" {idx}. Tool: {tc['name']}")
                print(f"    Input: {tc['input']}")
                print(f"    Output: {tc['output']}")
                
        print("\n[Final Answer]")
        print(data.get("content"))
        
    except Exception as e:
        print(f"Request failed: {str(e)}")

def run_streaming_chat(provider, api_key):
    print(f"\n--- Running Streaming Chat Request (Provider: {provider}) ---")
    
    payload = {
        "message": "Search Wikipedia for Albert Einstein and tell me his birth year.",
        "history": [],
        "provider": provider,
        "apiKey": api_key,
        "stream": True
    }
    
    print(f"Query: {payload['message']}")
    print("Streaming events...\n")
    
    try:
        # Use requests with stream=True
        with requests.post(f"{BASE_URL}/chat", json=payload, stream=True, timeout=30.0) as r:
            if r.status_code != 200:
                print(f"Error ({r.status_code}) starting stream")
                return
                
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        event = json.loads(decoded_line[6:])
                        event_type = event.get("type")
                        
                        if event_type == "token":
                            # Print token immediately
                            sys.stdout.write(event.get("content", ""))
                            sys.stdout.flush()
                        elif event_type == "tool_start":
                            print(f"\n\n[Tool Started: {event.get('name')}]")
                            print(f"Input: {event.get('input')}")
                        elif event_type == "tool_end":
                            print(f"[Tool Succeeded: {event.get('name')}]")
                            print(f"Output summary: {str(event.get('output'))[:200]}...")
                            print("[Streaming response resuming...]")
                        elif event_type == "done":
                            print("\n\n[Stream Completed]")
                        elif event_type == "error":
                            print(f"\n\n[Agent Error]: {event.get('message')}")
                            
    except Exception as e:
        print(f"\nStream request failed: {str(e)}")

if __name__ == "__main__":
    # 1. Check server configuration
    check_config()
    
    # 2. Get credentials
    provider, api_key = get_provider_and_key()
    
    # 3. Test non-streaming Chat (triggers Calculator tool)
    run_non_streaming_chat(provider, api_key)
    
    # 4. Test streaming Chat (triggers Wikipedia tool)
    run_streaming_chat(provider, api_key)
