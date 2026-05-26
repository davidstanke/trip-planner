import os
import vertexai
from vertexai import agent_engines

def main():
    print("Initializing Vertex AI...")
    vertexai.init(project="YOUR_PROJECT_ID", location="us-central1")
    
    engine_id = "projects/YOUR_PROJECT_NUMBER/locations/us-central1/reasoningEngines/YOUR_AGENT_ID"
    print(f"Retrieving agent engine: {engine_id}")
    engine = agent_engines.get(engine_id)
    
    print("Creating session...")
    session = engine.create_session(user_id="test-user")
    session_id = session["id"]
    print(f"Session created with ID: {session_id}")
    
    query = "Plan a 2-day trip from San Francisco to Monterey"
    print(f"Sending query: {query}")
    
    for i, event in enumerate(engine.stream_query(user_id="test-user", session_id=session_id, message=query)):
        print(f"\n--- Event {i} ---")
        print(f"Type: {type(event)}")
        print(f"Attributes: {dir(event)}")
        try:
            print(f"Repr: {repr(event)}")
        except Exception as e:
            print(f"Repr failed: {e}")
        try:
            print(f"__dict__: {event.__dict__}")
        except Exception as e:
            print(f"__dict__ failed: {e}")
        print("-" * 30)

if __name__ == "__main__":
    main()
