import os
import json
import asyncio
from contextlib import aclosing
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables for Google GenAI / Vertex AI
load_dotenv("road_trip_planner/.env")

# Initialize ADK Runner and Services
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
from google.adk.auth.credential_service.in_memory_credential_service import InMemoryCredentialService
from google.genai import types
from road_trip_planner.agent import root_agent

app = FastAPI(title="Road Trip Planner API")

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup ADK Services
session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()
credential_service = InMemoryCredentialService()

runner = Runner(
    agent=root_agent,
    session_service=session_service,
    artifact_service=artifact_service,
    credential_service=credential_service,
)

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/api/clear")
async def clear_data():
    """Clears previous trip plan files to start fresh."""
    for filename in ["route_data.json", "itinerary.md"]:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception as e:
                return {"status": "error", "message": f"Failed to remove {filename}: {str(e)}"}
    return {"status": "success", "message": "Previous trip data cleared successfully."}

@app.get("/api/route")
async def get_route():
    """Returns the calculated route geometry and distance details."""
    filepath = "route_data.json"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Route data not found. Please plan a trip first.")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read route data: {str(e)}")

@app.get("/api/itinerary")
async def get_itinerary():
    """Returns the generated markdown itinerary."""
    filepath = "itinerary.md"
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Itinerary file not found. Please plan a trip first.")
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return {"markdown": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read itinerary: {str(e)}")

@app.get("/api/plan")
async def plan_trip(query: str = Query(..., description="The road trip planning query")):
    """Streams the multi-agent execution events in real time using SSE."""
    async def event_generator():
        # Create an ADK session for this execution
        session = await session_service.create_session(
            app_name="road_trip_planner",
            user_id="web_user",
            state={}
        )
        
        user_message = types.Content(role='user', parts=[types.Part(text=query)])
        
        try:
            # Yield starting event
            yield f"data: {json.dumps({'type': 'status', 'message': 'Initializing agents and workflow...'})}\n\n"
            
            async with aclosing(
                runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=user_message
                )
            ) as agen:
                async for event in agen:
                    # Check text content
                    text = ""
                    if event.content and event.content.parts:
                        text = "".join(p.text or "" for p in event.content.parts)
                    
                    # Check tool calls
                    tool_calls = []
                    if event.actions and event.actions.tool_calls:
                        for tc in event.actions.tool_calls:
                            tool_calls.append({
                                "name": tc.name,
                                "args": tc.args
                            })
                    
                    # Yield event back to browser client
                    payload = {
                        "type": "event",
                        "author": event.author or "unknown",
                        "node_path": event.node_info.path if event.node_info else "",
                        "text": text,
                        "tool_calls": tool_calls
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                    # Small sleep to prevent network congestion
                    await asyncio.sleep(0.02)
            
            # Send completion signal
            yield f"data: {json.dumps({'type': 'status', 'message': 'Plan compiled successfully!'})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': f'Planning failed: {str(e)}'})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount static folder
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
