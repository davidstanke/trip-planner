# Setup Guide: Antigravity PR Code Reviewer Agent

The **Antigravity PR Code Reviewer Agent** is a lightweight, ultra-fast GitHub Actions workflow that automatically analyzes incoming pull requests for code quality (syntax, maintainability, formatting, and architecture). It uses Google's `gemini-2.5-flash` model to analyze only the added or modified lines and posts inline review comments on the exact lines in your pull request.

If no issues are found, the agent automatically approves the pull request with a positive summary!

---

## Key Features

* **High Performance**: Optimized to run under 10 seconds by fetching and parsing only the pull request's unified diff instead of the entire codebase.
* **Line-by-Line Pins**: Targets comments directly at the line numbers where code quality improvements are needed.
* **Smart Throttling**: Batches all comments into a single pull request review submission, ensuring your PR activity log remains clean and avoiding GitHub rate limits.
* **Autonomous Approval**: Automatically approves the pull request if the changes look clean and meet standard software engineering practices.

---

## Step-by-Step Configuration

To configure the Code Quality Reviewer on **GitHub.com**, follow these steps:

### Step 1: Obtain a Gemini API Key
1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your Google account.
3. Click on **Create API Key** and copy your generated key.

### Step 2: Add the Secret to GitHub
1. Navigate to your repository on **GitHub.com**.
2. Click on the **Settings** tab.
3. In the left sidebar, expand **Secrets and variables** and select **Actions**.
4. Click on the **New repository secret** button.
5. Set the secret details:
   * **Name**: `GEMINI_API_KEY`
   * **Secret**: *Paste your copied Gemini API key here*
6. Click **Add secret** to save.

### Step 3: Trigger the Reviewer
The next time you (or anyone) opens a Pull Request or pushes new commits to an open Pull Request on this repository, the workflow will automatically trigger!

You can view the progress of the review under the **Actions** tab of your repository on GitHub.

---

## How It Works Under the Hood

```
   Pull Request Event
           │
           ▼
┌──────────────────────┐
│  GitHub Actions Job  │ (Ubuntu runner)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Fetch & Parse Diff   │ (Standard Python urllib - extracts modified files & exact line numbers)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Gemini 2.5 Flash API │ (Structured JSON output schema validation via Pydantic)
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Submit Single Review │ (Approve or Comment Review posted with line-pinned comments)
└──────────────────────┘
```

1. **Trigger**: When a PR is `opened`, `reopened`, or new code is `synchronized` (pushed), GitHub starts the workflow.
2. **Diff Retrieval**: The Python script fetches the raw unified diff of the PR. It processes the diff line-by-line to extract the exact files, modified contents, and 1-indexed line numbers.
3. **Structured Review**: The code changes and line numbers are compiled and sent to `gemini-2.5-flash` with a strict JSON output schema.
4. **Publish Review**: The script translates Gemini's validated output into a single unified GitHub PR Review payload and submits it.
