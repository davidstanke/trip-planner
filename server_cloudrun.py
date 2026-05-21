import os
import json
import asyncio
from fastapi import FastAPI, Query, HTTPException
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
        _engine = agent_engines.get(AGENT_ID)
    return _engine


@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/api/config")
async def get_config():
    return {"maps_api_key": os.environ.get("GOOGLE_MAPS_API_KEY", "")}


@app.get("/api/plan")
async def plan_trip(query: str = Query(..., description="The road trip planning query")):
    engine = get_engine()
    session = engine.create_session(user_id="web-user")
    session_id = session["id"]

    async def event_generator():
        yield f"data: {json.dumps({'type': 'status', 'message': 'Planning your trip...'})}\n\n"

        try:
            for event in engine.stream_query(
                user_id="web-user",
                session_id=session_id,
                message=query,
            ):
                text = ""
                author = "agent"
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts'):
                        text = "".join(
                            p.text for p in event.content.parts
                            if hasattr(p, 'text') and p.text
                        )
                    if hasattr(event, 'author'):
                        author = event.author or "agent"
                elif isinstance(event, dict):
                    content = event.get('content', {})
                    if isinstance(content, dict) and 'parts' in content:
                        text = "".join(
                            p.get('text', '') for p in content['parts']
                        )
                    elif isinstance(content, str):
                        text = content
                    author = event.get('author', 'agent')

                if text.strip():
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
