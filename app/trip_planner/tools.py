import os
import json
import asyncio
import urllib.request
import urllib.parse
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
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


def get_google_maps_api_key() -> str:
    """Gets the Google Maps API key.
    
    1. Returns 'GOOGLE_MAPS_API_KEY' environment variable if it's set and not a placeholder.
    2. If in GCP (Vertex AI Reasoning Engine / Agent Runtime), retrieves securely from Google Secret Manager.
    3. Returns placeholder 'YOUR_MAPS_API_KEY' if not available.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if api_key and api_key != "YOUR_MAPS_API_KEY":
        return api_key
        
    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project_id:
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            secret_path = f"projects/{project_id}/secrets/google-maps-api-key/versions/latest"
            response = client.access_secret_version(request={"name": secret_path})
            retrieved_key = response.payload.data.decode("UTF-8").strip()
            if retrieved_key:
                return retrieved_key
        except Exception:
            pass
            
    return "YOUR_MAPS_API_KEY"


# ==============================================================================
# Persistent SQLite Cache Layer (Zero-Dependency & No ORM)
# ==============================================================================

CACHE_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".cache",
    "travel_api_cache.db"
)
_db_lock = threading.Lock()

def _init_db():
    """Initializes the SQLite cache database and table if not already present."""
    try:
        os.makedirs(os.path.dirname(CACHE_DB_PATH), exist_ok=True)
        with _db_lock:
            conn = sqlite3.connect(CACHE_DB_PATH, timeout=10)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS api_cache (
                        cache_key TEXT PRIMARY KEY,
                        response_json TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            finally:
                conn.close()
    except Exception:
        # Graceful fallback: do not fail execution if cache database setup fails
        pass

def get_cached_response(cache_key: str) -> dict | None:
    """Retrieves a cached JSON response for a key, or None if not cached."""
    try:
        _init_db()
        with _db_lock:
            conn = sqlite3.connect(CACHE_DB_PATH, timeout=5)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT response_json FROM api_cache WHERE cache_key = ?", (cache_key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
            finally:
                conn.close()
    except Exception:
        pass
    return None

def set_cached_response(cache_key: str, data: dict):
    """Stores a successful JSON response in the SQLite cache."""
    try:
        _init_db()
        with _db_lock:
            conn = sqlite3.connect(CACHE_DB_PATH, timeout=5)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO api_cache (cache_key, response_json)
                    VALUES (?, ?)
                """, (cache_key, json.dumps(data)))
                conn.commit()
            finally:
                conn.close()
    except Exception:
        pass


# ==============================================================================
# Core Travel Tools
# ==============================================================================

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
    
    # Check persistent cache prior to network execution
    stopovers_str = ";".join(sorted(parsed_stopovers))
    cache_key = f"directions:{origin}:{destination}:{stopovers_str}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    api_key = get_google_maps_api_key()
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
        
        result = {
            "total_distance_miles": total_distance_miles,
            "total_duration_hours": total_duration_hours,
            "legs": legs_summary,
            "waypoint_order": route.get("waypoint_order", []),
            "summary": route.get("summary", "")
        }
        set_cached_response(cache_key, result)
        return result
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


def _search_single_hotel(loc: str, api_key: str) -> dict:
    """Helper to search hotels for a single location, handling caching directly."""
    cache_key = f"hotels:{loc}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.userRatingCount"
    }
    body = {
        "textQuery": f"best lodging hotels resorts in {loc}"
    }
    
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
        result = {"hotels": results}
        set_cached_response(cache_key, result)
        return result


def search_hotels(location: str) -> dict:
    """Searches for hotels, lodgings, and resorts at a destination using the Google Places API (New).
    
    Supports semicolon-separated locations to execute queries in parallel.
    
    Args:
        location: Semicolon-separated or single city/area name (e.g. 'Santa Cruz, CA; Monterey, CA').
        
    Returns:
        A dictionary listing hotels with names, ratings, addresses, and price levels.
    """
    args_dict = {"location": location}
    api_key = get_google_maps_api_key()
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

    # Split and clean the list of locations
    locs = [l.strip() for l in location.split(";") if l.strip()]
    if not locs:
        return {"hotels": []}

    try:
        all_hotels = []
        uncached_locs = []
        # First, check the cache for all locations to fetch hits immediately
        for loc in locs:
            cache_key = f"hotels:{loc}"
            cached = get_cached_response(cache_key)
            if cached is not None:
                all_hotels.extend(cached.get("hotels", []))
            else:
                uncached_locs.append(loc)

        # For uncached locations, fetch them concurrently using ThreadPoolExecutor
        if uncached_locs:
            with ThreadPoolExecutor(max_workers=min(len(uncached_locs), 10)) as executor:
                futures = {executor.submit(_search_single_hotel, loc, api_key): loc for loc in uncached_locs}
                for future in futures:
                    try:
                        res = future.result()
                        all_hotels.extend(res.get("hotels", []))
                    except Exception as e:
                        raise e

        return {"hotels": all_hotels}
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


