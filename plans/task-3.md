# Task 3: The System Agent - Implementation Plan

## Overview
Add query_api tool to the documentation agent from Task 2, enabling it to query the deployed backend API.

## Tool: query_api
- **Purpose**: Call backend API endpoints to get real system data
- **Parameters**: method (GET/POST/PUT/DELETE/PATCH), path, body (optional)
- **Authentication**: Use LMS_API_KEY from environment via X-API-Key header
- **Base URL**: From AGENT_API_BASE_URL env var (default: http://localhost:42002)
- **Returns**: JSON string with status_code and body fields

## Implementation Details

### Tool Schema
Added query_api to TOOL_SCHEMAS with:
- method: enum of HTTP methods
- path: endpoint path string
- body: optional JSON string for POST/PUT/PATCH

### Function Implementation
```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    # Uses httpx.Client for synchronous HTTP requests
    # Reads LMS_API_KEY from environment
    # Builds URL from AGENT_API_BASE_URL + path
    # Returns JSON with status_code and body
```

### System Prompt Updates
The system prompt now instructs the LLM to:
- Use `query_api` for data-dependent questions (item counts, scores, analytics)
- Use `query_api` for system facts (framework, ports, status codes)
- Use `read_file`/`list_files` for wiki and documentation questions
- Use "system" as the source for API-based answers

## Environment Variables
| Variable | Purpose | Source |
|----------|---------|--------|
| LLM_API_KEY | LLM provider key | .env.agent.secret |
| LLM_API_BASE | LLM endpoint | .env.agent.secret |
| LLM_MODEL | Model name | .env.agent.secret |
| LMS_API_KEY | Backend auth | .env.docker.secret |
| AGENT_API_BASE_URL | Backend URL | optional, defaults to localhost:42002 |

## Benchmark Strategy
1. Run `uv run run_eval.py` to see current failures
2. Fix one question at a time:
   - Data queries → ensure query_api works
   - System facts → point to correct files
   - Bug diagnosis → chain read_file + query_api
3. Iterate until all 10 pass

## Test Coverage
Added 2 regression tests in `tests/test_agent.py`:
1. `test_agent_framework_question` - Tests system fact question uses query_api or read_file
2. `test_agent_item_count_question` - Tests data-dependent question uses query_api with GET /items/

## Initial Score (to be filled after first run)
- [ ] Run 1: ___/10
- [ ] First failures: ______

## Iteration Log
| Run | Score | Failures | Fix Applied |
|-----|-------|----------|-------------|
| 1 | _/10 | _ | _ |

## Notes
- The autochecker uses hidden questions not in run_eval.py
- LLM-based judging is used for open-ended questions on the bot side
- Must pass minimum threshold overall (local + hidden questions)
