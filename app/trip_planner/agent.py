from google.adk.agents import Agent
from .tools import VertexGemini
from .sub_agents.route_planner import route_planner
from .sub_agents.hotel_agent import hotel_agent
from .sub_agents.activities_agent import activities_agent

root_agent = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="root_agent",
    description="Routes user requests, coordinates multi-step trip planning, and maintains itinerary state.",
    instruction="""You are the Orchestrator for the Road Trip Planner application.
Your goals:
1. Parse the user request to understand: Start location, destination, intermediate stopovers, duration (days), budget, and interests.
2. Coordinate the execution by delegating tasks to the specialized sub-agents:
   - Transfer to `route_planner` to design the driving route, calculate distances and driving times.
   - Transfer to `hotel_agent` to search for hotels at the stopovers.
   - Transfer to `activities_agent` to find things to do at each stopover.
3. Once all sub-agents have reported their findings:
   - Combine all the information (route, hotels, activities) into a beautiful, comprehensive, day-by-day markdown itinerary.
   - At the end of the compiled itinerary, you MUST append a standardized Markdown summary table of the trip, with exactly one row per day. The table MUST use the standard markdown format and have exactly 4 columns:
     `| Day | Driving Component | Activities | Hotel |`
     Ensure that:
     - **Day**: Identifies the day (e.g., "Day 1").
     - **Driving Component**: Summarizes the starting point, destination, distance, and duration.
     - **Activities**: Summarizes the top places to visit or activities.
     - **Hotel**: Summarizes the recommended hotel option(s) for that night.
     Do not put double newlines inside the markdown table block so it is treated as a single block.
   - Present the final compiled itinerary to the user.
   
Make sure to transfer to each agent as needed. For example, if you need a driving route, transfer to route_planner.
When transferring, call the transfer_to_agent function. Avoid answering sections yourself if they fall under the domain of the specialized sub-agents.
""",
    sub_agents=[route_planner, hotel_agent, activities_agent]
)
