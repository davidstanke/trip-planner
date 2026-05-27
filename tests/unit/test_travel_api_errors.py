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

from app.trip_planner.tools import get_directions, search_activities, search_hotels, search_restaurants, TravelAPIError, get_google_maps_api_key


@pytest.fixture(autouse=True)
def mock_disable_cache() -> None:
    """Disables the travel tools persistent SQLite cache to isolate error tests."""
    with patch("app.trip_planner.tools.get_cached_response", return_value=None):
        yield


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

        # 4. Test search_restaurants
        with pytest.raises(TravelAPIError) as exc_info:
            search_restaurants("Monterey, CA")
        assert exc_info.value.tool_name == "search_restaurants"
        assert "MISSING" in exc_info.value.api_key_status


def test_placeholder_api_key_raises_travel_api_error() -> None:
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "YOUR_MAPS_API_KEY"}):
        with pytest.raises(TravelAPIError) as exc_info:
            get_directions("San Francisco, CA", "Los Angeles, CA")
        assert "placeholder 'YOUR_MAPS_API_KEY'" in exc_info.value.api_key_status

        with pytest.raises(TravelAPIError) as exc_info:
            search_restaurants("Monterey, CA")
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
        # Test search_hotels SSL failure
        with pytest.raises(TravelAPIError) as exc_info:
            search_hotels("Santa Cruz, CA")
        
        assert exc_info.value.tool_name == "search_hotels"
        assert "CERTIFICATE_VERIFY_FAILED" in exc_info.value.raw_error
        # Check that SSL certificate troubleshooting steps are injected into actionable steps
        assert "SSL CERTIFICATE VERIFICATION FAILURE DETECTED" in exc_info.value.actionable_steps
        assert "Install\\ Certificates.command" in exc_info.value.actionable_steps

        # Test search_restaurants SSL failure
        with pytest.raises(TravelAPIError) as exc_info:
            search_restaurants("Santa Cruz, CA")
        
        assert exc_info.value.tool_name == "search_restaurants"
        assert "CERTIFICATE_VERIFY_FAILED" in exc_info.value.raw_error
        assert "SSL CERTIFICATE VERIFICATION FAILURE DETECTED" in exc_info.value.actionable_steps
        assert "Install\\ Certificates.command" in exc_info.value.actionable_steps


@patch("google.cloud.secretmanager.SecretManagerServiceClient")
def test_get_google_maps_api_key_secret_manager(mock_sm_client_class) -> None:
    # 1. Test environment variable exists and is valid
    with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "env-key"}, clear=True):
        assert get_google_maps_api_key() == "env-key"

    # 2. Test environment variable is missing/placeholder, but we are in GCP (GOOGLE_CLOUD_PROJECT is set)
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.payload.data = b"secret-manager-retrieved-key"
    mock_client.access_secret_version.return_value = mock_response
    mock_sm_client_class.return_value = mock_client

    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-gcp-project", "GOOGLE_MAPS_API_KEY": "YOUR_MAPS_API_KEY"}, clear=True):
        assert get_google_maps_api_key() == "secret-manager-retrieved-key"
        mock_client.access_secret_version.assert_called_once_with(
            request={"name": "projects/my-gcp-project/secrets/google-maps-api-key/versions/latest"}
        )

    # 3. Test fallback when Secret Manager lookup fails
    mock_client.access_secret_version.side_effect = Exception("API disabled")
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "my-gcp-project", "GOOGLE_MAPS_API_KEY": ""}, clear=True):
        assert get_google_maps_api_key() == "YOUR_MAPS_API_KEY"

