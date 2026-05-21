import os
import sys
import json
import urllib.request
import subprocess

def get_identity_token(url):
    """Retrieves an identity token using gcloud as specified."""
    print(f"Retrieving identity token for audience: {url} via gcloud")
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token", f"--audiences={url}"],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()

def test_config(url, token):
    """Tests the /api/config endpoint."""
    print("\n--- Testing /api/config ---")
    req = urllib.request.Request(f"{url}/api/config")
    req.add_header("Authorization", f"Bearer {token}")
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            print("Config Response:", data)
            if "maps_api_key" in data and data["maps_api_key"] == "YOUR_MAPS_API_KEY":
                print("✅ /api/config passed. Maps API key matches.")
            else:
                print("❌ /api/config failed. Missing or incorrect maps API key.")
    except Exception as e:
        print(f"❌ /api/config request failed: {e}")

def test_plan_sse(url, token):
    """Tests the /api/plan SSE endpoint."""
    print("\n--- Testing /api/plan (SSE Stream) ---")
    query = "Plan a 3 day road trip from Seattle to Portland"
    encoded_query = urllib.parse.quote_plus(query)
    
    req = urllib.request.Request(f"{url}/api/plan?query={encoded_query}")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "text/event-stream")
    
    found_hotel = False
    found_activity = False
    found_route = False

    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                decoded_line = line.decode("utf-8").strip()
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    try:
                        data = json.loads(data_str)
                        if data.get("type") == "event" and "text" in data:
                            text = data["text"]
                            print(f"[{data.get('author', 'unknown')}] {text}")
                            
                            if "**Hotel:**" in text or "Hotel:" in text or "Accommodation:" in text:
                                found_hotel = True
                            if "**Activity:**" in text or "Activity:" in text or "Tour:" in text:
                                found_activity = True
                            if "**Drive:**" in text or "Drive:" in text or "Distance:" in text:
                                found_route = True
                                
                        elif data.get("type") == "status":
                            print(f"[STATUS] {data.get('message')}")
                        elif data.get("type") == "error":
                            print(f"❌ [ERROR] {data.get('message')}")
                    except json.JSONDecodeError:
                        print(f"Could not parse JSON from line: {data_str}")
                        
        print("\n--- SSE Stream Complete ---")
        if found_hotel:
            print("✅ Agent returned hotel recommendations.")
        else:
            print("❌ Agent did not return hotel recommendations.")
            
        if found_activity:
            print("✅ Agent returned activity recommendations.")
        else:
            print("❌ Agent did not return activity recommendations.")
            
        if found_route:
            print("✅ Agent returned route/drive segments.")
        else:
            print("❌ Agent did not return route/drive segments.")
            
    except Exception as e:
        print(f"❌ /api/plan request failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_deployment.py <CLOUD_RUN_URL>")
        sys.exit(1)
        
    url = sys.argv[1].rstrip("/")
    try:
        token = get_identity_token(url)
        test_config(url, token)
        test_plan_sse(url, token)
    except subprocess.CalledProcessError as e:
        print(f"Failed to get identity token: {e.stderr}")
