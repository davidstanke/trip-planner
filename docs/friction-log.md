# AGY CLI Friction Log — Trip Planner

## Issues Encountered

### Issue 1: Google Search grounding + custom tools conflict (400 INVALID_ARGUMENT)
- **What happened**: Vertex AI rejects API calls that mix `google_search` grounding with custom function tools (including ADK's auto-generated transfer tools) in a single agent.
- **Expected**: Should work seamlessly or show a clear error message.
- **Workaround**: ADK's `GoogleSearchTool(bypass_multi_tools_limit=True)` wraps search in a sub-agent. Adding any helper tool to the agent triggers this wrapping.
- **Impact**: High — blocks any agent that combines search grounding + tools without the workaround.

### Issue 2: agy model quota exhausted mid-session
- **What happened**: `You have exhausted your capacity on this model. Your quota will reset after 164h8m1s.` appeared during the deployment phase.
- **Expected**: Should warn when approaching quota limits, not fail mid-operation.
- **Workaround**: Completed deployment manually via `agents-cli deploy` from the terminal.
- **Impact**: High — lost autonomous workflow continuity.

### Issue 3: google-cloud-logging not in default scaffold dependencies
- **What happened**: `agents-cli scaffold enhance` generates `agent_runtime_app.py` that imports `google.cloud.logging`, but doesn't add it to `pyproject.toml`.
- **Expected**: Scaffold should add all dependencies its generated code requires.
- **Workaround**: Manually added `google-cloud-logging` to `pyproject.toml` and ran `uv lock`.
- **Impact**: Medium — deployment fails with a confusing import error.

### Issue 4: agents-cli `--yes` flag doesn't exist
- **What happened**: `agents-cli deploy --yes` returns `Error: No such option: --yes`.
- **Expected**: A `--yes` or `--auto-approve` flag for non-interactive deployment.
- **Workaround**: Run without `--yes` (the command proceeds without prompting anyway).
- **Impact**: Low — cosmetic, but makes scripting harder.

### Issue 5: Onboarding wizard on every new workspace
- **What happened**: Same as commerce-intel — agy shows the full onboarding wizard for each new workspace directory.
- **Workaround**: Navigate via tmux key sequences.
- **Impact**: Low — ~15 seconds overhead per new workspace.

## Positive Observations

1. **agy built a web UI without being asked**: Created `server.py` (FastAPI) + `static/` (HTML/CSS/JS) — impressive initiative
2. **VertexGemini pattern reuse**: agy found and reused the `VertexGemini` class from the commerce-intel agent
3. **`bypass_multi_tools_limit` discovery**: agy found this ADK-specific workaround autonomously by reading ADK source code
4. **agents-cli scaffold enhance**: One command generated production-ready deployment structure with Terraform and CI/CD
5. **agents-cli deploy**: Clean deployment with detailed output (resource ID, console link, service account)
