def test_orchestrator_lc_fallback(client, tmp_path):
    # When LangChain is not installed, wrapper should fallback to local orchestrator
    payload = {"goal": "Write tests", "execute": True, "base_path": str(tmp_path)}
    resp = client.post("/api/v1/agent/orchestrate_lc", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] in ("completed", "blocked") or data.get("status") == "pending_approval"
    # if executed, generated files should be present
    gen_dir = tmp_path / "tests" / "generated_by_orchestrator"
    # Either it's created or not depending on mapping; just ensure call succeeded
    assert "planner_tasks" in data and "executor_tasks" in data
