import tempfile
from pathlib import Path


def test_executor_create_file(client, tmp_path):
    # Create a temp target path to write to
    target_file = tmp_path / "generated.txt"
    tasks = [
        {
            "id": 1,
            "title": "Create README",
            "action": "create_file",
            "path": str(target_file),
            "content": "Hello Executor",
        }
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    results = data["results"]
    assert isinstance(results, list) and len(results) == 1
    assert results[0]["status"] == "created"
    # Verify file content
    assert target_file.read_text(encoding="utf-8") == "Hello Executor"


def test_executor_blocks_unbounded_file_write(client, tmp_path):
    target_file = tmp_path / "large.txt"
    content = "x" * 20000
    tasks = [
        {
            "id": 1,
            "title": "Write huge file",
            "action": "create_file",
            "path": str(target_file),
            "content": content,
        }
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert results[0]["status"] == "blocked"
    assert "content size exceeds limit" in results[0]["error"]


def test_executor_blocks_secret_in_file(client, tmp_path):
    target_file = tmp_path / "secrets.txt"
    tasks = [
        {
            "id": 1,
            "title": "Write secret file",
            "action": "create_file",
            "path": str(target_file),
            "content": "password=hunter2",
        }
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert results[0]["status"] == "blocked"
    assert "secret material detected" in results[0]["error"]
