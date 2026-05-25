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
from unittest.mock import MagicMock, patch
import pytest

from app.trip_planner.tools import get_directions, search_activities, search_hotels, TravelAPIError


def test_missing_api_key_raises_travel_api_error() -> None:
    # Patch environment to make sure GOOGLE_MAPS_API_KEY is empty or missing
    with patch.dict(os.environ, {}, clear=True):
        # 1. Test get_directions
        with pytest.raises(TravelAPIError) as exc_info:
            get_directions("San Francisco, CA", "Los Angeles, CA")
        assert exc_info.value.tool_name == "get_directions"
        assert "MISSING" in exc_info.value.api_key_status
        assert "No active Google Maps API key provided" in exc_info.value.raw_error
        
        # 2. Test search_hotels
        with pytest.raises(TravelAPIError) as exc_info:
            search_hotels("Santa Cruz, CA")
        assert exc_info.value.tool_name == "search_hotels"
        assert "MISSING" in exc_info.value.api_key_status
        
        # 3. Test search_activities
        with pytest.raises(TravelAPIError) as exc_info:
            search_activities("Monterey, CA")
        assert exc_info.value.tool_name == "search_activities"
        assert "MISSING" in exc_info.value.api_key_status


def test_placeholder_api_key_raises_travel_api_error() -> None:
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "YOUR_MAPS_API_KEY"}):
        with pytest.raises(TravelAPIError) as exc_info:
            get_directions("San Francisco, CA", "Los Angeles, CA")
        assert "placeholder 'YOUR_MAPS_API_KEY'" in exc_info.value.api_key_status


@patch("googlemaps.Client")
def test_googlemaps_failure_raises_travel_api_error(mock_gmaps_client_class) -> None:
    # Present API key but Google Maps API fails
    mock_client = MagicMock()
    mock_client.directions.side_effect = Exception("API Key is invalid or has expired.")
    mock_gmaps_client_class.return_value = mock_client
    
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "some-valid-looking-key"}):
        with pytest.raises(TravelAPIError) as exc_info:
            get_directions("San Francisco, CA", "Los Angeles, CA")
        assert exc_info.value.tool_name == "get_directions"
        assert exc_info.value.api_key_status == "PRESENT (key set in environment)"
        assert "API Key is invalid or has expired." in exc_info.value.raw_error


@patch("urllib.request.urlopen")
def test_urllib_ssl_failure_raises_travel_api_error_with_troubleshooting(mock_urlopen) -> None:
    # Mock urllib request failure with SSL CERTIFICATE_VERIFY_FAILED error
    mock_urlopen.side_effect = urllib.error.URLError("SSL: CERTIFICATE_VERIFY_FAILED certificate verify failed")
    
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "some-valid-looking-key"}):
        with pytest.raises(TravelAPIError) as exc_info:
            search_hotels("Santa Cruz, CA")
        
        assert exc_info.value.tool_name == "search_hotels"
        assert "CERTIFICATE_VERIFY_FAILED" in exc_info.value.raw_error
        # Check that SSL certificate troubleshooting steps are injected into actionable steps
        assert "SSL CERTIFICATE VERIFICATION FAILURE DETECTED" in exc_info.value.actionable_steps
        assert "Install\\ Certificates.command" in exc_info.value.actionable_steps
