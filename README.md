# Road Trip Planner Agent

**Build with AGY CLI. Deploy to GEAP. Plan epic road trips.**

A multi-agent Road Trip Planner built autonomously by [Antigravity CLI (agy)](https://antigravity.google) using [Google ADK](https://github.com/google/adk-python), deployed to [Gemini Enterprise Agent Platform (GEAP)](https://docs.cloud.google.com/gemini-enterprise-agent-platform).

Users describe a trip in plain English. The agent plans routes, finds flights, books hotels, discovers activities, and recommends tours — all using real Google APIs and web search.

## Architecture

```
                    ┌──────────────────────────┐
                    │    Orchestrator Agent     │
                    │  (coordinates trip plan)  │
                    └──────────┬───────────────┘
                               │
    ┌──────────┬───────────────┼───────────────┬──────────┐
    │          │               │               │          │
┌───▼───┐ ┌───▼────┐ ┌────────▼──────┐ ┌──────▼───┐ ┌───▼────┐
│Flight │ │ Route  │ │    Hotel     │ │Activities│ │ Tour  │
│Agent  │ │Planner │ │    Agent     │ │  Agent   │ │ Agent │
│       │ │        │ │              │ │          │ │       │
│Google │ │Google  │ │Google Places │ │Google    │ │Google │
│Search │ │Maps    │ │API (lodging) │ │Places API│ │Search │
│Ground.│ │Direct. │ │ratings,price │ │attract., │ │Ground.│
│       │ │API     │ │reviews       │ │food,fun  │ │       │
└───────┘ └────────┘ └──────────────┘ └──────────┘ └───────┘
```

## What Each Agent Does

| Agent | Role | Data Source |
|-------|------|-------------|
| **Orchestrator** | Routes requests, coordinates multi-step planning, composes final itinerary | ADK sub-agent delegation |
| **Flight Agent** | Searches flights between cities, compares prices, suggests options | Gemini web search grounding |
| **Route Planner** | Plans driving routes, calculates times/distances, suggests scenic routes | Google Maps Directions API |
| **Hotel Agent** | Finds hotels at each stop, shows ratings/prices/reviews | Google Places API |
| **Activities Agent** | Discovers attractions, restaurants, parks, hidden gems at each location | Google Places API |
| **Tour Agent** | Finds guided tours, day trips, adventure/food/historical experiences | Gemini web search grounding |

## Demo Flow (3 Acts, ~45 min)

| Act | What Happens | Products Showcased | Time |
|-----|-------------|-------------------|------|
| **Act 1: Build** | agy CLI autonomously builds 6-agent app from a single `/goal` prompt | AGY CLI, Google ADK | 15-20 min |
| **Act 2: Deploy** | agy deploys to GEAP via `agents-cli scaffold` + `agents-cli deploy` | AGY CLI, agents-cli, GEAP |10 min |
| **Act 3: Run** | Query the deployed agent, plan a real road trip | GEAP Runtime, Console Playground | 10 min |

## Prerequisites

```bash
# Install tools
pip install google-adk google-agents-cli googlemaps

# Verify versions
adk --version        # 2.0.0+
agents-cli --version # 0.2.0+

# Configure GCP
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login

# Enable APIs
gcloud services enable aiplatform.googleapis.com
gcloud services enable places-backend.googleapis.com
gcloud services enable geocoding-backend.googleapis.com
gcloud services enable maps-backend.googleapis.com

# Get a Google Maps API key
# https://console.cloud.google.com/apis/credentials
```

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/agylabs/trip-planner.git
cd trip-planner
cp .env.example .env
# Edit .env: set your project ID and Maps API key
```

### 2. Build with AGY CLI (Act 1)

Launch agy and paste the build prompt:

```bash
agy --dangerously-skip-permissions
```

```
/goal Build a complete multi-agent Road Trip Planner application using Google ADK
(google-adk v2.0.0) in this directory. The app helps users plan road trips with real
data from Google APIs and web search. Create 6 agents: Orchestrator, Flight Agent,
Route Planner, Hotel Agent, Activities Agent, Tour Agent...
```

See [docs/demo-guide.md](docs/demo-guide.md) for the full prompt.

### 3. Deploy to GEAP (Act 2)

In the same agy session:

```
Now deploy this Road Trip Planner Agent to Google's Gemini Enterprise Agent Platform (GEAP).
Use GCP project YOUR_PROJECT_ID in us-central1...
```

### 4. Demo on GEAP (Act 3)

After deployment, interact via the **GEAP Console Playground** or the local web UI:

```bash
# Local web UI (built by agy)
python server.py
# Open http://localhost:8000

# Or use the GEAP Console Playground
# https://console.cloud.google.com/vertex-ai/agents/agent-engines/...
```

### 5. Publish to Gemini Enterprise (Optional)

```bash
agents-cli publish gemini-enterprise
```

This registers the agent in the Gemini Enterprise catalog, making it discoverable by org users in the Gemini Enterprise web app.

## Example Queries

- *"Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur"*
- *"Find the best flights from New York to Miami for next weekend"*
- *"What are the best things to do in Monterey? Include hidden gems and local food spots"*
- *"Find adventure tours and wine tasting experiences in the Napa Valley area"*
- *"Plan a scenic drive from Portland to Seattle with hotel stops"*

## Project Structure

```
trip-planner/
├── trip_planner/                # Agent source (local development)
│   ├── __init__.py
│   ├── agent.py                 # Root orchestrator
│   ├── tools.py                 # Google Maps/Places tools + VertexGemini
│   └── sub_agents/
│       ├── flight_agent.py      # Flight search (web grounding)
│       ├── route_planner.py     # Driving routes (Maps Directions API)
│       ├── hotel_agent.py       # Hotel search (Places API)
│       ├── activities_agent.py  # Things to do (Places API)
│       └── tour_agent.py        # Tours & experiences (web grounding)
├── app/                         # Deployment package (for GEAP)
│   ├── agent.py                 # GEAP entrypoint
│   ├── agent_runtime_app.py     # Runtime wrapper
│   └── trip_planner/            # Agent code (for deployment)
├── server.py                    # Local FastAPI web server
├── static/                      # Web UI (HTML/CSS/JS)
├── deployment/                  # Terraform configs
├── tests/                       # Test scaffolding
├── pyproject.toml
├── agents-cli-manifest.yaml
└── docs/                        # Documentation
```

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/demo-guide.md](docs/demo-guide.md) | Complete step-by-step demo playbook |
| [docs/architecture.md](docs/architecture.md) | Architecture diagram + agent details |
| [docs/prompt-log.md](docs/prompt-log.md) | Exact prompts sent to agy |
| [docs/friction-log.md](docs/friction-log.md) | Issues encountered + workarounds |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `400 INVALID_ARGUMENT` mixing Google Search + tools | ADK wraps search in a sub-agent when `bypass_multi_tools_limit=True`. Add a helper tool to trigger this. |
| `ImportError: google.cloud.logging` | Add `google-cloud-logging` to `pyproject.toml` and run `uv lock` |
| `Event loop is closed` in GEAP | Use loop-aware caching in VertexGemini (see `tools.py`) |
| Maps API returns empty results | Ensure Maps/Places/Geocoding APIs are enabled and API key is set |
| agy quota exhausted | Model quotas reset periodically. Use `--model` flag to try a different model. |

## License

This project is intended for demonstration purposes.
