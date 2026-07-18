def test_orchestrator_approval_flow(client, tmp_path):
    # Create a pending orchestration
    resp = client.post("/api/v1/agent/orchestrate", json={"goal": "Write tests", "require_approval": True, "base_path": str(tmp_path)})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "pending_approval"
    approval_id = data.get("approval_id")
    assert approval_id

    # Approve it
    resp2 = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": True})
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["status"] == "completed"
    # ensure files created
    gen_dir = tmp_path / "tests" / "generated_by_orchestrator"
    assert gen_dir.exists()


def test_orchestrator_reject_flow(client, tmp_path):
    resp = client.post("/api/v1/agent/orchestrate", json={"goal": "Write tests", "require_approval": True, "base_path": str(tmp_path)})
    data = resp.json()
    approval_id = data.get("approval_id")

    # Reject it
    resp2 = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": False})
    assert resp2.status_code == 200, resp2.text
    data2 = resp2.json()
    assert data2["status"] == "rejected"

    # Ensure record remains and state shows rejected
    status_resp = client.get(f"/api/v1/agent/approval/{approval_id}")
    assert status_resp.status_code == 200
    rec = status_resp.json()
    assert rec.get("state") == "rejected"
    # New structured fields should exist and be lists
    assert isinstance(rec.get("assumptions"), list)
    assert isinstance(rec.get("decisions"), list)
    assert isinstance(rec.get("files_touched"), list)
    assert isinstance(rec.get("retry_history"), list)


def test_approval_exec_metadata_persists(client, tmp_path):
    resp = client.post("/api/v1/agent/orchestrate", json={"goal": "Write tests", "require_approval": True, "base_path": str(tmp_path)})
    approval_id = resp.json().get("approval_id")

    resp2 = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": True})
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "completed"

    status_resp = client.get(f"/api/v1/agent/approval/{approval_id}")
    assert status_resp.status_code == 200
    rec = status_resp.json()
    assert isinstance(rec.get("files_touched"), list)
    assert len(rec.get("files_touched")) >= 1
    assert isinstance(rec.get("retry_history"), list)
    assert isinstance(rec.get("traces"), list)
    assert len(rec.get("traces")) >= 2


def test_approve_records_approver_metadata(client, tmp_path):
    resp = client.post("/api/v1/agent/orchestrate", json={"goal": "Write tests", "require_approval": True, "base_path": str(tmp_path)})
    assert resp.status_code == 200, resp.text
    approval_id = resp.json().get("approval_id")

    resp2 = client.post("/api/v1/agent/approve", json={
        "approval_id": approval_id,
        "approve": True,
        "approver_id": "reviewer-1",
        "approver_comment": "Approved for execution",
    })
    assert resp2.status_code == 200, resp2.text
    assert resp2.json()["status"] == "completed"

    status_resp = client.get(f"/api/v1/agent/approval/{approval_id}")
    assert status_resp.status_code == 200
    rec = status_resp.json()
    assert rec.get("state") == "completed"
    assert rec.get("approver_id") == "reviewer-1"
    assert rec.get("approver_comment") == "Approved for execution"
