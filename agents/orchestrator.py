from typing import List, Dict, Optional
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.approval_store import create_approval, _create_trace_entry


class OrchestratorAgent:
    """Simple orchestrator that runs plan -> execute -> review loop.

    This is a minimal prototype that maps planner tasks conservatively to
    executor tasks (create_file or noop), optionally requires approval, runs
    execution, and runs the reviewer on generated artifacts.
    """

    def run(self, goal: str, execute: bool = False, base_path: Optional[str] = None, require_approval: bool = False) -> Dict:
        planner = PlannerAgent()
        planner_tasks = planner.plan(goal)

        # Map planner tasks to executor tasks (same conservative mapping)
        executor_tasks: List[Dict] = []
        tid = 1
        for pt in planner_tasks:
            title = pt.get("title", "").lower()
            if "write tests" in title or "tests" in title:
                base = base_path or "."
                path = f"{base}/tests/generated_by_orchestrator/test_placeholder_{tid}.py"
                content = "def test_generated():\n    assert True\n"
                executor_tasks.append({"id": tid, "action": "create_file", "path": path, "content": content})
            else:
                executor_tasks.append({"id": tid, "action": "noop", "note": pt.get("description")})
            tid += 1

        if require_approval:
            initial_trace = [
                _create_trace_entry(name="planner", trace_type="llm_call", metadata={"goal": goal, "planner_tasks": planner_tasks}),
                _create_trace_entry(name="task_mapping", trace_type="decision", metadata={"executor_tasks": executor_tasks}),
            ]
            approval_id = create_approval(
                executor_tasks=executor_tasks,
                planner_tasks=planner_tasks,
                base_path=base_path,
                traces=initial_trace,
            )
            return {"status": "pending_approval", "approval_id": approval_id, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "assumptions": [], "decisions": []}

        results = None
        files_touched: List[str] = []
        retry_history: List[Dict[str, Any]] = []
        if execute:
            executor = ExecutorAgent()
            execution = executor.execute(executor_tasks, return_metadata=True)
            results = execution["results"]
            files_touched = execution["files_touched"]
            retry_history = execution["retry_history"]

        # Run reviewer on created files
        reviewer = ReviewerAgent()
        paths_to_review: List[str] = files_touched if files_touched else []

        reviews = reviewer.review_paths(paths_to_review) if paths_to_review else []

        # Block if critical issues found
        critical = False
        for r in reviews:
            for issue in r.get("issues", []):
                if issue.get("type") in ("secret", "forbidden"):
                    critical = True

        status = "blocked" if critical else "completed"

        return {"status": status, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "results": results, "reviews": reviews}
