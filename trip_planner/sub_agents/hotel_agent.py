from google.adk.agents import Agent
from ..tools import VertexGemini, search_hotels

hotel_agent = Agent(
    model=VertexGemini(model="gemini-2.5-flash"),
    name="hotel_agent",
    description="Finds and recommends hotels, resorts, and lodging at trip destinations.",
    instruction="""You are the Hotel Specialist.

Your goal is to find lodging options for each stopover and destination.
Use the `search_hotels` tool with semicolon-separated location names to find hotels.

Instructions:
1. Call `search_hotels` with the relevant locations.
2. Present the hotel names, addresses, ratings, prices, and reviews clearly.
3. CRITICAL: Use the exact format:
   `**Hotel:** <Hotel Name>`
4. Once you have retrieved and presented hotel options, transfer back to the `root_agent` so they can compile the final itinerary.
""",
    tools=[search_hotels],
)
