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


def get_directions(origin: str, destination: str, stopovers_semicolon_separated: str = "") -> dict:
    """Plans driving routes between stops using Google Maps Platform Directions API.
    
    Calculates driving times, total distances, route summary, and optimal stop order.
    
    Args:
        origin: The starting address or city name (e.g., 'San Francisco, CA').
        destination: The ending address or city name (e.g., 'Los Angeles, CA').
        stopovers_semicolon_separated: Semicolon-separated list of stops between origin and destination.
                                       Example: 'Santa Cruz, CA; Monterey, CA; Big Sur, CA'
                                       
    Returns:
        A dictionary containing total distance, duration, leg details, and waypoint order.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print("[Warning] GOOGLE_MAPS_API_KEY not found. Using simulated Directions route.")
        return {
            "total_distance_miles": 453.2,
            "total_duration_hours": 9.8,
            "legs": [
                {"leg_index": 1, "start": "San Francisco, CA", "end": "Santa Cruz, CA", "distance": "73.1 miles", "duration": "1.3 hours"},
                {"leg_index": 2, "start": "Santa Cruz, CA", "end": "Monterey, CA", "distance": "42.8 miles", "duration": "0.9 hours"},
                {"leg_index": 3, "start": "Monterey, CA", "end": "Big Sur, CA", "distance": "29.7 miles", "duration": "0.8 hours"},
                {"leg_index": 4, "start": "Big Sur, CA", "end": "Los Angeles, CA", "distance": "307.6 miles", "duration": "6.8 hours"}
            ],
            "waypoint_order": [0, 1, 2],
            "summary": "CA-1 S / US-101 S"
        }
        
    try:
        gmaps = googlemaps.Client(key=api_key)
        
        waypoints = []
        if stopovers_semicolon_separated:
            waypoints = [stop.strip() for stop in stopovers_semicolon_separated.split(";") if stop.strip()]
        
        directions_result = gmaps.directions(
            origin=origin,
            destination=destination,
            waypoints=waypoints,
            optimize_waypoints=True,
            mode="driving"
        )
        
        if not directions_result:
            return {"error": f"No driving route found from '{origin}' to '{destination}'."}
            
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
        return {"error": f"Google Maps Directions API call failed: {str(e)}"}


def search_hotels(location: str) -> dict:
    """Searches for hotels, lodgings, and resorts at a destination using the Google Places API (New).
    
    Shows hotel name, full address, average rating, price tier (if available), and reviews count.
    
    Args:
        location: The city/area name to search for hotels (e.g. 'Santa Cruz, CA').
        
    Returns:
        A dictionary listing hotels with names, ratings, addresses, and price levels.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print(f"[Warning] GOOGLE_MAPS_API_KEY not found. Using simulated Places (New) search for hotels in: {location}")
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
        return {"error": f"Google Places API (Hotels) call failed: {str(e)}"}


def search_activities(location: str) -> dict:
    """Searches for attractions, tourist destinations, parks, and dining at a location using the Google Places API (New).
    
    Args:
        location: The city/area name (e.g. 'Monterey, CA').
        
    Returns:
        A dictionary listing points of interest with names, ratings, addresses, and details.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        print(f"[Warning] GOOGLE_MAPS_API_KEY not found. Using simulated Places (New) search for activities in: {location}")
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
        return {"error": f"Google Places API (Activities) call failed: {str(e)}"}
