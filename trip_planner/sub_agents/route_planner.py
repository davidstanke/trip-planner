from google.adk.agents import Agent
from ..tools import VertexGemini, get_directions

route_planner = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="route_planner",
    description="Plans driving routes, distances, and driving durations between stopovers.",
    instruction="""You are the Route Planner Specialist.

Your goal is to plan driving routes between stops using Google Maps Platform APIs.
Use the `get_directions` tool to calculate optimal driving paths, drive times, and distances.

Instructions:
1. Call `get_directions` with the origin, destination, and any intermediate stops.
2. Present the calculated drive times, distances, and suggestions for scenic routes or optimal stop order.
3. CRITICAL: Use the exact format:
   `**Drive:** From <Origin> to <Destination> - <Distance> miles, <Duration> hours`
4. Once you have retrieved and presented the directions, transfer back to the `root_agent` so they can compile the final itinerary.
""",
    tools=[get_directions],
)