def _search_single_activity(loc: str, api_key: str) -> dict:
    """Helper to search activities for a single location, handling caching directly."""
    cache_key = f"activities:{loc}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.primaryType,places.userRatingCount"
    }
    body = {
        "textQuery": f"top tourist attractions, parks, landmarks, and things to do in {loc}"
    }
    
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
        result = {"activities": results}
        set_cached_response(cache_key, result)
        return result


def search_activities(location: str) -> dict:
    """Searches for attractions, tourist destinations, parks, and dining at a location using the Google Places API (New).
    
    Supports semicolon-separated locations to execute queries in parallel.
    
    Args:
        location: Semicolon-separated or single city/area name (e.g. 'Monterey, CA; Santa Cruz, CA').
        
    Returns:
        A dictionary listing points of interest with names, ratings, addresses, and details.
    """
    args_dict = {"location": location}
    api_key = get_google_maps_api_key()
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

    # Split and clean the list of locations
    locs = [l.strip() for l in location.split(";") if l.strip()]
    if not locs:
        return {"activities": []}

    try:
        all_activities = []
        uncached_locs = []
        # First, check the cache for all locations to fetch hits immediately
        for loc in locs:
            cache_key = f"activities:{loc}"
            cached = get_cached_response(cache_key)
            if cached is not None:
                all_activities.extend(cached.get("activities", []))
            else:
                uncached_locs.append(loc)

        # For uncached locations, fetch them concurrently using ThreadPoolExecutor
        if uncached_locs:
            with ThreadPoolExecutor(max_workers=min(len(uncached_locs), 10)) as executor:
                futures = {executor.submit(_search_single_activity, loc, api_key): loc for loc in uncached_locs}
                for future in futures:
                    try:
                        res = future.result()
                        all_activities.extend(res.get("activities", []))
                    except Exception as e:
                        raise e

        return {"activities": all_activities}
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


def _search_single_restaurant(loc: str, api_key: str) -> dict:
    """Helper to search restaurants for a single location, handling caching directly."""
    cache_key = f"restaurants:{loc}"
    cached = get_cached_response(cache_key)
    if cached is not None:
        return cached

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.priceLevel,places.userRatingCount,places.primaryType"
    }
    body = {
        "textQuery": f"top local favorite restaurants, cafes, and eateries in {loc}"
    }
    
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
            display_name = p.get("displayName", {}).get("text", "Unknown Restaurant")
            address = p.get("formattedAddress", "Address not available")
            rating = p.get("rating", "N/A")
            price_level = p.get("priceLevel", "N/A")
            user_ratings = p.get("userRatingCount", 0)
            primary_type = p.get("primaryType", "N/A")
            
            results.append({
                "name": display_name,
                "address": address,
                "rating": rating,
                "price_level": price_level,
                "reviews_count": user_ratings,
                "type": primary_type
            })
        result = {"restaurants": results}
        set_cached_response(cache_key, result)
        return result


def search_restaurants(location: str) -> dict:
    """Searches for top local favorite restaurants, cafes, and eateries at a location using the Google Places API (New).
    
    Supports semicolon-separated locations to execute queries in parallel.
    
    Args:
        location: Semicolon-separated or single city/area name (e.g. 'Monterey, CA; Santa Cruz, CA').
        
    Returns:
        A dictionary listing restaurants with names, ratings, addresses, types, and price levels.
    """
    args_dict = {"location": location}
    api_key = get_google_maps_api_key()
    if not api_key or api_key == "YOUR_MAPS_API_KEY":
        raise TravelAPIError(
            tool_name="search_restaurants",
            args=args_dict,
            api_key_status="MISSING or set to placeholder 'YOUR_MAPS_API_KEY'",
            raw_error="No active Google Maps API key provided.",
            actionable_steps=(
                "1. Open your project's .env file (or set a system environment variable).\n"
                "2. Define GOOGLE_MAPS_API_KEY with a valid Google Cloud API key.\n"
                "3. Ensure the Places API (New) is enabled on your API key in the Google Cloud Console."
            )
        )

    # Split and clean the list of locations
    locs = [l.strip() for l in location.split(";") if l.strip()]
    if not locs:
        return {"restaurants": []}

    try:
        all_restaurants = []
        uncached_locs = []
        # First, check the cache for all locations to fetch hits immediately
        for loc in locs:
            cache_key = f"restaurants:{loc}"
            cached = get_cached_response(cache_key)
            if cached is not None:
                all_restaurants.extend(cached.get("restaurants", []))
            else:
                uncached_locs.append(loc)

        # For uncached locations, fetch them concurrently using ThreadPoolExecutor
        if uncached_locs:
            with ThreadPoolExecutor(max_workers=min(len(uncached_locs), 10)) as executor:
                futures = {executor.submit(_search_single_restaurant, loc, api_key): loc for loc in uncached_locs}
                for future in futures:
                    try:
                        res = future.result()
                        all_restaurants.extend(res.get("restaurants", []))
                    except Exception as e:
                        raise e

        return {"restaurants": all_restaurants}
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
            tool_name="search_restaurants",
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
