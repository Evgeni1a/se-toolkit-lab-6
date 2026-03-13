# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider Choice
- **Provider**: Qwen Code API (deployed on VM)
- **Model**: `qwen3-coder-plus`
- **API Base**: `http://10.93.26.45:42002/v1` (VM IP address)
- **API Key**: `0.0.0.0` (from setup)
- **Reason**: 
  - 1000 free requests per day
  - Works in Russia without VPN
  - Already configured and tested on VM
  - Good tool calling support for future tasks

## Implementation Approach
1. **Code Structure**:
   - Use OpenAI-compatible client
   - Load configuration from `.env.agent.secret`
   - Minimal system prompt: "You are a helpful assistant. Answer questions concisely."
   - JSON output only to stdout
   - All logs and errors to stderr

2. **Error Handling**:
   - Check if question argument is provided
   - Validate API key and base URL are present
   - Catch and handle LLM API exceptions
   - Exit with code 1 on errors

3. **Configuration** (`.env.agent.secret`):
LLM_API_KEY=0.0.0.0
LLM_API_BASE=http://10.93.26.45:42002/v1
LLM_MODEL=qwen3-coder-plus


## Testing Strategy
- One regression test using subprocess
- Verify JSON format (fields: answer, tool_calls)
- Verify tool_calls is an empty list
- Test must pass locally

## Acceptance Criteria Check
- [ ] `plans/task-1.md` exists and is committed
- [ ] `agent.py` exists in root directory
- [ ] `uv run agent.py "question"` returns valid JSON with required fields
- [ ] API key stored in `.env.agent.secret` (not hardcoded)
- [ ] `AGENT.md` documents the solution
- [ ] One regression test exists and passes
- [ ] Git workflow followed: issue, branch, PR with "Closes #...", partner approval

## Timeline
- Plan creation: today
- Implementation: today
- Testing: today
- PR creation: today
