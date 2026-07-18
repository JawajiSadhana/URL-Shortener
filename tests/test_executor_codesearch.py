from pathlib import Path


def test_executor_code_search_finds_token(client, tmp_path):
    # Create files under tmp_path
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "sub" / "b.txt"
    f2.parent.mkdir(parents=True, exist_ok=True)
    f1.write_text("hello\nUNIQUE_SEARCH_TOKEN here\nbye", encoding="utf-8")
    f2.write_text("nothing here", encoding="utf-8")

    tasks = [
        {"id": 1, "action": "code_search", "path": str(tmp_path), "query": "UNIQUE_SEARCH_TOKEN"}
    ]

    resp = client.post("/api/v1/agent/execute", json={"tasks": tasks})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    results = data["results"]
    assert results[0]["status"] == "found"
    matches = results[0].get("matches", [])
    assert any(m["path"].endswith("a.txt") for m in matches)
