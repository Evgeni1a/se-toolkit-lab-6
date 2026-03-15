#!/usr/bin/env python3
"""
Lab assistant agent — answers questions using an LLM with tools.

Usage:
    uv run agent.py "What does REST stand for?"

Output:
    {
      "answer": "...",
      "source": "wiki/rest-api.md#what-is-rest",
      "tool_calls": [...]
    }
"""

import json
import os
import sys
import time
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# Load LLM configuration from .env.agent.secret
load_dotenv(".env.agent.secret")

# Configuration
LLM_API_KEY = os.getenv('LLM_API_KEY')
LLM_API_BASE = os.getenv('LLM_API_BASE')
LLM_MODEL = os.getenv('LLM_MODEL', 'qwen3-coder-plus')
LMS_API_KEY = os.getenv('LMS_API_KEY')
AGENT_API_BASE_URL = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')

PROJECT_ROOT = Path(__file__).parent.absolute()

# Tool implementations
def list_files(path: str = ".") -> str:
    """List files and directories at the given path."""
    try:
        # Security: prevent directory traversal
        target_path = (PROJECT_ROOT / path).resolve()
        if not str(target_path).startswith(str(PROJECT_ROOT)):
            return "Error: Access denied - cannot list files outside project directory"
        
        if not target_path.exists():
            return f"Error: Path '{path}' does not exist"
        if not target_path.is_dir():
            return f"Error: '{path}' is not a directory"
        
        items = list(target_path.iterdir())
        result = []
        for item in items:
            suffix = "/" if item.is_dir() else ""
            result.append(f"{item.name}{suffix}")
        
        return "\n".join(result)
    except Exception as e:
        return f"Error listing files: {str(e)}"

def read_file(path: str) -> str:
    """Read and return the contents of a file."""
    try:
        # Security: prevent directory traversal
        target_path = (PROJECT_ROOT / path).resolve()
        if not str(target_path).startswith(str(PROJECT_ROOT)):
            return "Error: Access denied - cannot read files outside project directory"
        
        if not target_path.exists():
            return f"Error: File '{path}' does not exist"
        if not target_path.is_file():
            return f"Error: '{path}' is not a file"
        
        # Limit file size to avoid huge responses
        if target_path.stat().st_size > 100000:  # 100KB limit
            return "Error: File too large (max 100KB)"
        
        with open(target_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def query_api(method: str, path: str, body: str = None) -> str:
    """Call the backend API."""
    try:
        url = f"{AGENT_API_BASE_URL}{path}"
        headers = {
            "Authorization": f"Bearer {LMS_API_KEY}",
            "Content-Type": "application/json"
        }
        
        method = method.upper()
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            data = json.loads(body) if body else {}
            response = requests.post(url, headers=headers, json=data)
        else:
            return json.dumps({"status_code": 400, "body": f"Unsupported method: {method}"})
        
        try:
            body_json = response.json()
        except:
            body_json = response.text
        
        result = {
            "status_code": response.status_code,
            "body": body_json
        }
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"status_code": 500, "body": str(e)})

# Tool schemas for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file from the project repository. Use this to read file contents after discovering relevant files with list_files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative path from project root (e.g., 'wiki/rest-api.md')",
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
            "description": "List files and directories at a given path in the project repository. Use this to discover files in a directory.",    
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Relative directory path from project root (e.g., 'wiki/')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API. Use this to get real system data like item counts, scores, or analytics. For data-dependent questions, use this tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
                    },
                    "path": {
                        "type": "string",
                        "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')",
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST requests"
                    }
                },
                "required": ["method", "path"]
            }
        }
    }
]

def execute_tool(tool_name, tool_args):
    """Execute a tool by name with given arguments."""
    if tool_name == "list_files":
        return list_files(tool_args.get("path", "."))
    elif tool_name == "read_file":
        return read_file(tool_args["path"])
    elif tool_name == "query_api":
        return query_api(
            tool_args["method"],
            tool_args["path"],
            tool_args.get("body")
        )
    else:
        return f"Error: Unknown tool '{tool_name}'"

def agent_loop(question):
    """Main agentic loop with max 10 tool calls."""
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to tools. "
                "You can:\n"
                "- list_files and read_file to explore the wiki and source code\n"
                "- query_api to get real data from the backend API\n\n"
                "For questions about the system (framework, ports, status codes), read the source code.\n"
                "For questions about data (item counts, scores), use query_api.\n"
                "For wiki questions, read the wiki files.\n\n"
                "Always include the source of your answer:\n"
                "- For wiki/code: file path with section if possible\n"
                "- For API: the endpoint used\n\n"
                "After using tools, analyze the results and decide if you need more information or can provide the final answer."
            )
        },
        {"role": "user", "content": question}
    ]
    
    tool_calls_log = []
    
    
    try:
        client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_API_BASE)
        
        for _ in range(10):  # Max 10 tool calls
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            
            # If no tool calls, we're done
            if not message.tool_calls:
                final_answer = message.content or ""
                # Extract source from the response if present, or use default
                source = "agent response"
                # Simple heuristic: try to find file path in answer
                import re
                file_match = re.search(r'(wiki/[a-zA-Z0-9_/-]+\.md)', final_answer)
                if file_match:
                    source = file_match.group(1)
                
                result = {
                    "answer": final_answer,
                    "source": source,
                    "tool_calls": tool_calls_log
                }
                return result
            
            # Process tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                
                # Execute tool
                result = execute_tool(tool_name, tool_args)
                
                tool_calls_log.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result,
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })
        else:
            answer = message.get("content", "")
            source = ""
            
            if "source:" in answer.lower():
                matches = re.findall(
                    r"source:\s*`?([a-zA-Z0-9_/.-]+\.(py|md|json|yml|yaml))",
                    answer,
                    re.IGNORECASE,
                )
                if matches:
                    file_paths = [m[0] for m in matches]
                    for path in file_paths:
                        if path.endswith(".py"):
                            source = path
                            break
                    if not source:
                        source = file_paths[0]

            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log,
            }

    return {
        "answer": "Unable to find answer within maximum tool calls.",
        "source": "",
        "tool_calls": tool_calls_log,
    }

def main():
    if len(sys.argv) != 2:
        print('Usage: uv run agent.py "<question>"', file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    result = run_agentic_loop(question)
    
    # Только JSON в stdout, никаких других print
    print(json.dumps(result))

if __name__ == "__main__":
    main()
#ssssssssssssssssssssssssss