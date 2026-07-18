from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List

from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.orchestrator import OrchestratorAgent
from app.agents.approval_store import get_approval, list_approvals, delete_approval, transition_approval, set_approval_state_force, set_approver_metadata, update_execution_metadata, append_trace, append_decision, _create_trace_entry
from app.agents.orchestrator_lc import LCOrchestratorWrapper

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

templates = Jinja2Templates(directory="app/templates")


class PlannerRequest(BaseModel):
    goal: str


class TaskModel(BaseModel):
    id: int
    title: str
    description: str


class PlannerResponse(BaseModel):
    tasks: List[TaskModel]


@router.post("/planner", response_model=PlannerResponse)
def planner_endpoint(req: PlannerRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal must be provided")

    agent = PlannerAgent()
    tasks = agent.plan(req.goal)
    return {"tasks": tasks}


class ExecuteRequest(BaseModel):
    tasks: List[dict]


class ExecuteResponse(BaseModel):
    results: List[dict]


@router.post("/execute", response_model=ExecuteResponse)
def execute_endpoint(req: ExecuteRequest):
    if not req.tasks:
        raise HTTPException(status_code=400, detail="Tasks must be provided")

    agent = ExecutorAgent()
    results = agent.execute(req.tasks)
    return {"results": results}


class PlanExecuteRequest(BaseModel):
    goal: str
    execute: bool = False
    # Optional path to prefix created files (useful for tests)
    base_path: str | None = None


class PlanExecuteResponse(BaseModel):
    planner_tasks: List[dict]
    executor_tasks: List[dict]
    results: List[dict] | None = None


@router.post("/plan_execute", response_model=PlanExecuteResponse)
def plan_execute(req: PlanExecuteRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal must be provided")

    planner = PlannerAgent()
    planner_tasks = planner.plan(req.goal)

    # Conservative mapping: only map "Write tests" task to a create_file action.
    executor_tasks = []
    tid = 1
    for pt in planner_tasks:
        title = pt.get("title", "").lower()
        if "write tests" in title or "tests" in title:
            # create a placeholder test file under base_path if provided
            base = req.base_path or "."
            path = f"{base}/tests/generated_by_planner/test_placeholder_{tid}.py"
            content = "def test_generated():\n    assert True\n"
            executor_tasks.append({
                "id": tid,
                "action": "create_file",
                "path": path,
                "content": content,
            })
        else:
            executor_tasks.append({"id": tid, "action": "noop", "note": pt.get("description")})
        tid += 1

    results = None
    if req.execute:
        executor = ExecutorAgent()
        results = executor.execute(executor_tasks)

    return {"planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "results": results}


class ReviewRequest(BaseModel):
    paths: List[str]


class ReviewResponse(BaseModel):
    reviews: List[dict]


@router.post("/review", response_model=ReviewResponse)
def review_endpoint(req: ReviewRequest):
    if not req.paths:
        raise HTTPException(status_code=400, detail="Paths must be provided")
    reviewer = ReviewerAgent()
    reviews = reviewer.review_paths(req.paths)
    return {"reviews": reviews}


class OrchestrateRequest(BaseModel):
    goal: str
    execute: bool = False
    base_path: str | None = None
    require_approval: bool = False


class OrchestrateResponse(BaseModel):
    status: str
    planner_tasks: List[dict]
    executor_tasks: List[dict]
    results: List[dict] | None = None
    reviews: List[dict] | None = None
    approval_id: str | None = None
    assumptions: List[str] | None = None
    decisions: List[str] | None = None


@router.post("/orchestrate", response_model=OrchestrateResponse)
def orchestrate_endpoint(req: OrchestrateRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal must be provided")
    orch = OrchestratorAgent()
    out = orch.run(req.goal, execute=req.execute, base_path=req.base_path, require_approval=req.require_approval)
    return out


@router.post("/orchestrate_lc", response_model=OrchestrateResponse)
def orchestrate_lc_endpoint(req: OrchestrateRequest):
    if not req.goal or not req.goal.strip():
        raise HTTPException(status_code=400, detail="Goal must be provided")
    orch = LCOrchestratorWrapper()
    out = orch.run(req.goal, execute=req.execute, base_path=req.base_path, require_approval=req.require_approval)
    return out


class ApproveRequest(BaseModel):
    approval_id: str
    approve: bool = True
    approver_id: str | None = None
    approver_comment: str | None = None


class ApproveResponse(BaseModel):
    status: str
    results: List[dict] | None = None
    reviews: List[dict] | None = None


@router.post("/approve", response_model=ApproveResponse)
def approve_endpoint(req: ApproveRequest):
    record = get_approval(req.approval_id)
    if not record:
        raise HTTPException(status_code=404, detail="Approval id not found")

    # Persist approver metadata for audit
    try:
        set_approver_metadata(req.approval_id, req.approver_id, req.approver_comment)
    except Exception:
        pass

    if not req.approve:
        append_trace(req.approval_id, _create_trace_entry(
            name="approval_decision",
            trace_type="decision",
            metadata={"approve": req.approve, "approver_id": req.approver_id, "approver_comment": req.approver_comment},
        ))
        transition_approval(req.approval_id, "rejected")
        # keep record for audit; do not delete
        return {"status": "rejected", "results": None, "reviews": None}

    append_decision(req.approval_id, {
        "approve": req.approve,
        "approver_id": req.approver_id,
        "approver_comment": req.approver_comment,
    })
    append_trace(req.approval_id, _create_trace_entry(
        name="approval_decision",
        trace_type="decision",
        metadata={"approve": req.approve, "approver_id": req.approver_id, "approver_comment": req.approver_comment},
    ))

    # Move to approved -> executing
    ok = transition_approval(req.approval_id, "approved")
    if not ok:
        # If transition not allowed, force to approved
        set_approval_state_force(req.approval_id, "approved")

    transition_approval(req.approval_id, "executing")

    # Execute stored executor tasks and capture metadata
    executor = ExecutorAgent()
    execution = executor.execute(record.get("executor_tasks", []), return_metadata=True)
    results = execution["results"]
    files_touched = execution["files_touched"]
    retry_history = execution["retry_history"]
    update_execution_metadata(req.approval_id, files_touched, retry_history)
    append_trace(req.approval_id, _create_trace_entry(
        name="executor",
        trace_type="tool_invocation",
        metadata={"executor_tasks": record.get("executor_tasks", [])},
        result={"results": results, "files_touched": files_touched, "retry_history": retry_history},
    ))

    # Move to reviewing
    transition_approval(req.approval_id, "reviewing")

    # Review generated files if any
    reviewer = ReviewerAgent()
    paths_to_review = [et.get("path") for et in record.get("executor_tasks", []) if et.get("action") == "create_file" and et.get("path")]
    reviews = reviewer.review_paths(paths_to_review) if paths_to_review else []
    append_trace(req.approval_id, _create_trace_entry(
        name="reviewer",
        trace_type="tool_invocation",
        metadata={"paths": paths_to_review},
        result={"reviews": reviews},
    ))

    # If critical issues, block; else complete
    critical = any(any(issue.get("type") in ("secret", "forbidden") for issue in r.get("issues", [])) for r in reviews)
    if critical:
        transition_approval(req.approval_id, "blocked")
        return {"status": "blocked", "results": results, "reviews": reviews}

    transition_approval(req.approval_id, "completed")
    return {"status": "completed", "results": results, "reviews": reviews}


@router.get("/approval/{approval_id}")
def get_approval_record(approval_id: str):
    rec = get_approval(approval_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Approval id not found")
    return rec


@router.get("/approval/list")
def list_approval_ids():
    return {"approvals": list_approvals()}


@router.get("/replay")
def replay_console(request: Request, approval_id: str | None = None):
    approvals = list_approvals()
    record = None
    if approval_id:
        record = get_approval(approval_id)
    return templates.TemplateResponse(
        "replay_console.html",
        {"request": request, "approval_id": approval_id, "record": record, "approvals": approvals},
    )
