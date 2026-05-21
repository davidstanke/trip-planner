from google.adk.agents.llm_agent import Agent
from google.adk.tools.google_search_tool import GoogleSearchTool
from ..tools import VertexGemini

def tour_search_helper() -> str:
    """Helper utility for tour agent. Always active."""
    return "Tour search helper active."

tour_agent = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="tour_agent",
    description="Finds guided tours, day trips, and unique experiences at destinations using web search grounding.",
    instruction="""You are a travel coordinator specialized in booking tours and guided experiences.
Your job is to search for guided tours, day trips, excursions, and ticketed experiences at the road trip destinations using `google_search`.
Use the `google_search` tool to:
1. Search for guided tours (e.g. boat tours, whale watching, historical walking tours, wine tasting, guided hikes).
2. Detail the tour description, typical price ranges, duration, and local tour operators.
3. Suggest unique experiences (e.g., helicopter tours, food tastings, surf lessons).

Provide at least 1-2 distinct tour ideas or guided experiences for each stop.

IMPORTANT: Once you have summarized the tour options, you MUST transfer control back to the orchestrator by calling the `transfer_to_agent` tool with `agent_name="root_agent"`. Do not just output text saying you are transferring; you must execute the tool call.
""",
    tools=[GoogleSearchTool(bypass_multi_tools_limit=True), tour_search_helper]
)
