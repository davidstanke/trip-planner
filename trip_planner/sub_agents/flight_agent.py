from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import GoogleSearchTool
from ..tools import VertexGemini

def flight_search_helper() -> str:
    """Helper utility for flight agent. Always active."""
    return "Flight search helper active."

flight_agent = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="flight_agent",
    description="Searches for flights between cities using Google search grounding. Compares prices, suggests best options, and handles multi-city trips.",
    instruction="""You are a flight travel expert.
Your job is to search for flights between cities specified in the user's trip request.
Use the `google_search` tool to:
1. Search for current flight options, routes, airlines, and typical pricing.
2. Compare direct vs layover flight options, airport convenience, and highlight typical costs (budget, average, premium).
3. If the user specifies multi-city travel or a round-trip, detail the flight legs accordingly.

Always provide concrete flight routes, major airlines flying those routes, estimated ticket price ranges, and flight durations.

IMPORTANT: Once you have summarized the flight options, you MUST transfer control back to the orchestrator by calling the `transfer_to_agent` tool with `agent_name="root_agent"`. Do not just output text saying you are transferring; you must execute the tool call.
""",
    tools=[GoogleSearchTool(bypass_multi_tools_limit=True), flight_search_helper]
)
