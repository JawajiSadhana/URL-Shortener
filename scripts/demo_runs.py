import logging
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("demo")

client = TestClient(app)


def run_greenfield(goal: str):
    logger.info("=== Greenfield run ===")
    with tempfile.TemporaryDirectory(prefix="demo_greenfield_") as td:
        base = td
        resp = client.post("/api/v1/agent/orchestrate", json={"goal": goal, "execute": True, "base_path": base, "require_approval": False})
        logger.info(f"Orchestrator response status: {resp.status_code}")
        data = resp.json()
        logger.info(data)
        # list created files
        created = Path(base) / "tests" / "generated_by_orchestrator"
        if created.exists():
            logger.info("Created files:")
            for p in created.rglob("*"):
                if p.is_file():
                    logger.info(f" - {p}")
        else:
            logger.info("No files created in greenfield run")


def run_brownfield_with_approval(goal: str):
    logger.info("=== Brownfield run (require approval) ===")
    with tempfile.TemporaryDirectory(prefix="demo_brownfield_") as td:
        base = td
        # create pending approval
        resp = client.post("/api/v1/agent/orchestrate", json={"goal": goal, "execute": False, "base_path": base, "require_approval": True})
        data = resp.json()
        logger.info(data)
        approval_id = data.get("approval_id")
        if not approval_id:
            logger.error("No approval_id returned")
            return

        # Simulate approver reviewing and approving
        approve_resp = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": True, "approver_id": "demo-runner", "approver_comment": "Approved by demo script"})
        logger.info(f"Approve response: {approve_resp.status_code}")
        logger.info(approve_resp.json())
        # Fetch final approval record
        rec = client.get(f"/api/v1/agent/approval/{approval_id}").json()
        logger.info(rec)


def run_brownfield_with_question(goal: str):
    logger.info("=== Brownfield run (clarifying question) ===")
    with tempfile.TemporaryDirectory(prefix="demo_bq_") as td:
        base = td
        resp = client.post("/api/v1/agent/orchestrate", json={"goal": goal, "execute": False, "base_path": base, "require_approval": True})
        data = resp.json()
        logger.info(data)
        approval_id = data.get("approval_id")
        if not approval_id:
            logger.error("No approval_id returned")
            return

        # Append a clarifying decision (simulate reviewer asking a question)
        # The approver endpoint appends decisions when approving; to simulate a clarifying question
        # we will call the approve endpoint with approve=False and add a comment, then re-open/force approve.
        resp_reject = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": False, "approver_id": "reviewer-qa", "approver_comment": "Please clarify desired analytics granularity"})
        logger.info(f"Reject (question) response: {resp_reject.status_code}")
        logger.info(resp_reject.json())

        # Now for demo, force approval (simulate clarifying answered)
        force_resp = client.post("/api/v1/agent/approve", json={"approval_id": approval_id, "approve": True, "approver_id": "reviewer-qa", "approver_comment": "Clarification received; approving"})
        logger.info(f"Force approve response: {force_resp.status_code}")
        logger.info(force_resp.json())


if __name__ == "__main__":
    # Example goals
    greenfield_goal = "Create a URL shortener with admin, analytics, and observability"
    brownfield_goal = "Modify existing service to add analytics and admin"
    question_goal = "Add analytics to an existing URL shortener with clarifying questions"

    run_greenfield(greenfield_goal)
    run_brownfield_with_approval(brownfield_goal)
    run_brownfield_with_question(question_goal)
