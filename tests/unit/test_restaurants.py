# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import urllib.error
import urllib.request
import json
from unittest.mock import MagicMock, patch
import pytest

from app.trip_planner.tools import search_restaurants, TravelAPIError, get_google_maps_api_key


@pytest.fixture(autouse=True)
def mock_disable_cache() -> None:
    """Disables the travel tools persistent SQLite cache to isolate error tests."""
    with patch("app.trip_planner.tools.get_cached_response", return_value=None):
        yield


def test_missing_api_key_raises_travel_api_error_for_restaurants() -> None:
    # Patch environment to make sure GOOGLE_MAPS_API_KEY is empty or missing
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(TravelAPIError) as exc_info:
            search_restaurants("Santa Cruz, CA")
        assert exc_info.value.tool_name == "search_restaurants"
        assert "MISSING" in exc_info.value.api_key_status


def test_placeholder_api_key_raises_travel_api_error_for_restaurants() -> None:
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "YOUR_MAPS_API_KEY"}):
        with pytest.raises(TravelAPIError) as exc_info:
            search_restaurants("Santa Cruz, CA")
        assert "placeholder 'YOUR_MAPS_API_KEY'" in exc_info.value.api_key_status


@patch("urllib.request.urlopen")
def test_search_restaurants_success(mock_urlopen) -> None:
    # Set up simulated HTTP response matching Google Places API (New) schema
    mock_response = MagicMock()
    mock_places_data = {
        "places": [
            {
                "displayName": {"text": "Phil's Fish Market"},
                "formattedAddress": "Moss Landing, CA",
                "rating": 4.6,
                "priceLevel": "PRICE_LEVEL_MODERATE",
                "userRatingCount": 3500,
                "primaryType": "seafood_restaurant"
            }
        ]
    }
    mock_response.read.return_value = json.dumps(mock_places_data).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "some-valid-key"}):
        res = search_restaurants("Moss Landing, CA")
        
        assert "restaurants" in res
        restaurants = res["restaurants"]
        assert len(restaurants) == 1
        assert restaurants[0]["name"] == "Phil's Fish Market"
        assert restaurants[0]["address"] == "Moss Landing, CA"
        assert restaurants[0]["rating"] == 4.6
        assert restaurants[0]["price_level"] == "PRICE_LEVEL_MODERATE"
        assert restaurants[0]["reviews_count"] == 3500
        assert restaurants[0]["type"] == "seafood_restaurant"
