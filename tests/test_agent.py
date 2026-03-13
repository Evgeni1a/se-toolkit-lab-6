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
        cwd=root_dir
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
