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


class TravelAPIError(Exception):
    """Custom exception raised when live travel API calls fail or required keys are missing.
    
    Provides structured multi-line diagnostic details to help engineers troubleshoot and fix issues.
    """
    def __init__(self, tool_name: str, args: dict, api_key_status: str, raw_error: str, actionable_steps: str):
        self.tool_name = tool_name
        self.args = args
        self.api_key_status = api_key_status
        self.raw_error = raw_error
        self.actionable_steps = actionable_steps
        
        message = (
            f"\n"
            f"========================================================================\n"
            f"❌ TRAVEL API ERROR: Process Failed to Retrieve Actual Travel Information\n"
            f"========================================================================\n"
            f"Failed Tool  : {self.tool_name}\n"
            f"Arguments    : {json.dumps(self.args, indent=2)}\n"
            f"API Key State: {self.api_key_status}\n"
            f"Raw Error    : {self.raw_error}\n"
            f"------------------------------------------------------------------------\n"
            f"💡 ACTIONABLE STEPS FOR ENGINEERS:\n"
            f"{self.actionable_steps}\n"
            f"========================================================================"
        )
        super().__init__(message)



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
    args_dict = {
        "origin": origin,
        "destination": destination,
        "stopovers_semicolon_separated": stopovers_semicolon_separated,
        "stopovers": stopovers
    }
    
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        raise TravelAPIError(
            tool_name="get_directions",
            args=args_dict,
            api_key_status="MISSING or set to placeholder 'YOUR_MAPS_API_KEY'",
            raw_error="No active Google Maps API key provided.",
            actionable_steps=(
                "1. Open your project's .env file (or set a system environment variable).\n"
                "2. Define GOOGLE_MAPS_API_KEY with a valid Google Cloud API key.\n"
                "3. Ensure the Directions API is enabled on your API key in the Google Cloud Console."
            )
        )
        
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
            raise Exception("Google Maps Directions API returned an empty list of routes.")
            
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
        raise TravelAPIError(
            tool_name="get_directions",
            args=args_dict,
            api_key_status="PRESENT (key set in environment)",
            raw_error=str(e),
            actionable_steps=(
                "1. Verify that your Google Cloud billing account is active.\n"
                "2. Check that the Directions API is enabled in the Google Cloud Console.\n"
                "3. Verify that your API key is not IP-restricted or restricted from calling the Directions API.\n"
                "4. Check for network connectivity, timeout, or DNS issues from your environment."
            )
        )


def search_hotels(location: str) -> dict:
    """Searches for hotels, lodgings, and resorts at a destination using the Google Places API (New).
    
    Shows hotel name, full address, average rating, price tier (if available), and reviews count.
    
    Args:
        location: The city/area name to search for hotels (e.g. 'Santa Cruz, CA').
        
    Returns:
        A dictionary listing hotels with names, ratings, addresses, and price levels.
    """
    args_dict = {"location": location}
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        raise TravelAPIError(
            tool_name="search_hotels",
            args=args_dict,
            api_key_status="MISSING or set to placeholder 'YOUR_MAPS_API_KEY'",
            raw_error="No active Google Maps API key provided.",
            actionable_steps=(
                "1. Open your project's .env file (or set a system environment variable).\n"
                "2. Define GOOGLE_MAPS_API_KEY with a valid Google Cloud API key.\n"
                "3. Ensure the Places API (New) is enabled on your API key in the Google Cloud Console."
            )
        )
        
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
        raw_error_str = str(e)
        ssl_steps = ""
        if "CERTIFICATE_VERIFY_FAILED" in raw_error_str:
            ssl_steps = (
                "\n⚠️  SSL CERTIFICATE VERIFICATION FAILURE DETECTED:\n"
                "  Python's built-in urllib is failing to verify SSL certifications (very common on macOS).\n"
                "  To fix this, open terminal and run:\n"
                "    /Applications/Python\\ <version>/Install\\ Certificates.command\n"
                "  (replace <version> with your actual Python installation version, e.g. 3.13, 3.12, 3.11)."
            )
        raise TravelAPIError(
            tool_name="search_hotels",
            args=args_dict,
            api_key_status="PRESENT (key set in environment)",
            raw_error=raw_error_str,
            actionable_steps=(
                "1. Verify that your Google Cloud billing account is active.\n"
                "2. Check that the Places API (New) is enabled in the Google Cloud Console.\n"
                "3. Ensure your API key is not IP-restricted or restricted from calling the Places API (New).\n"
                f"4. Check for SSL certificate verification or network connectivity issues.{ssl_steps}"
            )
        )


def search_activities(location: str) -> dict:
    """Searches for attractions, tourist destinations, parks, and dining at a location using the Google Places API (New).
    
    Args:
        location: The city/area name (e.g. 'Monterey, CA').
        
    Returns:
        A dictionary listing points of interest with names, ratings, addresses, and details.
    """
    args_dict = {"location": location}
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        raise TravelAPIError(
            tool_name="search_activities",
            args=args_dict,
            api_key_status="MISSING or set to placeholder 'YOUR_MAPS_API_KEY'",
            raw_error="No active Google Maps API key provided.",
            actionable_steps=(
                "1. Open your project's .env file (or set a system environment variable).\n"
                "2. Define GOOGLE_MAPS_API_KEY with a valid Google Cloud API key.\n"
                "3. Ensure the Places API (New) is enabled on your API key in the Google Cloud Console."
            )
        )
        
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
        raw_error_str = str(e)
        ssl_steps = ""
        if "CERTIFICATE_VERIFY_FAILED" in raw_error_str:
            ssl_steps = (
                "\n⚠️  SSL CERTIFICATE VERIFICATION FAILURE DETECTED:\n"
                "  Python's built-in urllib is failing to verify SSL certifications (very common on macOS).\n"
                "  To fix this, open terminal and run:\n"
                "    /Applications/Python\\ <version>/Install\\ Certificates.command\n"
                "  (replace <version> with your actual Python installation version, e.g. 3.13, 3.12, 3.11)."
            )
        raise TravelAPIError(
            tool_name="search_activities",
            args=args_dict,
            api_key_status="PRESENT (key set in environment)",
            raw_error=raw_error_str,
            actionable_steps=(
                "1. Verify that your Google Cloud billing account is active.\n"
                "2. Check that the Places API (New) is enabled in the Google Cloud Console.\n"
                "3. Ensure your API key is not IP-restricted or restricted from calling the Places API (New).\n"
                f"4. Check for SSL certificate verification or network connectivity issues.{ssl_steps}"
            )
        )


