import sys


def test_executor_shell_runs_python(client):
    # Use current interpreter to run a small print command
    cmd = [sys.executable, "-c", "print('executor-shell')"]
    tasks = [
        {"id": 1, "title": "Run python print", "action": "shell", "command": cmd, "timeout": 5}
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    results = data["results"]
    assert results[0]["status"] == "completed"
    assert "executor-shell" in results[0]["stdout"]


def test_executor_blocks_destructive_shell(client):
    cmd = [sys.executable, "-c", "print('safe')"]
    # simulate a destructive shell command by string match, not actual dangerous execution
    tasks = [
        {"id": 1, "title": "Dangerous shell", "action": "shell", "command": ["rm", "-rf", "/tmp/test"], "timeout": 5}
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert results[0]["status"] == "blocked"
    assert "destructive shell command blocked" in results[0]["error"]
