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
"""Unit tests for the custom credential detection script."""

import os
import sys
import tempfile
import pytest

# Add the script's directory to python path to import functions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.agents/skills/credential-detector/scripts")))

import detect_credentials

def test_mask_secret() -> None:
    """Verifies that secrets are masked properly without leaking full content."""
    short_secret = "123"
    assert detect_credentials.mask_secret(short_secret) == "****"

    long_secret = "AIzaSyD_TEST_GOOGLE_API_KEY_123456"
    masked = detect_credentials.mask_secret(long_secret)
    assert masked.startswith("AIzaSy")
    assert masked.endswith("456")
    assert "****************" in masked
    assert "TEST_GOOGLE" not in masked

def test_pattern_exclusions() -> None:
    """Verifies that specific pattern exclusions are applied based on path."""
    assert detect_credentials.should_exclude_pattern_for_file("Generic Placeholders", "app/trip_planner/tools.py")
    assert detect_credentials.should_exclude_pattern_for_file("Generic Placeholders", "test_deployment.py")
    assert not detect_credentials.should_exclude_pattern_for_file("Google API Key", "app/trip_planner/tools.py")
    assert not detect_credentials.should_exclude_pattern_for_file("Generic Placeholders", "app/trip_planner/main.py")

def test_scan_file_detection() -> None:
    """Tests file scanning for credentials and the bypass/ignore mechanisms."""
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".py", delete=False) as temp_file:
        temp_file.write("GOOGLE_KEY = 'AIzaSyD_SOME_ACTUAL_LOOKING_KEY_1234567'\n")  # ignore-credential
        temp_file.write("AWS_ID = 'AKIA1234567890123456'\n")  # ignore-credential
        temp_file.write("BYPASSED_KEY = 'AIzaSyD_BYPASSED_TEST_KEY_FOR_DEMO_9999' # ignore-credential\n")
        temp_file.write("NOSEC_KEY = 'ghp_abc123xyzABC123XYZabc123xyzABC123XYZ' # nosec\n")
        temp_file.write("GITHUB_TOKEN = 'ghp_abc123xyzABC123XYZabc123xyzABC123XYZ'\n")  # ignore-credential
        temp_file_name = temp_file.name

    try:
        findings = detect_credentials.scan_file(temp_file_name)
        # Expected matches:
        # 1. GOOGLE_KEY (Google API Key)
        # 2. AWS_ID (AWS Access Key ID)
        # 3. GITHUB_TOKEN (GitHub PAT)
        # Bypassed keys (BYPASSED_KEY and NOSEC_KEY) should NOT be detected.
        
        assert len(findings) == 3
        
        pattern_names = [f["pattern_name"] for f in findings]
        assert "Google API Key" in pattern_names
        assert "AWS Access Key ID" in pattern_names
        assert "GitHub PAT" in pattern_names
    finally:
        os.unlink(temp_file_name)
