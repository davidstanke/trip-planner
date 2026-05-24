import os
import sys
import json
import urllib.request
import urllib.error
from typing import List, Dict, Any, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration & Inputs
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
PR_NUMBER = os.environ.get("PR_NUMBER")
REPO = os.environ.get("REPO")
HEAD_SHA = os.environ.get("HEAD_SHA")

# Ensure all environment variables are present
if not all([GEMINI_API_KEY, GITHUB_TOKEN, PR_NUMBER, REPO, HEAD_SHA]):
    print("Error: Missing required environment variables.", file=sys.stderr)
    print(f"GEMINI_API_KEY: {'set' if GEMINI_API_KEY else 'missing'}", file=sys.stderr)
    print(f"GITHUB_TOKEN: {'set' if GITHUB_TOKEN else 'missing'}", file=sys.stderr)
    print(f"PR_NUMBER: {PR_NUMBER}", file=sys.stderr)
    print(f"REPO: {REPO}", file=sys.stderr)
    print(f"HEAD_SHA: {HEAD_SHA}", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Models for Structured Output
# ---------------------------------------------------------------------------
class PRComment(BaseModel):
    path: str = Field(description="The exact relative path of the file.")
    line: int = Field(description="The 1-indexed line number in the modified file where this comment applies.")
    body: str = Field(description="Constructive code quality review feedback (syntax, maintainability, formatting, architecture) in markdown. Keep it clear, concise, and actionable.")

class PRReview(BaseModel):
    summary: str = Field(description="An overall summary of the review (50 words or less).")
    comments: List[PRComment] = Field(description="List of line-by-line review comments.")

# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def make_github_request(url: str, method: str = "GET", payload: Any = None, custom_headers: Dict[str, str] = None) -> Tuple[int, bytes]:
    """Helper to perform GitHub REST API calls using standard urllib."""
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "User-Agent": "antigravity-code-reviewer-action",
        "Accept": "application/vnd.github.v3+json"
    }
    if custom_headers:
        headers.update(custom_headers)
        
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}", file=sys.stderr)
        raise e
    except Exception as e:
        print(f"Request failed: {str(e)}", file=sys.stderr)
        raise e

def parse_diff(diff_text: str) -> Dict[str, List[Tuple[int, str]]]:
    """Parses a unified diff and maps changes to exact line numbers in the modified files."""
    files_changes = {}
    current_file = None
    current_line = 0
    
    for line in diff_text.splitlines():
        if line.startswith('diff --git '):
            current_file = None
        elif line.startswith('--- a/'):
            pass
        elif line.startswith('+++ b/'):
            # Extract file name, removing leading b/
            current_file = line[6:]
            files_changes[current_file] = []
        elif line.startswith('@@ '):
            # Parse chunk header: @@ -old_start,old_count +new_start,new_count @@
            parts = line.split()
            if len(parts) >= 3:
                new_info = parts[2]  # e.g., "+10,6"
                if ',' in new_info:
                    current_line = int(new_info.split(',')[0].replace('+', ''))
                else:
                    current_line = int(new_info.replace('+', ''))
        elif current_file:
            if line.startswith('+'):
                content = line[1:]
                files_changes[current_file].append((current_line, content))
                current_line += 1
            elif line.startswith('-'):
                # Deleted line: doesn't increment the line counter for the target file
                pass
            else:
                # Unchanged context line
                current_line += 1
                
    return {k: v for k, v in files_changes.items() if v}

# ---------------------------------------------------------------------------
# Main Logic
# ---------------------------------------------------------------------------
def main():
    print(f"Fetching diff for PR #{PR_NUMBER} in {REPO}...")
    pr_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}"
    
    # Request raw unified diff
    try:
        _, diff_bytes = make_github_request(
            pr_url, 
            custom_headers={"Accept": "application/vnd.github.v3.diff"}
        )
        diff_text = diff_bytes.decode("utf-8")
    except Exception as e:
        print(f"Failed to fetch PR diff: {e}", file=sys.stderr)
        sys.exit(1)
        
    # Parse the diff
    changes = parse_diff(diff_text)
    if not changes:
        print("No added or modified lines found in this PR. Skipping review.")
        sys.exit(0)
        
    print(f"Successfully parsed changes across {len(changes)} files. Initializing Gemini client...")
    
    # Build prompt content
    prompt_lines = [
        "Please review the following pull request code changes.",
        "Below is a list of added or modified lines, grouped by file, along with their exact line numbers.",
        "Provide constructive code quality review feedback (syntax, maintainability, formatting, architecture) only for lines with real issues.",
        "Avoid nitpicking or commenting on lines that are fine.",
        "---",
    ]
    for filepath, lines in changes.items():
        prompt_lines.append(f"\nFile: {filepath}")
        for line_num, content in lines:
            prompt_lines.append(f"  L{line_num}: {content}")
            
    prompt = "\n".join(prompt_lines)
    
    # Invoke Gemini 2.5 Flash with Structured Output
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=PRReview,
                system_instruction=(
                    "You are an expert Senior Staff Software Engineer and architect reviewing code changes. "
                    "Analyze the given PR changes for potential bugs, security flaws, performance degradation, "
                    "formatting irregularities, and maintainability concerns. "
                    "Be direct, polite, and extremely concise. "
                    "Only comment on lines that have legitimate, actionable areas of improvement. "
                    "If a line or file is of high quality, do not comment on it. "
                    "Your overall review summary must be 50 words or less."
                )
            ),
        )
        # Validate schema
        review_data = PRReview.model_validate_json(response.text)
    except Exception as e:
        print(f"Failed to generate review via Gemini API: {e}", file=sys.stderr)
        sys.exit(1)
        
    print(f"\nGenerated Review Summary: {review_data.summary}")
    print(f"Generated {len(review_data.comments)} inline comments.")
    
    # Prepare PR review payload
    review_comments = []
    for c in review_data.comments:
        # Extra verification that filepath and line match the changes we parsed
        if c.path in changes:
            review_comments.append({
                "path": c.path,
                "line": c.line,
                "side": "RIGHT",
                "body": c.body
            })
            
    # If we have comments, post them as a COMMENT review. Otherwise, post an APPROVE review.
    if review_comments:
        review_payload = {
            "commit_id": HEAD_SHA,
            "event": "COMMENT",
            "body": f"### Antigravity Code Quality Review\n\n{review_data.summary}",
            "comments": review_comments
        }
    else:
        review_payload = {
            "commit_id": HEAD_SHA,
            "event": "APPROVE",
            "body": f"### Antigravity Code Quality Review\n\n🟢 **LGTM!** I analyzed all changed lines and found no code quality issues.\n\n{review_data.summary}"
        }
        
    # Submit the review back to GitHub
    reviews_url = f"https://api.github.com/repos/{REPO}/pulls/{PR_NUMBER}/reviews"
    print(f"Submitting PR review to {reviews_url}...")
    try:
        status, _ = make_github_request(reviews_url, method="POST", payload=review_payload)
        if status in (200, 201):
            print("✅ Successfully submitted PR review comments!")
        else:
            print(f"Warning: GitHub API returned status code {status}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to submit PR review comments: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
