# Road Trip Planner — Architecture

## System Overview

The Road Trip Planner is a 6-agent AI system that plans road trips using real Google APIs and web search. Users describe a trip in natural language; the agents coordinate to find flights, plan routes, book hotels, discover activities, and recommend tours.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          ROAD TRIP PLANNER AGENT                                     │
│                          Gemini Enterprise Agent Platform (GEAP)                     │
│                                                                                      │
│  ┌────────────────────────────────────────────────────────────────────────────────┐   │
│  │                         ORCHESTRATOR (root_agent)                             │   │
│  │                         Model: Gemini 2.5 Flash via Vertex AI                │   │
│  │                                                                               │   │
│  │  Receives trip planning requests in natural language.                         │   │
│  │  Decomposes into sub-tasks and delegates to specialist agents.               │   │
│  │  Composes the final day-by-day itinerary from all agent outputs.             │   │
│  │  Maintains trip context via GEAP session persistence.                        │   │
│  └──────┬──────────┬───────────┬───────────┬──────────┬─────────────────────────┘   │
│         │          │           │           │          │                               │
│  ┌──────▼───┐ ┌────▼────┐ ┌───▼──────┐ ┌──▼───────┐ ┌▼─────────┐                   │
│  │  FLIGHT  │ │  ROUTE  │ │  HOTEL   │ │ACTIVITIES│ │   TOUR   │                   │
│  │  AGENT   │ │ PLANNER │ │  AGENT   │ │  AGENT   │ │  AGENT   │                   │
│  │          │ │         │ │          │ │          │ │          │                   │
│  │ Searches │ │ Plans   │ │ Finds    │ │Discovers │ │ Finds    │                   │
│  │ flights  │ │ driving │ │ hotels   │ │things to │ │ guided   │                   │
│  │ between  │ │ routes  │ │ at each  │ │do: food, │ │ tours,   │                   │
│  │ cities.  │ │ between │ │ stop.    │ │attract., │ │ day trips│                   │
│  │ Compares │ │ stops.  │ │ Shows    │ │parks,    │ │ adventure│                   │
│  │ prices & │ │ Drive   │ │ ratings, │ │hidden    │ │ food &   │                   │
│  │ options. │ │ times,  │ │ prices,  │ │gems,     │ │ history  │                   │
│  │          │ │ scenic  │ │ reviews. │ │nightlife.│ │ walks.   │                   │
│  └────┬─────┘ └────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘                   │
│       │            │           │            │            │                           │
│  ┌────▼────┐  ┌────▼──────┐  ┌▼────────────▼──┐    ┌────▼────┐                     │
│  │ Gemini  │  │  Google   │  │  Google Places  │    │ Gemini  │                     │
│  │  Web    │  │  Maps     │  │  API (New)      │    │  Web    │                     │
│  │ Search  │  │ Directions│  │  Nearby Search  │    │ Search  │                     │
│  │Grounding│  │  API      │  │  Text Search    │    │Grounding│                     │
│  └─────────┘  └───────────┘  └─────────────────┘    └─────────┘                     │
│                                                                                      │
└──────────────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          GEAP RUNTIME SERVICES                                       │
│                                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐     │
│  │   Sessions   │  │  Cloud Trace │  │ Agent        │  │ Gemini Enterprise   │     │
│  │   Per-user   │  │  Execution   │  │ Registry     │  │ Catalog             │     │
│  │   trip state │  │  tracing &   │  │ Version      │  │ Discoverable by     │     │
│  │   across     │  │  debugging   │  │ lifecycle    │  │ org users in the    │     │
│  │   turns      │  │              │  │ management   │  │ Gemini web app      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Agent Descriptions

### Orchestrator (root_agent)
- **Role**: Trip planning coordinator
- **Model**: Gemini 2.5 Flash (Vertex AI)
- **Behavior**: Receives trip requests, breaks them into sub-tasks (flights, routes, hotels, activities, tours), delegates to specialist agents via `transfer_to_agent`, and composes the final day-by-day itinerary

