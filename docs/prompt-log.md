# AGY CLI Prompt Log — Trip Planner

Exact prompts sent to agy CLI. Replay these to reproduce the demo.

## Prompt 1: Build the multi-agent trip planner

**Mode**: `/goal` (fully autonomous)

```
/goal Build a complete multi-agent Road Trip Planner application using Google ADK (google-adk v2.0.0) in this directory. The app helps users plan road trips with real data from Google APIs and web search.

ARCHITECTURE - 6 agents:
1. Orchestrator (root_agent) - Routes user requests, coordinates multi-step trip planning, maintains itinerary state
2. Flight Agent - Searches for flights between cities using Google search grounding. Compares prices, suggests best options, handles multi-city trips
3. Route Planner Agent - Plans driving routes between stops using Google Maps Platform APIs (Directions/Routes). Calculates drive times, distances, suggests scenic routes and optimal stop order
4. Hotel Agent - Finds and recommends hotels at each destination using Google Places API (nearby search for lodging). Shows ratings, price levels, reviews
5. Activities Agent - Discovers things to do at each location using Google Places API (tourist attractions, restaurants, entertainment, parks). Suggests unique local experiences, hidden gems, food scenes
6. Tour Agent - Finds guided tours, day trips, and unique experiences at destinations using web search grounding. Covers adventure tours, food tours, historical walks, outdoor excursions

STRUCTURE:
trip_planner/
  __init__.py          # Exports root_agent
  agent.py             # Root orchestrator with sub-agent delegation
  tools.py             # Google Maps/Places API tools + web search helpers
  sub_agents/
    __init__.py
    flight_agent.py    # Flight search agent
    route_planner.py   # Driving route planning agent
    hotel_agent.py     # Hotel search and booking agent
    activities_agent.py # Things-to-do discovery agent
    tour_agent.py      # Tour and experience finder agent
pyproject.toml         # Deps: google-adk, googlemaps, python-dotenv
.env                   # GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID

REQUIREMENTS:
1. Use google.adk.agents.Agent class, model "gemini-2.5-flash"
2. For Vertex AI auth, create a VertexGemini subclass of google.adk.models.Gemini that sets vertexai=True (same pattern as commerce-intel agent)
3. Route Planner tools should use the googlemaps Python client (pip install googlemaps) with Google Maps Directions API
4. Hotel and Activities tools should use Google Places API (New) via the googlemaps client or direct REST calls
5. Flight and Tour agents should use Gemini's built-in web search/grounding capabilities for real-time data (no external API needed - just instruct the agent to search the web)
6. Root agent orchestrates by delegating to sub-agents using transfer_to_agent (ADK's sub_agents parameter)
7. Each sub-agent has focused instructions in its own file
8. Create a comprehensive test: python3 -c "from trip_planner.agent import root_agent; print(root_agent.name)"
9. Create a test_run.py that tests the agent with: "Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur. Find flights, hotels, activities, and tours at each stop."
10. Google Maps API key should be read from GOOGLE_MAPS_API_KEY env var

Make sure the agent is fully functional and all imports work. Test it.
```

**What agy did**:
- Researched ADK v2.0.0 via web search and package introspection
- Scaffolded a test app with `adk create` to learn the framework
- Read commerce-intel agent's `VertexGemini` class and reused the pattern
- Created all 8+ source files
- Discovered Vertex AI limitation: can't mix Google Search grounding with custom tools
- Found ADK's `bypass_multi_tools_limit=True` workaround
- Updated all sub-agents with explicit transfer instructions
- Ran 3 test iterations, fixing issues each time
- Final test produced a complete California Coastal Road Trip itinerary
- Also built a FastAPI web server + HTML/CSS frontend (bonus!)

## Prompt 2: Deploy to GEAP

```
Now deploy this Road Trip Planner Agent to Google's Gemini Enterprise Agent Platform (GEAP). Use GCP project YOUR_PROJECT_ID in us-central1. Steps: 1) Use agents-cli scaffold enhance to prepare for deployment targeting agent_runtime 2) Copy the trip_planner package into the app/ directory 3) Update app/agent.py entrypoint to load root_agent from trip_planner 4) Ensure pyproject.toml has all required deps including google-adk, googlemaps, python-dotenv, google-cloud-aiplatform 5) Run uv lock 6) Deploy with agents-cli deploy 7) Grant the Agent Runtime service account any needed permissions 8) After deployment, also try running: agents-cli publish gemini-enterprise to register it in the Gemini Enterprise catalog. Document the deployed agent's resource ID.
```

**What agy did**:
- Ran `agents-cli scaffold enhance . -d agent_runtime --region us-central1`
- Copied `trip_planner` into `app/` directory
- Updated entrypoint `app/agent.py`
- Updated `pyproject.toml` with all dependencies
- Ran `uv lock`
- Kicked off `agents-cli deploy` (model quota exhausted before completion)
- Deployment was completed manually — deployed successfully to Agent Runtime
