#!/usr/bin/env python
"""
Documentation Agent for Task 2.
Implements agentic loop with read_file and list_files tools.
"""

import json
import sys
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env.agent.secret")

# Project root directory
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool call iterations
MAX_ITERATIONS = 10

# Tool schemas for OpenAI function calling
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki')",
                    }
                },
                "required": ["path"],
            },
        },
    },
]

# System prompt for the documentation agent
SYSTEM_PROMPT = """You are a documentation assistant for a software engineering project.
You have access to the project wiki files through two tools:

1. list_files(path) - lists files in a directory
2. read_file(path) - reads file contents

Workflow:
1. Use list_files("wiki") to discover available documentation files
2. Use read_file() to read relevant files and find the answer
3. Look for section headers (# Section Name) to create precise source anchors
4. Return your final answer as JSON with:
   - answer: the concise answer to the question
   - source: file path with section anchor (e.g., wiki/git-workflow.md#resolving-merge-conflicts)

Always cite the exact file path and section that contains the answer.
If the answer spans multiple sections, choose the most relevant one.
Respond with valid JSON only when giving the final answer."""


def validate_path(relative_path: str) -> Path:
    """
    Validate that a path does not escape the project directory.

    Args:
        relative_path: Relative path from project root

    Returns:
        Absolute Path object

    Raises:
        ValueError: If path is absolute or escapes project directory
    """
    # Reject absolute paths
    if os.path.isabs(relative_path):
        raise ValueError(f"Absolute paths not allowed: {relative_path}")

    # Normalize path (resolves .. and .)
    normalized = os.path.normpath(relative_path)

    # Build full path
    full_path = PROJECT_ROOT / normalized

    # Verify the resolved path is within PROJECT_ROOT
    try:
        full_path.resolve().relative_to(PROJECT_ROOT)
    except ValueError:
        raise ValueError(f"Path traversal detected: {relative_path}")

    return full_path


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    try:
        full_path = validate_path(path)
    except ValueError as e:
        return f"Error: {str(e)}"

    if not full_path.exists():
        return f"Error: File not found: {path}"

    if not full_path.is_file():
        return f"Error: Not a file: {path}"

    try:
        return full_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing of entries, or error message
    """
    try:
        full_path = validate_path(path)
    except ValueError as e:
        return f"Error: {str(e)}"

    if not full_path.exists():
        return f"Error: Directory not found: {path}"

    if not full_path.is_dir():
        return f"Error: Not a directory: {path}"

    entries: list[str] = []
    for entry in full_path.iterdir():
        suffix = "/" if entry.is_dir() else ""
        entries.append(entry.name + suffix)

    return "\n".join(sorted(entries))


def execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    """
    Execute a tool by name with given arguments.

    Args:
        tool_name: Name of the tool to execute
        args: Arguments for the tool

    Returns:
        Tool result as string
    """
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    else:
        return f"Error: Unknown tool: {tool_name}"


def parse_final_answer(content: str) -> dict[str, str]:
    """
    Parse the final answer from LLM content.
    Tries to extract JSON, falls back to treating entire content as answer.

    Args:
        content: Raw content from LLM

    Returns:
        Dict with 'answer' and 'source' keys
    """
    # Try to find JSON in the content
    content = content.strip()

    # Check if content starts with { and ends with }
    if content.startswith("{") and content.endswith("}"):
        try:
            parsed = json.loads(content)
            return {
                "answer": parsed.get("answer", content),
                "source": parsed.get("source", "unknown"),
            }
        except json.JSONDecodeError:
            pass

    # Try to extract JSON from code block
    json_match = re.search(r'\{[^{}]*"answer"[^{}]*\}', content, re.DOTALL)
    if json_match:
        try:
            parsed = json.loads(json_match.group())
            return {
                "answer": parsed.get("answer", content),
                "source": parsed.get("source", "unknown"),
            }
        except json.JSONDecodeError:
            pass

    # Fallback: use entire content as answer, no source
    return {"answer": content, "source": "unknown"}


def run_agentic_loop(question: str, client: OpenAI, model: str) -> dict[str, Any]:
    """
    Run the agentic loop: LLM -> tool calls -> execute -> back to LLM.

    Args:
        question: User's question
        client: OpenAI client
        model: Model name to use

    Returns:
        Result dict with answer, source, and tool_calls
    """
    from openai.types.chat import (
        ChatCompletionMessageParam,
        ChatCompletionToolMessageParam,
    )

    # Initialize messages with system prompt and user question
    messages: list[ChatCompletionMessageParam] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]

    # Track all tool calls for output
    tool_calls_log: list[dict[str, Any]] = []

    iterations = 0

    while iterations < MAX_ITERATIONS:
        iterations += 1
        print(f"Iteration {iterations}/{MAX_ITERATIONS}", file=sys.stderr)

        # Call LLM with tool schemas
        print("Calling LLM...", file=sys.stderr)
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_choice="auto",
            temperature=0.7,
        )

        assistant_message = response.choices[0].message

        # Check if LLM wants to call tools
        if assistant_message.tool_calls:
            print(
                f"LLM requested {len(assistant_message.tool_calls)} tool call(s)",
                file=sys.stderr,
            )

            # Build tool_calls list for the assistant message
            tool_calls_data = []
            for tc in assistant_message.tool_calls:
                tool_calls_data.append(
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )

            # Add assistant message with tool calls to conversation
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_message.content,
                    "tool_calls": tool_calls_data,
                }
            )

            # Execute each tool call
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)

                # Execute the tool
                result = execute_tool(tool_name, args)

                # Log the tool call
                tool_calls_log.append(
                    {"tool": tool_name, "args": args, "result": result}
                )

                # Add tool result to messages
                tool_message: ChatCompletionToolMessageParam = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result,
                }
                messages.append(tool_message)

                print(f"Tool result ({len(result)} chars)", file=sys.stderr)

            # Continue loop - LLM will decide next action

        else:
            # No tool calls - this is the final answer
            print("LLLM returned final answer", file=sys.stderr)

            final_content = assistant_message.content or ""
            parsed = parse_final_answer(final_content)

            return {
                "answer": parsed["answer"],
                "source": parsed["source"],
                "tool_calls": tool_calls_log,
            }

    # Max iterations reached
    print("Max iterations reached", file=sys.stderr)

    # Try to extract answer from last assistant message
    if messages and messages[-1].get("role") == "assistant":
        final_content = messages[-1].get("content", "")
        parsed = parse_final_answer(final_content)
        return {
            "answer": parsed["answer"],
            "source": parsed["source"],
            "tool_calls": tool_calls_log,
        }

    # No answer found
    return {
        "answer": "Could not find answer after maximum iterations",
        "source": "unknown",
        "tool_calls": tool_calls_log,
    }


def main():
    print("Starting agent...", file=sys.stderr)

    if len(sys.argv) < 2:
        print(json.dumps({"error": "No question provided"}), file=sys.stdout)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen3-coder-plus")

    if not api_key:
        print(
            json.dumps({"error": "LLM_API_KEY not set in .env.agent.secret"}),
            file=sys.stdout,
        )
        sys.exit(1)

    if not api_base:
        print(
            json.dumps({"error": "LLM_API_BASE not set in .env.agent.secret"}),
            file=sys.stdout,
        )
        sys.exit(1)

    print(f"Using model: {model}", file=sys.stderr)
    print(f"API Base: {api_base}", file=sys.stderr)

    try:
        client = OpenAI(api_key=api_key, base_url=api_base)

        # Run the agentic loop
        result = run_agentic_loop(question, client, model)

        print(f"Final answer ({len(result['answer'])} chars)", file=sys.stderr)
        print(f"Source: {result['source']}", file=sys.stderr)
        print(f"Tool calls: {len(result['tool_calls'])}", file=sys.stderr)

        print(json.dumps(result, ensure_ascii=False), file=sys.stdout)

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg, file=sys.stderr)
        print(json.dumps({"error": error_msg}), file=sys.stdout)
        sys.exit(1)


if __name__ == "__main__":
    main()
