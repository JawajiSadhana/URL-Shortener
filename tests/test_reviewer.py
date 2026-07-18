from pathlib import Path


def test_reviewer_flags_todo_and_secret(client, tmp_path):
    p = tmp_path / "bad.py"
    p.write_text("# TODO: remove\npassword='hunter2'\nexec('2+2')\n", encoding="utf-8")

    resp = client.post("/api/v1/agent/review", json={"paths": [str(p)]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    reviews = data.get("reviews", [])
    assert len(reviews) == 1
    issues = reviews[0].get("issues", [])
    assert any(i["type"] == "todo" for i in issues)
    assert any(i["type"] == "secret" for i in issues)
    assert any(i["type"] == "forbidden" for i in issues)


def test_reviewer_missing_path(client):
    resp = client.post("/api/v1/agent/review", json={"paths": ["nonexistent.file"]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    reviews = data.get("reviews", [])
    assert reviews[0]["issues"][0]["type"] == "missing"
