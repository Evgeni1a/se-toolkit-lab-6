import subprocess
import json
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent


def test_agent_basic():
    """Test that agent.py returns valid JSON with answer and tool_calls"""

    result = subprocess.run(
        [sys.executable, "agent.py", "What is 2+2?"],
        capture_output=True,
        text=True,
        cwd=root_dir,
    )

    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"

    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"
    assert len(output["tool_calls"]) == 0, "'tool_calls' should be empty for Task 1"


def test_agent_merge_conflict():
    """Test that agent uses read_file to answer 'How do you resolve a merge conflict?'"""

    result = subprocess.run(
        [sys.executable, "agent.py", "How do you resolve a merge conflict?"],
        capture_output=True,
        text=True,
        cwd=root_dir,
    )

    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check that read_file was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [call["tool"] for call in tool_calls]
    assert "read_file" in tool_names, "Expected read_file to be called"

    # Check that source references wiki/git-workflow.md
    source = output["source"]
    assert "wiki/git-workflow.md" in source, (
        f"Expected 'wiki/git-workflow.md' in source, got: {source}"
    )


def test_agent_list_wiki_files():
    """Test that agent uses list_files when asked about wiki files"""

    result = subprocess.run(
        [sys.executable, "agent.py", "What files are in the wiki?"],
        capture_output=True,
        text=True,
        cwd=root_dir,
    )

    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check that list_files was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [call["tool"] for call in tool_calls]
    assert "list_files" in tool_names, "Expected list_files to be called"

    # Check that list_files was called with path "wiki"
    list_files_calls = [call for call in tool_calls if call["tool"] == "list_files"]
    assert any(call["args"].get("path") == "wiki" for call in list_files_calls), (
        "Expected list_files to be called with path='wiki'"
    )


def test_agent_framework_question():
    """Test that agent uses query_api or read_file for system framework question"""

    result = subprocess.run(
        [sys.executable, "agent.py", "What Python web framework does the backend use?"],
        capture_output=True,
        text=True,
        cwd=root_dir,
    )

    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "source" in output, "Missing 'source' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check that either query_api or read_file was used
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [call["tool"] for call in tool_calls]
    # Agent can use query_api to check the system or read_file to check source code
    assert "query_api" in tool_names or "read_file" in tool_names, (
        "Expected query_api or read_file to be called for system question"
    )

    # Check that answer mentions FastAPI or similar framework
    answer = output["answer"].lower()
    assert "fastapi" in answer or "flask" in answer or "django" in answer or "framework" in answer, (
        f"Expected answer to mention framework, got: {output['answer']}"
    )


def test_agent_item_count_question():
    """Test that agent uses query_api for data-dependent item count question"""

    result = subprocess.run(
        [sys.executable, "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        cwd=root_dir,
    )

    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON: {result.stdout}"

    # Check required fields
    assert "answer" in output, "Missing 'answer' field"
    assert "tool_calls" in output, "Missing 'tool_calls' field"

    # Check that query_api was used for data-dependent question
    tool_calls = output["tool_calls"]
    assert len(tool_calls) > 0, "Expected at least one tool call"

    tool_names = [call["tool"] for call in tool_calls]
    assert "query_api" in tool_names, (
        "Expected query_api to be called for data-dependent question"
    )

    # Check that query_api was called with GET /items/
    query_api_calls = [call for call in tool_calls if call["tool"] == "query_api"]
    assert any(
        call["args"].get("method") == "GET" and "/items" in call["args"].get("path", "")
        for call in query_api_calls
    ), "Expected query_api to be called with GET /items/"
