import os
import sys
from dotenv import load_dotenv

# Load env variables from .env
load_dotenv()

# Add workspace directory to python path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from google.adk.runners import InMemoryRunner, print_event
from google.genai import types
from trip_planner.agent import root_agent

def main():
    print("Initializing InMemoryRunner with root_agent...")
    runner = InMemoryRunner(agent=root_agent)
    runner.auto_create_session = True
    
    query = (
        "Plan a 5-day road trip from San Francisco to Los Angeles with stops in Santa Cruz, Monterey, and Big Sur. "
        "Find flights, hotels, activities, and tours at each stop."
    )
    print(f"User Query:\n{query}\n")
    
    new_message = types.Content(parts=[types.Part.from_text(text=query)])
    
    print("Starting agent execution...\n" + "="*50)
    try:
        events = runner.run(
            user_id="test_user",
            session_id="session_123",
            new_message=new_message
        )
        for event in events:
            print_event(event, verbose=True)
        print("="*50 + "\nAgent execution completed.")
    except Exception as e:
        print(f"\nExecution failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
