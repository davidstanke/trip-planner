# Road Trip Planner: End-to-End Demo Guide

## Build with AGY CLI → Deploy to GEAP → Plan Epic Road Trips

**Duration**: ~45 minutes | **Audience**: Technical Sales Engineers

---

## Act 1: Build with AGY CLI (~15-20 min)

### Step 1: Launch AGY CLI

```bash
cd trip-planner
agy --dangerously-skip-permissions
```

### Step 2: Send the Build Prompt

```
/goal Build a complete multi-agent Road Trip Planner application using Google ADK (google-adk v2.0.0) in this directory. The app helps users plan road trips with real data from Google APIs.

ARCHITECTURE - 4 agents:
1. Orchestrator (root_agent) - Routes user requests, coordinates multi-step trip planning, maintains itinerary state
2. Route Planner Agent - Plans driving routes between stops using Google Maps Platform APIs (Directions/Routes). Calculates drive times, distances, suggests scenic routes and optimal stop order
3. Hotel Agent - Finds and recommends hotels at each destination using Google Places API (nearby search for lodging). Shows ratings, price levels, reviews
4. Activities Agent - Discovers things to do at each location using Google Places API (tourist attractions, restaurants, entertainment, parks). Suggests unique local experiences, hidden gems, food scenes

STRUCTURE:
trip_planner/
  __init__.py
  agent.py
  tools.py
  sub_agents/
    __init__.py
    route_planner.py
    hotel_agent.py
    activities_agent.py
pyproject.toml
.env

REQUIREMENTS:
1. Use google.adk.agents.Agent class, model "gemini-2.5-flash"
2. For Vertex AI auth, create a VertexGemini subclass of google.adk.models.Gemini that sets vertexai=True
3. Route Planner tools should use the googlemaps Python client with Google Maps Directions API
4. Hotel and Activities tools should use Google Places API via the googlemaps client or direct REST calls
5. Root agent orchestrates by delegating to sub-agents using transfer_to_agent
6. Each sub-agent has focused instructions in its own file
7. Create a test: python3 -c "from trip_planner.agent import root_agent; print(root_agent.name)"
8. Create a test_run.py that tests with: "Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur."
9. Google Maps API key should be read from GOOGLE_MAPS_API_KEY env var
```

### What to Watch For

1. **Research phase**: agy searches for ADK v2.0.0 APIs, introspects the package
2. **Google Search grounding workaround**: Vertex AI doesn't allow mixing Google Search with custom tools. agy discovers ADK's `bypass_multi_tools_limit=True` trick
3. **Self-correction**: agy fixes tool configurations, transfer instructions, import paths
4. **Test execution**: Multi-agent coordination producing a complete itinerary

---

## Act 2: Deploy to GEAP (~10 min)

### Step 3: Send the Deploy Prompt

```
Now deploy this Road Trip Planner Agent to Google's Gemini Enterprise Agent Platform (GEAP). Use GCP project YOUR_PROJECT_ID in us-central1. Steps: 1) Use agents-cli scaffold enhance to prepare for deployment targeting agent_runtime 2) Copy the trip_planner package into the app/ directory 3) Update app/agent.py entrypoint 4) Ensure pyproject.toml has all deps including google-adk, googlemaps, python-dotenv, google-cloud-aiplatform, google-cloud-logging 5) Run uv lock 6) Deploy with agents-cli deploy 7) Grant the Agent Runtime service account any needed permissions 8) Try agents-cli publish gemini-enterprise to register in the Gemini Enterprise catalog.
```

### Expected Output

```
✅ Deployment successful!
Agent Runtime ID: projects/YOUR_PROJECT_NUMBER/locations/us-central1/reasoningEngines/YOUR_AGENT_ID
Console Playground: https://console.cloud.google.com/vertex-ai/agents/...
```

---

## Act 3: Run on GEAP (~10 min)

### Step 4: Open the Console Playground

Navigate to the Console Playground URL from the deployment output. Try these queries:

1. *"Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur. Find hotels and activities at each stop."*
2. Follow-up: *"What about restaurant recommendations for Monterey?"* (tests session persistence)
3. New session: *"Plan a driving trip from Portland to Seattle" (tests multi-user isolation)*

### Step 5: Show Observability

```bash
# View traces
gcloud logging read "resource.type=aiplatform.googleapis.com/ReasoningEngine" --limit=10 --project=YOUR_PROJECT_ID
```

### Step 6: Publish to Gemini Enterprise (Optional)

```bash
agents-cli publish gemini-enterprise
```

---

## Cleanup

```bash
gcloud ai reasoning-engines delete YOUR_AGENT_ID --project=YOUR_PROJECT_ID --region=us-central1
```

---

## Act 4: Deploy Frontend to Cloud Run (~5 min)

**Narrative**: *"Let's make this accessible to the whole org with a beautiful web interface."*

### Step 5: Deploy the Web Frontend

```bash
gcloud run deploy trip-planner \
  --source . \
  --project YOUR_PROJECT_ID \
  --region us-central1 \
  --no-allow-unauthenticated \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_REGION=us-central1,AGENT_ENGINE_ID=projects/YOUR_PROJECT_NUMBER/locations/us-central1/reasoningEngines/YOUR_AGENT_ID,GOOGLE_MAPS_API_KEY=YOUR_MAPS_API_KEY"
```

### Step 6: Grant Access (IAP)

```bash
# Only your account can access
gcloud run services add-iam-policy-binding trip-planner \
  --project=YOUR_PROJECT_ID \
  --region=us-central1 \
  --member="user:your-email@your-domain.com" \
  --role="roles/run.invoker"
```

### Step 7: Access the Frontend

```bash
# Use Cloud Run proxy for local browser access
gcloud run services proxy trip-planner --project YOUR_PROJECT_ID --region us-central1
# Open http://localhost:8080
```

### Frontend Features
- Dark mode with glassmorphism UI
- Interactive Leaflet map with route visualization
- Agent console showing which specialist is working
- Real-time streaming of the itinerary as it's generated
- Timeline-based day-by-day itinerary with photos, hotels, activities

---

## Act 5: Publish to Gemini Enterprise (Optional)

```bash
agents-cli publish gemini-enterprise
```

This registers the agent in the Gemini Enterprise catalog, making it discoverable by authorized users in the Gemini Enterprise web app (gemini.google.com for enterprise).
