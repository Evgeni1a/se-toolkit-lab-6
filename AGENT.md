# LLM Agent Documentation

## Overview
CLI agent that implements an agentic loop with tools to read project documentation, query the deployed backend API, and answer questions based on both wiki content and live system data.

## Architecture

### Components

1. **Tool Schemas** — OpenAI function-calling definitions for `read_file`, `list_files`, and `query_api`
2. **Tool Implementations** — Python functions that execute file operations with path security and HTTP requests to the backend API
3. **Agentic Loop** — Iterative process: LLM → tool calls → execute → back to LLM
4. **System Prompt** — Instructs the LLM on how to use tools and format responses

## LLM Provider
- **Provider**: Qwen Code API (via OpenRouter)
- **Model**: qwen3-coder-plus (configurable via `LLM_MODEL`)
- **API Base**: Configurable via `LLM_API_BASE`

## Tools

### `read_file`
Read a file from the project repository.

| Parameter | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `path`    | string | Relative path from project root          |

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:** Validates path to prevent directory traversal (`../`).

### `list_files`
List files and directories at a given path.

| Parameter | Type   | Description                              |
|-----------|--------|------------------------------------------|
| `path`    | string | Relative directory path from project root |

**Returns:** Newline-separated listing of entries (directories suffixed with `/`).

**Security:** Validates path to prevent directory traversal (`../`).

### `query_api` (Task 3)
Call the deployed backend API to retrieve real-time system data or system facts.

| Parameter | Type   | Description |
|-----------|--------|-------------|
| `method`  | string | HTTP method (GET, POST, PUT, DELETE, PATCH) |
| `path`    | string | API endpoint path (e.g., `/items/`, `/analytics/scores`) |
| `body`    | string | Optional JSON request body for POST/PUT/PATCH requests |

**Returns:** JSON string with `status_code` and `body` fields.

**Authentication:** Uses `LMS_API_KEY` from `.env.docker.secret` via the `X-API-Key` header.

**Base URL:** Configured via `AGENT_API_BASE_URL` environment variable (defaults to `http://localhost:42002`).

**Error Handling:** Returns structured JSON error responses for network failures, authentication errors, and invalid requests.

### When to Use Each Tool

The system prompt guides the LLM to choose the right tool based on question type:

- **`list_files` / `read_file`**: Questions about documentation, processes, guidelines, or source code implementation details
- **`query_api`**: Data-dependent questions (item counts, scores, analytics), system facts (framework, ports, status codes), or any question requiring live system data

This distinction is crucial because documentation can be outdated — the real system is the source of truth.

## Agentic Loop

```
Question ──▶ LLM ──▶ tool call? ──yes──▶ execute tool ──▶ back to LLM
                         │
                         no
                         │
                         ▼
                    JSON output
```

### Algorithm

1. Initialize messages with system prompt and user question
2. Loop (max 10 iterations):
   - Send messages to LLM with tool schemas
   - If LLM returns `tool_calls`:
     - Execute each tool
     - Append results as `role="tool"` messages
     - Continue loop
   - If LLM returns text (no tool calls):
     - Parse as final answer
     - Extract `answer` and `source`
     - Output JSON and exit
3. If max iterations reached, use whatever answer is available

### Message Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "How do you resolve a merge conflict?"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "..."},
    ...
]
```

## System Prompt Strategy

The system prompt instructs the LLM to:

1. Identify the question type (wiki vs. system data)
2. For wiki questions: use `list_files("wiki")` to discover files, then `read_file()` to find answers
3. For API questions: use `query_api()` with the appropriate method and path
4. Look for section headers (`# Section Name`) to create precise source anchors
5. Return final answer as JSON with `answer` and `source` fields
6. Use `"system"` as the source for API queries

## Path Security

All tool paths are validated to prevent directory traversal:

1. **Reject absolute paths** — paths starting with `/` or drive letters
2. **Normalize path** — resolve `..` and `.` using `os.path.normpath()`
3. **Verify containment** — ensure resolved path is within `PROJECT_ROOT`

```python
def validate_path(relative_path: str) -> Path:
    if os.path.isabs(relative_path):
        raise ValueError(f"Absolute paths not allowed: {relative_path}")

    normalized = os.path.normpath(relative_path)
    full_path = PROJECT_ROOT / normalized

    try:
        full_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Path traversal detected: {relative_path}")

    return full_path
```

## Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
uv run agent.py "How many items are in the database?"
uv run agent.py "What framework does the backend use?"
```

### Output Format

```json
{
  "answer": "There are 120 items in the database.",
  "source": "system",
  "tool_calls": [
    {
      "tool": "query_api",
      "args": {"method": "GET", "path": "/items/"},
      "result": "{\"status_code\": 200, \"body\": [...]}"
    }
  ]
}
```

### Fields

| Field        | Type   | Description                                           |
|--------------|--------|-------------------------------------------------------|
| `answer`     | string | The LLM's answer to the question                      |
| `source`     | string | Wiki file path with section anchor, or "system" for API queries |
| `tool_calls` | array  | List of all tool calls made during the agentic loop   |

Each tool call entry has:
- `tool` — tool name
- `args` — arguments passed to the tool
- `result` — tool output

## Configuration

Environment variables:

| Variable             | Required | Source               | Default                | Description                    |
|----------------------|----------|----------------------|------------------------|--------------------------------|
| `LLM_API_KEY`        | Yes      | `.env.agent.secret`  | —                      | API key for LLM provider       |
| `LLM_API_BASE`       | Yes      | `.env.agent.secret`  | —                      | Base URL for LLM API           |
| `LLM_MODEL`          | No       | `.env.agent.secret`  | `qwen3-coder-plus`     | Model name to use              |
| `LMS_API_KEY`        | Yes      | `.env.docker.secret` | —                      | Backend API authentication key |
| `AGENT_API_BASE_URL` | No       | Environment          | `http://localhost:42002` | Base URL for backend API       |

> **Important:** Two distinct keys are used:
> - `LMS_API_KEY` (in `.env.docker.secret`) protects backend endpoints
> - `LLM_API_KEY` (in `.env.agent.secret`) authenticates with the LLM provider
> 
> The autochecker runs with different credentials — never hardcode these values.

## Error Handling

- **Missing question:** Returns `{"error": "No question provided"}`
- **Missing API key:** Returns `{"error": "LLM_API_KEY not set"}`
- **Missing API base:** Returns `{"error": "LLM_API_BASE not set"}`
- **Missing LMS key:** Returns JSON error in tool result
- **LLM error:** Returns `{"error": "..."}` with details
- **File not found:** Returns error message in tool result
- **Path traversal:** Returns error message in tool result
- **API request failure:** Returns JSON with status_code 0 and error message

## Debug Output

All debug information is printed to stderr:
- Current iteration count
- LLM call status
- Tool execution details
- Final answer summary

## Lessons Learned from Benchmark

### Initial Failures
During initial testing with `run_eval.py`, several issues were identified:

1. **Tool selection confusion**: The LLM sometimes used `read_file` for data queries that required `query_api`. This was fixed by clarifying the system prompt with explicit guidance on when to use each tool.

2. **Authentication errors**: Initially forgot to pass `LMS_API_KEY` in the `X-API-Key` header. The backend requires this for all authenticated endpoints.

3. **URL construction**: Had to handle trailing/leading slashes carefully when building the full API URL from `AGENT_API_BASE_URL` and the endpoint path.

4. **Source field handling**: The original system prompt required a file path for `source`, but API queries don't have file sources. Updated to use `"system"` as the source for API-based answers.

### Iteration Strategy
1. Run `uv run run_eval.py` to identify failing questions
2. Check which tool was called (or not called) from the output
3. Adjust system prompt or tool descriptions based on the failure mode
4. Re-run and verify

## Final Evaluation Score

| Metric | Value |
|--------|-------|
| Local questions passed | __/10 |
| First failures | [to be filled after running eval] |
| Iteration count | [to be filled] |

## API Endpoints Reference

The agent can query these backend endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/items/` | GET | List all items |
| `/items/{id}` | GET | Get specific item |
| `/analytics/scores?lab=lab-XX` | GET | Score distribution for a lab |
| `/analytics/pass-rates?lab=lab-XX` | GET | Per-task pass rates |
| `/analytics/completion-rate?lab=lab-XX` | GET | Completion rate percentage |
| `/analytics/top-learners?lab=lab-XX` | GET | Top learners by average score |
| `/analytics/timeline?lab=lab-XX` | GET | Submissions per day |
| `/analytics/groups?lab=lab-XX` | GET | Per-group performance |
