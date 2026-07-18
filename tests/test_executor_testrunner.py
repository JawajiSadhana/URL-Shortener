from pathlib import Path
import sys


def test_executor_test_runner_runs_pytest(client, tmp_path):
    # Create a test file
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert 1 == 1\n", encoding="utf-8")

    tasks = [
        {"id": 1, "action": "test_runner", "target": str(test_file), "timeout": 20}
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    results = data["results"]
    assert results[0]["status"] == "completed"
    # Ensure pytest exit code is success
    assert results[0]["returncode"] == 0
