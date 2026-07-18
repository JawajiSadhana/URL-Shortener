import json
import logging
import os
import re
from typing import Dict, Optional

try:
    import langchain  # type: ignore
    from langchain.llms import OpenAI  # type: ignore
    HAS_LANGCHAIN = True
except Exception:
    HAS_LANGCHAIN = False

from app.config import settings
from app.agents.planner import PlannerAgent
from app.agents.executor import ExecutorAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.approval_store import create_approval, get_approval, transition_approval, set_approval_state_force, set_approver_metadata, update_execution_metadata, append_trace, append_decision, _create_trace_entry

logger = logging.getLogger(__name__)

MODEL_NAME_MAP = {
    "gpt-3.5-cheap": "gpt-3.5-turbo",
    "gpt-4-expensive": "gpt-4",
}


class LCOrchestratorWrapper:
    """Wrapper that uses LangChain/AutoGen orchestration when available.

    In this prototype we detect LangChain/AutoGen. If unavailable, we use a
    hand-rolled state machine orchestrator that manages planning, approval,
    execution, review, and trace persistence.
    """

    def __init__(self):
        self.planner = PlannerAgent()

    def run(self, goal: str, execute: bool = False, base_path: Optional[str] = None, require_approval: bool = False) -> Dict:
        if HAS_LANGCHAIN and self._openai_enabled():
            logger.info("Using LangChain orchestration flow")
            return self._run_langchain(goal, execute=execute, base_path=base_path, require_approval=require_approval)

        if HAS_LANGCHAIN:
            logger.warning("LangChain is installed but OPENAI_API_KEY is not configured; falling back to local state machine")
        else:
            logger.debug("LangChain not available; using hand-rolled state machine orchestrator")

        return self._run_state_machine(goal, execute=execute, base_path=base_path, require_approval=require_approval)

    def _openai_enabled(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _run_langchain(self, goal: str, execute: bool, base_path: Optional[str], require_approval: bool) -> Dict:
        planner_tasks = self._plan_with_langchain(goal)
        if planner_tasks is None:
            return self._run_state_machine(goal, execute=execute, base_path=base_path, require_approval=require_approval)

        executor_tasks = []
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

        initial_trace = [
            _create_trace_entry(name="planner", trace_type="llm_call", metadata={"goal": goal, "planner_tasks": planner_tasks}),
            _create_trace_entry(name="task_mapping", trace_type="decision", metadata={"executor_tasks": executor_tasks}),
        ]

        if require_approval:
            approval_id = create_approval(
                executor_tasks=executor_tasks,
                planner_tasks=planner_tasks,
                base_path=base_path,
                traces=initial_trace,
            )
            return {"status": "pending_approval", "approval_id": approval_id, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "assumptions": [], "decisions": []}

        if execute:
            executor = ExecutorAgent()
            execution = executor.execute(executor_tasks, return_metadata=True)
            results = execution["results"]
            files_touched = execution["files_touched"]
            retry_history = execution["retry_history"]
        else:
            results = None
            files_touched = []
            retry_history = []

        reviewer = ReviewerAgent()
        reviews = reviewer.review_paths(files_touched) if files_touched else []
        critical = any(any(issue.get("type") in ("secret", "forbidden") for issue in r.get("issues", [])) for r in reviews)
        status = "blocked" if critical else "completed"

        return {"status": status, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "results": results, "reviews": reviews}

    def _plan_with_langchain(self, goal: str) -> list[Dict] | None:
        try:
            llm = OpenAI(temperature=0, model_name=MODEL_NAME_MAP.get(settings.default_reasoning_model, "gpt-3.5-turbo"))
            prompt = self._build_langchain_prompt(goal)
            response = llm(prompt)
            return self._parse_planner_output(response)
        except Exception as exc:
            logger.warning("LangChain planning failed, falling back to local orchestrator: %s", exc)
            return None

    def _build_langchain_prompt(self, goal: str) -> str:
        return (
            "You are an intelligent planning assistant. "
            "Convert the user's goal into a JSON array of tasks. "
            "Each task should be an object with keys: id, title, description. "
            "Return only valid JSON with no surrounding markdown.\n"
            f"Goal: {goal}\n"
        )

    def _parse_planner_output(self, text: str) -> list[Dict] | None:
        if not text:
            return None

        cleaned = re.sub(r"```.*?```", "", text, flags=re.S).strip()
        cleaned = cleaned.strip('\n \t\"')

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return self._normalize_planner_tasks(parsed)
        except json.JSONDecodeError:
            pass

        match = re.search(r"(\[.*\])", cleaned, flags=re.S)
        if match:
            try:
                parsed = json.loads(match.group(1))
                if isinstance(parsed, list):
                    return self._normalize_planner_tasks(parsed)
            except json.JSONDecodeError:
                pass

        logger.warning("Unable to parse LangChain planner output: %s", cleaned)
        return None

    def _normalize_planner_tasks(self, tasks: list[Dict]) -> list[Dict]:
        normalized = []
        tid = 1
        for task in tasks:
            if not isinstance(task, dict):
                continue
            title = str(task.get("title") or task.get("name") or f"Task {tid}").strip()
            description = str(task.get("description") or task.get("details") or "").strip()
            normalized.append({"id": tid, "title": title, "description": description})
            tid += 1
        return normalized

    def _run_state_machine(self, goal: str, execute: bool, base_path: Optional[str], require_approval: bool) -> Dict:
        planner_tasks = self.planner.plan(goal)
        executor_tasks = []
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

        initial_trace = [
            _create_trace_entry(name="planner", trace_type="llm_call", metadata={"goal": goal, "planner_tasks": planner_tasks}),
            _create_trace_entry(name="task_mapping", trace_type="decision", metadata={"executor_tasks": executor_tasks}),
        ]

        if require_approval:
            approval_id = create_approval(
                executor_tasks=executor_tasks,
                planner_tasks=planner_tasks,
                base_path=base_path,
                traces=initial_trace,
            )
            return {"status": "pending_approval", "approval_id": approval_id, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "assumptions": [], "decisions": []}

        if execute:
            executor = ExecutorAgent()
            execution = executor.execute(executor_tasks, return_metadata=True)
            results = execution["results"]
            files_touched = execution["files_touched"]
            retry_history = execution["retry_history"]
        else:
            results = None
            files_touched = []
            retry_history = []

        reviewer = ReviewerAgent()
        reviews = reviewer.review_paths(files_touched) if files_touched else []
        critical = any(any(issue.get("type") in ("secret", "forbidden") for issue in r.get("issues", [])) for r in reviews)
        status = "blocked" if critical else "completed"

        return {"status": status, "planner_tasks": planner_tasks, "executor_tasks": executor_tasks, "results": results, "reviews": reviews}
