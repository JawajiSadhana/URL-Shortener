from pathlib import Path


def test_orchestrator_dry_requires_approval(client):
    payload = {"goal": "Build a URL shortener", "require_approval": True}
    resp = client.post("/api/v1/agent/orchestrate", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert "executor_tasks" in data


def test_orchestrator_execute_and_review(client, tmp_path):
    payload = {"goal": "Write tests", "execute": True, "base_path": str(tmp_path)}
    resp = client.post("/api/v1/agent/orchestrate", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    # Should complete and create files and reviews (no critical issues)
    assert data["status"] == "completed"
    assert data.get("results") is not None
    # Check generated file exists
    gen_dir = tmp_path / "tests" / "generated_by_orchestrator"
    assert gen_dir.exists()
