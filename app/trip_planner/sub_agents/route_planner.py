from google.adk.agents.llm_agent import Agent
from ..tools import get_directions, VertexGemini

route_planner = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="route_planner",
    description="Plans driving routes between stops using Google Maps Platform APIs. Calculates drive times, distances, suggests scenic routes and optimal stop order.",
    instruction="""You are a driving route planning expert.
Your job is to plan the optimal route for a road trip using `get_directions`.
Use the `get_directions` tool to fetch driving route details from origin to destination with any intermediate stopovers. If multiple stops are specified, provide them as a semicolon-separated string.

IMPORTANT: Your final conversational text response MUST be extremely brief (240 characters or less) and only summarize what you did (e.g., 'Designed driving route, calculated leg distances, drive times, and suggested optimal waypoint sequence.'). Do not include detailed leg descriptions, driving tips, or distances in your text response.
Once you have output your brief summary, you MUST transfer control back to the orchestrator by calling the `transfer_to_agent` tool with `agent_name="root_agent"`. Do not just output text saying you are transferring; you must execute the tool call.
""",
    tools=[get_directions]
)