### Flight Agent
- **Role**: Flight search and comparison
- **Data Source**: Gemini web search grounding (real-time flight data)
- **Capabilities**: Searches flights between cities, compares prices across airlines, suggests best options for dates/budget, handles multi-city trips

### Route Planner
- **Role**: Driving route optimization
- **Data Source**: Google Maps Directions API (via `googlemaps` Python client)
- **Tools**: `get_directions(origin, destination)` — returns distance, duration, step-by-step directions, polyline
- **Capabilities**: Plans optimal driving routes, calculates drive times and distances, suggests scenic alternatives

### Hotel Agent
- **Role**: Accommodation search
- **Data Source**: Google Places API (nearby search for lodging)
- **Tools**: `search_hotels(location, radius)` — returns hotels with name, address, rating, price level, user ratings
- **Capabilities**: Finds hotels at each destination, filters by price/rating, shows reviews

### Activities Agent
- **Role**: Things-to-do discovery
- **Data Source**: Google Places API (tourist attractions, restaurants, entertainment)
- **Tools**: `search_places(location, query, radius)` — returns places with details
- **Capabilities**: Discovers attractions, restaurants, parks, entertainment, hidden gems, local food scenes, nightlife

### Tour Agent
- **Role**: Guided tour and experience finder
- **Data Source**: Gemini web search grounding (real-time tour availability)
- **Capabilities**: Finds guided tours, day trips, adventure tours, food tours, historical walks, outdoor excursions, wine tastings

---

## Key Technical Details

### Google Search Grounding Workaround

Vertex AI doesn't allow mixing Google Search grounding with custom tools (including transfer tools) in a single agent. ADK solves this with `GoogleSearchTool(bypass_multi_tools_limit=True)`, which wraps the search in a sub-agent. The Flight and Tour agents include a small helper tool to trigger this wrapping behavior.

### VertexGemini Model Class

All agents use a custom `VertexGemini` subclass that configures the Gemini client for Vertex AI authentication via Application Default Credentials. Includes loop-aware caching to handle GEAP's serverless event loop lifecycle.

### Local Web UI

agy also built a local FastAPI web server (`server.py`) with an HTML/CSS/JS frontend (`static/`) for interactive trip planning outside of GEAP.

---

## GCP Services Used

| Service | Role |
|---------|------|
| **Vertex AI (Gemini 2.5 Flash)** | Powers all agent reasoning |
| **GEAP Agent Runtime** | Production hosting (serverless) |
| **GEAP Sessions** | Per-user trip state persistence |
| **Google Maps Directions API** | Driving route calculation |
| **Google Places API** | Hotel and activity search |
| **Gemini Web Search Grounding** | Real-time flight and tour data |
| **Cloud Storage** | Deployment artifact staging |
| **Artifact Registry** | Container image storage |
| **Cloud Trace** | Agent execution tracing |

---

## Example Queries

**Full Trip Planning**
- *"Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur"*
- *"Plan a weekend getaway from Portland to Seattle with scenic stops"*
- *"Create a 7-day California wine country road trip starting from San Francisco"*

**Flights**
- *"Find the cheapest flights from New York to Miami for next weekend"*
- *"Compare flight options from Chicago to Denver in July"*

**Routes**
- *"What's the fastest driving route from LA to Las Vegas?"*
- *"Plan a scenic coastal drive from Monterey to Big Sur"*

**Hotels**
- *"Find pet-friendly hotels in Santa Cruz under $200/night"*
- *"What are the best-rated hotels in downtown Monterey?"*

**Activities**
- *"What are the best things to do in Big Sur?"*
- *"Find hidden gem restaurants in Santa Cruz"*
- *"What outdoor activities are available in Yosemite?"*

**Tours**
- *"Find wine tasting tours in Napa Valley"*
- *"What adventure tours are available in Big Sur?"*
- *"Are there any whale watching tours from Monterey?"*
