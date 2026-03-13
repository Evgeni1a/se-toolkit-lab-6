# LLM Agent for Task 1

## Overview
CLI agent that calls LLM and returns JSON response.

## Architecture
- Uses OpenAI-compatible client
- Configuration from environment variables
- Question → LLM → JSON output

## LLM Provider
- **Provider**: Qwen Code API
- **Model**: qwen3-coder-plus
- **API Base**: http://10.93.26.45:42002/v1

## Usage
```bash
uv run agent.py "What is REST?"
