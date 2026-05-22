import os
import json
import asyncio
import urllib.request
import urllib.parse
from functools import cached_property
from google.adk.models import Gemini
from google.genai import Client
import googlemaps

class VertexGemini(Gemini):
    """Subclass of Gemini model utilizing Vertex AI with loop-aware client caching."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_loop = None
        self._cached_api_client = None
        self._cached_live_api_client = None

    @property
    def api_client(self) -> Client:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not self._current_loop or self._cached_api_client is None:
            self._current_loop = loop
            self._cached_api_client = Client(vertexai=True)
        return self._cached_api_client

    @property
    def _live_api_client(self) -> Client:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop is not self._current_loop or self._cached_live_api_client is None:
            self._current_loop = loop
            self._cached_live_api_client = Client(vertexai=True)
        return self._cached_live_api_client


# Mock databases for keyless fallback simulation
MOCK_HOTELS = {
    "san francisco": [
        {"name": "The Westin St. Francis", "address": "335 Powell St, San Francisco, CA", "rating": 4.4, "price_level": 3, "reviews_count": 4200},
        {"name": "Fairmont San Francisco", "address": "950 Mason St, San Francisco, CA", "rating": 4.6, "price_level": 4, "reviews_count": 2800}
    ],
    "santa cruz": [
        {"name": "Dream Inn Santa Cruz", "address": "175 W Cliff Dr, Santa Cruz, CA", "rating": 4.5, "price_level": 3, "reviews_count": 1250},
        {"name": "Sea & Sand Inn", "address": "201 W Cliff Dr, Santa Cruz, CA", "rating": 4.7, "price_level": 2, "reviews_count": 890}
    ],
    "monterey": [
        {"name": "Monterey Plaza Hotel & Spa", "address": "400 Cannery Row, Monterey, CA", "rating": 4.6, "price_level": 4, "reviews_count": 2100},
        {"name": "Portola Hotel & Spa at Monterey Bay", "address": "2 Portola Plaza, Monterey, CA", "rating": 4.3, "price_level": 3, "reviews_count": 3400}
    ],
    "big sur": [
        {"name": "Ventana Big Sur - An Alila Resort", "address": "48123 Highway 1, Big Sur, CA", "rating": 4.8, "price_level": 4, "reviews_count": 950},
        {"name": "Post Ranch Inn", "address": "47900 Highway 1, Big Sur, CA", "rating": 4.9, "price_level": 4, "reviews_count": 680},
        {"name": "Big Sur Campground & Cabins", "address": "47000 Highway 1, Big Sur, CA", "rating": 4.4, "price_level": 2, "reviews_count": 510}
    ],
    "los angeles": [
        {"name": "The Beverly Hills Hotel", "address": "9641 Sunset Blvd, Beverly Hills, CA", "rating": 4.7, "price_level": 4, "reviews_count": 3100},
        {"name": "Freehand Los Angeles", "address": "416 W 8th St, Los Angeles, CA", "rating": 4.1, "price_level": 1, "reviews_count": 2500}
    ]
}

MOCK_ACTIVITIES = {
    "san francisco": [
        {"name": "Golden Gate Bridge", "address": "Golden Gate Bridge, San Francisco, CA", "rating": 4.8, "type": "landmark", "reviews_count": 85000},
        {"name": "Alcatraz Island", "address": "San Francisco Bay, San Francisco, CA", "rating": 4.7, "type": "museum", "reviews_count": 42000}
    ],
    "santa cruz": [
        {"name": "Santa Cruz Beach Boardwalk", "address": "400 Beach St, Santa Cruz, CA", "rating": 4.6, "type": "amusement_park", "reviews_count": 18500},
        {"name": "Natural Bridges State Beach", "address": "2531 W Cliff Dr, Santa Cruz, CA", "rating": 4.7, "type": "park", "reviews_count": 4600}
    ],
    "monterey": [
        {"name": "Monterey Bay Aquarium", "address": "886 Cannery Row, Monterey, CA", "rating": 4.8, "type": "aquarium", "reviews_count": 32000},
        {"name": "Cannery Row", "address": "Cannery Row, Monterey, CA", "rating": 4.5, "type": "tourist_attraction", "reviews_count": 15000}
    ],
    "big sur": [
        {"name": "McWay Falls", "address": "Julia Pfeiffer Burns State Park, Big Sur, CA", "rating": 4.8, "type": "waterfall", "reviews_count": 3100},
        {"name": "Bixby Creek Bridge", "address": "Highway 1, Big Sur, CA", "rating": 4.8, "type": "bridge", "reviews_count": 4800},
        {"name": "Pfeiffer Beach", "address": "Sycamore Canyon Rd, Big Sur, CA", "rating": 4.7, "type": "beach", "reviews_count": 2200}
    ],
    "los angeles": [
        {"name": "Griffith Observatory", "address": "2800 E Observatory Rd, Los Angeles, CA", "rating": 4.7, "type": "planetarium", "reviews_count": 38000},
        {"name": "Getty Center", "address": "1200 Getty Center Dr, Los Angeles, CA", "rating": 4.8, "type": "art_museum", "reviews_count": 21000}
    ]
}


def _parse_stopovers(stopovers_semicolon_separated: str = "", stopovers: str = "") -> list[str]:
    waypoints_raw = []
    if stopovers_semicolon_separated:
        waypoints_raw.append(stopovers_semicolon_separated)
    if stopovers:
        waypoints_raw.append(stopovers)
        
    def parse_item(item) -> list:
        if not item:
            return []
        if isinstance(item, str):
            if ";" in item:
                return [s.strip() for s in item.split(";") if s.strip()]
            return [item.strip()]
        elif isinstance(item, list) or isinstance(item, tuple):
            parsed = []
            for sub_item in item:
                parsed.extend(parse_item(sub_item))
            return parsed
        elif isinstance(item, dict):
            for key in ["address", "name", "location"]:
                if key in item and isinstance(item[key], str):
                    return [item[key].strip()]
            return [str(item)]
        else:
            return [str(item).strip()]
            
    waypoints = []
    for item in waypoints_raw:
        waypoints.extend(parse_item(item))
    return waypoints


def _get_fallback_directions(origin: str, destination: str, stopovers: list[str]) -> dict:
    """Generates high-fidelity simulated driving directions using Gemini 2.5 Flash."""
    try:
        client = Client(vertexai=True)
        stopovers_desc = ", ".join(stopovers) if stopovers else "no stopovers"
        prompt = f"""Estimate realistic driving directions from "{origin}" to "{destination}" with intermediate stopovers: {stopovers_desc}.
        
        Generate a JSON response that matches this structure exactly:
        {{
            "total_distance_miles": float,
            "total_duration_hours": float,
            "legs": [
                {{
                    "leg_index": 1,
                    "start": "start location",
                    "end": "end location",
                    "distance": "e.g., '100 miles'",
                    "duration": "e.g., '2.0 hours'"
                }}
            ],
            "waypoint_order": list of indices in optimized stopover order (e.g., [0, 1] if there are 2 stopovers, or [] if none),
            "summary": "e.g., 'I-90 E / I-94 E'"
        }}
        
        Note: The waypoint_order list must contain 0-based indices mapping to the stopovers in their optimized order.
        Return ONLY valid JSON. Do not include markdown code block formatting or any other text.
        """
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = response.text.strip()
        if text.startswith("```"):
            if text.startswith("```json"):
                text = text[7:]
            else:
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
            
        data = json.loads(text)
        print(f"[Info] Dynamically simulated route for '{origin}' -> '{destination}' using Gemini.")
        return data
    except Exception as e:
        print(f"[Warning] Failed to generate dynamic fallback route via Gemini: {str(e)}")
        # Default static fallback
        return {
            "total_distance_miles": 453.2,
            "total_duration_hours": 9.8,
            "legs": [
                {"leg_index": 1, "start": origin, "end": destination, "distance": "453.2 miles", "duration": "9.8 hours"}
            ],
            "waypoint_order": list(range(len(stopovers))),
            "summary": "Simulated Route"
        }


def get_directions(origin: str, destination: str, stopovers_semicolon_separated: str = "", stopovers: str = "") -> dict:
    """Plans driving routes between stops using Google Maps Platform Directions API.
    
    Calculates driving times, total distances, route summary, and optimal stop order.
    
    Args:
        origin: The starting address or city name (e.g., 'San Francisco, CA').
        destination: The ending address or city name (e.g., 'Los Angeles, CA').
        stopovers_semicolon_separated: Semicolon-separated list of stops between origin and destination.
                                       Example: 'Santa Cruz, CA; Monterey, CA; Big Sur, CA'
        stopovers: Alternative parameter for semicolon-separated or list of stops.
                                       
    Returns:
        A dictionary containing total distance, duration, leg details, and waypoint order.
    """
    parsed_stopovers = _parse_stopovers(stopovers_semicolon_separated, stopovers)
    
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or "YOUR_MAPS_API_KEY"
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        print("[Warning] GOOGLE_MAPS_API_KEY not found or default. Using dynamic simulated Directions route.")
        return _get_fallback_directions(origin, destination, parsed_stopovers)
        
    try:
        gmaps = googlemaps.Client(key=api_key)
        
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            waypoints=parsed_stopovers,
            optimize_waypoints=True,
            mode="driving"
        )
        
        if not directions_result:
            print(f"[Warning] No driving route found via Google Maps Directions API. Falling back to dynamic simulation.")
            return _get_fallback_directions(origin, destination, parsed_stopovers)
            
        route = directions_result[0]
        
        total_distance_meters = 0
        total_duration_seconds = 0
        legs_summary = []
        
        for i, leg in enumerate(route.get("legs", [])):
            leg_distance = leg.get("distance", {}).get("text", "0 km")
            leg_duration = leg.get("duration", {}).get("text", "0 hours")
            start_addr = leg.get("start_address", "")
            end_addr = leg.get("end_address", "")
            
            total_distance_meters += leg.get("distance", {}).get("value", 0)
            total_duration_seconds += leg.get("duration", {}).get("value", 0)
            
            legs_summary.append({
                "leg_index": i + 1,
                "start": start_addr,
                "end": end_addr,
                "distance": leg_distance,
                "duration": leg_duration
            })
            
        total_distance_miles = round((total_distance_meters / 1609.34), 1)
        total_duration_hours = round(total_duration_seconds / 3600.0, 1)
        
        return {
            "total_distance_miles": total_distance_miles,
            "total_duration_hours": total_duration_hours,
            "legs": legs_summary,
            "waypoint_order": route.get("waypoint_order", []),
            "summary": route.get("summary", "")
        }
    except Exception as e:
        print(f"[Warning] Google Maps Directions API call failed: {str(e)}. Falling back to dynamic simulated Directions route.")
        return _get_fallback_directions(origin, destination, parsed_stopovers)


def search_hotels(location: str) -> dict:
    """Searches for hotels, lodgings, and resorts at a destination using the Google Places API (New).
    
    Shows hotel name, full address, average rating, price tier (if available), and reviews count.
    
    Args:
        location: The city/area name to search for hotels (e.g. 'Santa Cruz, CA').
        
    Returns:
        A dictionary listing hotels with names, ratings, addresses, and price levels.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or "YOUR_MAPS_API_KEY"
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        print(f"[Warning] GOOGLE_MAPS_API_KEY not found or default. Using simulated Places (New) search for hotels in: {location}")
        for key in MOCK_HOTELS:
            if key in location.lower():
                return {"hotels": MOCK_HOTELS[key]}
        return {"hotels": [
            {"name": f"Grand Central Hotel at {location}", "address": f"100 Main St, {location}", "rating": 4.2, "price_level": 2, "reviews_count": 120}
        ]}
        
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.userRatingCount"
    }
    body = {
        "textQuery": f"best lodging hotels resorts in {location}"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            places = res_data.get("places", [])
            
            results = []
            for p in places[:5]:
                display_name = p.get("displayName", {}).get("text", "Unknown Hotel")
                address = p.get("formattedAddress", "Address not available")
                rating = p.get("rating", "N/A")
                price_level = p.get("priceLevel", "N/A")
                user_ratings = p.get("userRatingCount", 0)
                
                results.append({
                    "name": display_name,
                    "address": address,
                    "rating": rating,
                    "price_level": price_level,
                    "reviews_count": user_ratings
                })
            return {"hotels": results}
    except Exception as e:
        print(f"[Warning] Google Places API (Hotels) call failed: {str(e)}. Falling back to simulated hotel search.")
        for key in MOCK_HOTELS:
            if key in location.lower():
                return {"hotels": MOCK_HOTELS[key]}
        return {"hotels": [
            {"name": f"Grand Central Hotel at {location}", "address": f"100 Main St, {location}", "rating": 4.2, "price_level": 2, "reviews_count": 120}
        ]}


def search_activities(location: str) -> dict:
    """Searches for attractions, tourist destinations, parks, and dining at a location using the Google Places API (New).
    
    Args:
        location: The city/area name (e.g. 'Monterey, CA').
        
    Returns:
        A dictionary listing points of interest with names, ratings, addresses, and details.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY") or "YOUR_MAPS_API_KEY"
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        print(f"[Warning] GOOGLE_MAPS_API_KEY not found or default. Using simulated Places (New) search for activities in: {location}")
        for key in MOCK_ACTIVITIES:
            if key in location.lower():
                return {"activities": MOCK_ACTIVITIES[key]}
        return {"activities": [
            {"name": f"Local Sightseeing at {location}", "address": f"200 Broad St, {location}", "rating": 4.3, "type": "park", "reviews_count": 85}
        ]}
        
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.primaryType,places.userRatingCount"
    }
    body = {
        "textQuery": f"top tourist attractions, parks, landmarks, and things to do in {location}"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            places = res_data.get("places", [])
            
            results = []
            for p in places[:5]:
                display_name = p.get("displayName", {}).get("text", "Unknown Attraction")
                address = p.get("formattedAddress", "Address not available")
                rating = p.get("rating", "N/A")
                primary_type = p.get("primaryType", "N/A")
                user_ratings = p.get("userRatingCount", 0)
                
                results.append({
                    "name": display_name,
                    "address": address,
                    "rating": rating,
                    "type": primary_type,
                    "reviews_count": user_ratings
                })
            return {"activities": results}
    except Exception as e:
        print(f"[Warning] Google Places API (Activities) call failed: {str(e)}. Falling back to simulated activity search.")
        for key in MOCK_ACTIVITIES:
            if key in location.lower():
                return {"activities": MOCK_ACTIVITIES[key]}
        return {"activities": [
            {"name": f"Local Sightseeing at {location}", "address": f"200 Broad St, {location}", "rating": 4.3, "type": "park", "reviews_count": 85}
        ]}

