import subprocess
import json
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent

def test_system_agent_framework_question():
    """Test that agent uses read_file for framework questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "What Python framework does the backend use?"],
        capture_output=True,
        text=True,
        cwd=root_dir
    )
    
    assert result.returncode == 0, f"Error: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Invalid JSON: {result.stdout}"
    
    assert "answer" in output
    assert "tool_calls" in output
    assert "source" in output
    
    # Should have used read_file
    tool_names = [t["tool"] for t in output["tool_calls"]]
    assert "read_file" in tool_names or "list_files" in tool_names

def test_system_agent_data_question():
    """Test that agent uses query_api for data questions."""
    result = subprocess.run(
        [sys.executable, "agent.py", "How many items are in the database?"],
        capture_output=True,
        text=True,
        cwd=root_dir
    )
    
    assert result.returncode == 0, f"Error: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Invalid JSON: {result.stdout}"
    
    assert "answer" in output
    assert "tool_calls" in output
    
    # Should have used query_api
    tool_names = [t["tool"] for t in output["tool_calls"]]
    assert "query_api" in tool_names
