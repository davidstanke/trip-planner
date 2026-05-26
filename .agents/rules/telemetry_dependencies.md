---
trigger: always_on
description: Maintain telemetry and tracing dependencies consistently across deployment environments
---

# Telemetry and Tracing Dependencies

When configuring, modifying, or extending tracing or telemetry within the Agent or server components:

1. **Keep Dependency Definitions Synchronized**:
   Always add/update tracing/telemetry dependencies in both:
   - [pyproject.toml](file:///Users/davidstanke/gitroot/davidstanke/trip-planner/pyproject.toml) (for local development and local playground)
   - [app/app_utils/.requirements.txt](file:///Users/davidstanke/gitroot/davidstanke/trip-planner/app/app_utils/.requirements.txt) (for remote Agent Runtime/Reasoning Engine deployments)

2. **Align Library Versions**:
   Ensure telemetry and tracing package versions align with existing `opentelemetry-*` core package versions (e.g., `opentelemetry-api`, `opentelemetry-sdk`, and `opentelemetry-semantic-conventions` which are currently pinned at `0.62b1`/`1.41.1`).

### Case Study: Adding `opentelemetry-instrumentation-httpx`
To fix missing trace info in Agent Runtime and resolve log warnings such as:
`WARNING: telemetry enabled but proceeding without httpx instrumentation, because opentelemetry-instrumentation-httpx has not been installed`

The dependency was resolved as follows:
- Added `opentelemetry-instrumentation-httpx==0.62b1` to [app/app_utils/.requirements.txt](file:///Users/davidstanke/gitroot/davidstanke/trip-planner/app/app_utils/.requirements.txt) inline with the other OpenTelemetry packages.
- Added `"opentelemetry-instrumentation-httpx"` to the `dependencies` array in [pyproject.toml](file:///Users/davidstanke/gitroot/davidstanke/trip-planner/pyproject.toml) to align the local development/playground environment.
