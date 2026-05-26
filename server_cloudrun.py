import os
import json
import asyncio
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Road Trip Planner")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "YOUR_PROJECT_ID")
LOCATION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
AGENT_ID = os.environ.get("AGENT_ENGINE_ID", "")

_engine = None

def get_engine():
    global _engine
    if _engine is None:
        import vertexai
        from vertexai import agent_engines
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        
        agent_id = AGENT_ID
        if not agent_id and os.path.exists("deployment_metadata.json"):
            with open("deployment_metadata.json") as f:
                meta = json.load(f)
                agent_id = meta.get("remote_agent_runtime_id", "")
                
        _engine = agent_engines.get(agent_id)
    return _engine


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/api/config")
async def get_config():
    return {"maps_api_key": os.environ.get("GOOGLE_MAPS_API_KEY", "")}

def extract_event_data(event):
    author = "agent"
    text = ""
    tool_calls = []

    # 1. Extract Author
    if isinstance(event, dict):
        author = event.get('author', 'agent')
    elif hasattr(event, 'author') and event.author:
        author = event.author

    # 2. Extract Content (Text and Tool Calls)
    if isinstance(event, dict):
        content = event.get('content', {})
        if isinstance(content, dict):
            parts = content.get('parts', [])
            for p in parts:
                if isinstance(p, dict):
                    if 'text' in p and p['text']:
                        text += p['text']
                    if 'function_call' in p and p['function_call']:
                        fc = p['function_call']
                        tool_calls.append({
                            "name": fc.get('name', 'unknown_tool'),
                            "args": dict(fc.get('args', {}))
                        })
    else:
        # If it's a Pydantic object or other object with attributes
        if hasattr(event, 'content') and event.content:
            content = event.content
            if hasattr(content, 'parts') and content.parts:
                for p in content.parts:
                    if hasattr(p, 'text') and p.text:
                        text += p.text
                    if hasattr(p, 'function_call') and p.function_call:
                        fc = p.function_call
                        tool_calls.append({
                            "name": getattr(fc, 'name', 'unknown_tool'),
                            "args": dict(fc.args) if hasattr(fc, 'args') and fc.args else {}
                        })

    return author, text, tool_calls


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    engine = get_engine()
    if req.session_id:
        session_id = req.session_id
    else:
        session = engine.create_session(user_id="web-user")
        session_id = session["id"]

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        yield f"data: {json.dumps({'type': 'status', 'message': 'Thinking...'})}\n\n"

        try:
            import time
            for event in engine.stream_query(
                user_id="web-user",
                session_id=session_id,
                message=req.message,
            ):
                author, text, tool_calls = extract_event_data(event)

                # Stream tool calls
                for tc in tool_calls:
                    payload = {
                        "type": "trajectory",
                        "author": author,
                        "action": tc["name"],
                        "args": tc["args"],
                        "timestamp": time.time()
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                # Stream text content
                if text:
                    payload = {
                        "type": "event",
                        "author": author,
                        "text": text,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'type': 'status', 'message': 'Done!'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/plan")
async def plan_trip(query: str = Query(..., description="The road trip planning query")):
    engine = get_engine()
    session = engine.create_session(user_id="web-user")
    session_id = session["id"]

    async def event_generator():
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        yield f"data: {json.dumps({'type': 'status', 'message': 'Planning your trip...'})}\n\n"

        try:
            import time
            for event in engine.stream_query(
                user_id="web-user",
                session_id=session_id,
                message=query,
            ):
                author, text, tool_calls = extract_event_data(event)

                # Stream tool calls
                for tc in tool_calls:
                    payload = {
                        "type": "trajectory",
                        "author": author,
                        "action": tc["name"],
                        "args": tc["args"],
                        "timestamp": time.time()
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                # Stream text content
                if text:
                    payload = {
                        "type": "event",
                        "author": author,
                        "text": text,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    await asyncio.sleep(0.01)

            yield f"data: {json.dumps({'type': 'status', 'message': 'Trip planned!'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8080, reload=True)
