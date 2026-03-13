# LLM Agent Documentation

## Overview
CLI agent that implements an agentic loop with tools to read project documentation and answer questions based on the wiki.

## Architecture

### Components

1. **Tool Schemas** — OpenAI function-calling definitions for `read_file` and `list_files`
2. **Tool Implementations** — Python functions that execute file operations with path security
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

1. Use `list_files("wiki")` to discover available documentation files
2. Use `read_file()` to read relevant files and find the answer
3. Look for section headers (`# Section Name`) to create precise source anchors
4. Return final answer as JSON with `answer` and `source` fields

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
```

### Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

### Fields

| Field        | Type   | Description                                           |
|--------------|--------|-------------------------------------------------------|
| `answer`     | string | The LLM's answer to the question                      |
| `source`     | string | Wiki file path with section anchor                    |
| `tool_calls` | array  | List of all tool calls made during the agentic loop   |

Each tool call entry has:
- `tool` — tool name
- `args` — arguments passed to the tool
- `result` — tool output

## Configuration

Environment variables (from `.env.agent.secret`):

| Variable      | Required | Default              | Description           |
|---------------|----------|----------------------|-----------------------|
| `LLM_API_KEY` | Yes      | —                    | API key for LLM       |
| `LLM_API_BASE`| Yes      | —                    | Base URL for API      |
| `LLM_MODEL`   | No       | `qwen3-coder-plus`   | Model name to use     |

## Error Handling

- **Missing question:** Returns `{"error": "No question provided"}`
- **Missing API key:** Returns `{"error": "LLM_API_KEY not set"}`
- **Missing API base:** Returns `{"error": "LLM_API_BASE not set"}`
- **LLLM error:** Returns `{"error": "..."}` with details
- **File not found:** Returns error message in tool result
- **Path traversal:** Returns error message in tool result

## Debug Output

All debug information is printed to stderr:
- Current iteration count
- LLM call status
- Tool execution details
- Final answer summary
