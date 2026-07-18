from pathlib import Path


def test_plan_execute_dry_run(client):
    payload = {"goal": "Build a scalable URL shortener with APIs, persistence, analytics"}
    resp = client.post("/api/v1/agent/plan_execute", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "planner_tasks" in data and "executor_tasks" in data
    # executor_tasks should be present and contain noop or create_file entries
    assert isinstance(data["executor_tasks"], list)


def test_plan_execute_run_creates_test_file(client, tmp_path):
    payload = {"goal": "Write tests for the project", "execute": True, "base_path": str(tmp_path)}
    resp = client.post("/api/v1/agent/plan_execute", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("results") is not None
    # verify file was created
    gen_dir = tmp_path / "tests" / "generated_by_planner"
    assert gen_dir.exists()
    files = list(gen_dir.glob("test_placeholder_*.py"))
    assert files, "No generated test files found"
