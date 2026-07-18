def test_planner_returns_tasks(client):
    payload = {
        "goal": "Build a scalable URL shortener with APIs, persistence, analytics"
    }
    resp = client.post("/api/v1/agent/planner", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "tasks" in data
    assert isinstance(data["tasks"], list)
    # Ensure analytics-related task is present
    assert any("analytics" in (t.get("title") or "").lower() or "analytics" in (t.get("description") or "").lower() for t in data["tasks"]) 
