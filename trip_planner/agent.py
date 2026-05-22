from google.adk.agents import Agent
from .tools import VertexGemini
from .sub_agents.flight_agent import flight_agent
from .sub_agents.route_planner import route_planner
from .sub_agents.hotel_agent import hotel_agent
from .sub_agents.activities_agent import activities_agent
from .sub_agents.tour_agent import tour_agent

root_agent = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="root_agent",
    description="Routes user requests, coordinates multi-step trip planning, and maintains itinerary state.",
    instruction="""You are the Orchestrator for the Road Trip Planner application.
Your goals:
1. Parse the user request to understand: Start location, destination, intermediate stopovers, duration (days), budget, and interests.
2. Coordinate the execution by delegating tasks to the specialized sub-agents:
   - Transfer to `flight_agent` to search for flights between the cities.
   - Transfer to `route_planner` to design the driving route, calculate distances and driving times.
   - Transfer to `hotel_agent` to search for hotels at the stopovers.
   - Transfer to `activities_agent` to find things to do at each stopover.
   - Transfer to `tour_agent` to find guided tours and unique experiences.
3. Once all sub-agents have reported their findings:
   - Combine all the information (flights, route, hotels, activities, tours) into a beautiful, comprehensive, day-by-day markdown itinerary.
   - Present the final compiled itinerary to the user.
   
Make sure to transfer to each agent as needed. For example, if you need flights, transfer to flight_agent. If you need a driving route, transfer to route_planner.
When transferring, call the transfer_to_agent function. Avoid answering sections yourself if they fall under the domain of the specialized sub-agents.
""",
    sub_agents=[flight_agent, route_planner, hotel_agent, activities_agent, tour_agent]
)
