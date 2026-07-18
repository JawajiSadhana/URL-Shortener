import re
from pathlib import Path
import tempfile
from typing import Any, List, Dict
import subprocess
import sys

from app.config import settings
from app.utils.tokenizer import estimate_tokens, estimate_cost

MAX_FILE_WRITE_SIZE = 10_000
DANGEROUS_SHELL_PATTERNS = [
    re.compile(r"\brm\b.*\-rf"),
    re.compile(r"\bchmod\b"),
    re.compile(r"\bchown\b"),
    re.compile(r"\bdd\b"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"\bshutdown\b|\breboot\b"),
    re.compile(r"\b(init|systemctl)\b"),
    re.compile(r"\bcurl\b.*\|.*sh\b"),
    re.compile(r"\bwget\b.*\|.*sh\b"),
]
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"api[_-]?key\W*[:=]\W*['\"]?[A-Za-z0-9-_]{16,}['\"]?", re.I),
    re.compile(r"password\W*[:=]\W*['\"]?.{4,}['\"]?", re.I),
    re.compile(r"secret\W*[:=]\W*['\"]?.{4,}['\"]?", re.I),
]

MODEL_COSTS = {
    "gpt-3.5-cheap": settings.cost_per_1k_tokens,
    "gpt-4-expensive": settings.cost_per_1k_tokens * settings.expensive_model_multiplier,
}
MODEL_ROUTING = {
    "code_search": settings.default_search_model,
    "shell": settings.default_search_model,
    "create_file": settings.default_reasoning_model,
    "test_runner": settings.default_reasoning_model,
}


def _normalize_shell_command(cmd: Any) -> str:
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(part) for part in cmd)
    return str(cmd)


def _contains_secret(content: str) -> bool:
    return any(p.search(content) for p in SECRET_PATTERNS)


def _is_destructive_shell_command(command: str) -> bool:
    cleaned = command.replace("\\\"", "").replace("\"", "")
    return any(p.search(cleaned) for p in DANGEROUS_SHELL_PATTERNS)


def _estimate_tokens(content: str, model: str = settings.default_reasoning_model) -> int:
    return estimate_tokens(content, model)


def _estimate_cost(tokens: int, model: str) -> float:
    return estimate_cost(tokens, model, settings.cost_per_1k_tokens, settings.expensive_model_multiplier)


def _route_model(action: str) -> str:
    return MODEL_ROUTING.get(action, settings.default_reasoning_model)


def _estimate_action_cost(action: str, task: Dict[str, Any]) -> Dict[str, Any]:
    model = _route_model(action)
    if action == "create_file":
        text = str(task.get("content", ""))
    elif action == "shell":
        text = _normalize_shell_command(task.get("command", ""))
    elif action == "code_search":
        text = str(task.get("query", ""))
    elif action == "test_runner":
        text = str(task.get("target") or task.get("path") or "")
    else:
        text = ""
    tokens = _estimate_tokens(text, model)
    cost = _estimate_cost(tokens, model)
    return {"model": model, "tokens": tokens, "cost": cost}


def _is_unbounded_write(path: str, content: str) -> str | None:
    if len(content) > MAX_FILE_WRITE_SIZE:
        return f"content size exceeds limit ({len(content)} > {MAX_FILE_WRITE_SIZE})"
    p = Path(path)
    try:
        resolved = p.resolve()
    except Exception:
        return "invalid path"
    root = Path.cwd().resolve()
    # allow writes under system temp directories for trusted tests
    try:
        temp_root = Path(tempfile.gettempdir()).resolve()
    except Exception:
        temp_root = None
    if temp_root and (temp_root == resolved or temp_root in resolved.parents):
        return None
    if root not in resolved.parents and resolved != root:
        return "file write outside allowed workspace"
    return None


def guardrail_issues(task: Dict) -> List[str]:
    action = task.get("action")
    issues: List[str] = []
    if action == "create_file":
        path = task.get("path")
        content = str(task.get("content", ""))
        if _contains_secret(content):
            issues.append("secret material detected in file content")
        if path:
            unbounded = _is_unbounded_write(path, content)
            if unbounded:
                issues.append(unbounded)
    elif action == "shell":
        command = _normalize_shell_command(task.get("command", ""))
        if _contains_secret(command):
            issues.append("secret material detected in shell command")
        if _is_destructive_shell_command(command):
            issues.append("destructive shell command blocked")
    return issues


class ExecutorAgent:
    """Minimal Executor agent prototype.

    Supported actions (prototype):
    - create_file: writes `content` to `path` (creates parent dirs)
    - noop / missing action: marks task skipped
    All other actions are returned as unsupported.
    """

    def execute(self, tasks: List[Dict], return_metadata: bool = False):
        results: List[Dict] = []
        files_touched: List[str] = []
        retry_history: List[Dict[str, Any]] = []

        for t in tasks:
            tid = t.get("id")
            action = t.get("action")
            max_retries = int(t.get("retry", 0) or settings.max_task_retries)
            max_retries = min(max_retries, settings.max_task_retries)
            attempt = 1
            model = _route_model(action)
            accumulated_cost = 0.0
            while True:
                if action == "create_file":
                    path = t.get("path")
                    content = t.get("content", "")
                    if not path:
                        results.append({"task_id": tid, "status": "error", "error": "missing path"})
                        break
                    issues = guardrail_issues(t)
                    if issues:
                        results.append({"task_id": tid, "status": "blocked", "error": "; ".join(issues), "issues": issues})
                        break
                    costs = _estimate_action_cost(action, t)
                    model = costs["model"]
                    tokens = costs["tokens"]
                    cost = costs["cost"]
                    if settings.enable_cost_controls and accumulated_cost + cost > settings.execution_budget_limit:
                        results.append({"task_id": tid, "status": "blocked", "error": "cost budget exceeded", "model": model, "tokens": tokens, "cost": cost})
                        break
                    try:
                        p = Path(path)
                        if not p.parent.exists():
                            p.parent.mkdir(parents=True, exist_ok=True)
                        p.write_text(str(content), encoding="utf-8")
                        results.append({"task_id": tid, "status": "created", "path": path, "model": model, "tokens": tokens, "cost": cost})
                        files_touched.append(path)
                        accumulated_cost += cost
                        break
                    except Exception as e:
                        if attempt <= max_retries:
                            retry_history.append({"task_id": tid, "action": action, "attempt": attempt, "reason": str(e)})
                            attempt += 1
                            continue
                        results.append({"task_id": tid, "status": "error", "error": str(e)})
                        break
                elif not action or action == "noop":
                    results.append({"task_id": tid, "status": "skipped"})
                    break
                elif action == "shell":
                    cmd = t.get("command")
                    timeout = t.get("timeout", 5)
                    if not cmd:
                        results.append({"task_id": tid, "status": "error", "error": "missing command"})
                        break
                    issues = guardrail_issues(t)
                    if issues:
                        results.append({"task_id": tid, "status": "blocked", "error": "; ".join(issues), "issues": issues})
                        break
                    costs = _estimate_action_cost(action, t)
                    model = costs["model"]
                    tokens = costs["tokens"]
                    cost = costs["cost"]
                    if settings.enable_cost_controls and accumulated_cost + cost > settings.execution_budget_limit:
                        results.append({"task_id": tid, "status": "blocked", "error": "cost budget exceeded", "model": model, "tokens": tokens, "cost": cost})
                        break
                    command_str = _normalize_shell_command(cmd)
                    try:
                        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                        if completed.returncode != 0 and attempt <= max_retries:
                            retry_history.append({"task_id": tid, "action": action, "attempt": attempt, "reason": completed.stderr or completed.stdout or f"returncode {completed.returncode}"})
                            attempt += 1
                            continue
                        results.append({
                            "task_id": tid,
                            "status": "completed",
                            "returncode": completed.returncode,
                            "stdout": completed.stdout,
                            "stderr": completed.stderr,
                            "model": model,
                            "tokens": tokens,
                            "cost": cost,
                        })
                        accumulated_cost += cost
                        break
                    except Exception as e:
                        if attempt <= max_retries:
                            retry_history.append({"task_id": tid, "action": action, "attempt": attempt, "reason": str(e)})
                            attempt += 1
                            continue
                        results.append({"task_id": tid, "status": "error", "error": str(e)})
                        break
                elif action == "code_search":
                    query = t.get("query")
                    path = t.get("path")
                    if not query:
                        results.append({"task_id": tid, "status": "error", "error": "missing query"})
                        break
                    if not path:
                        results.append({"task_id": tid, "status": "error", "error": "missing path"})
                        break
                    try:
                        base = Path(path)
                        matches = []
                        if not base.exists():
                            results.append({"task_id": tid, "status": "error", "error": "path does not exist"})
                            break
                        for p in base.rglob("*"):
                            if p.is_file():
                                try:
                                    text = p.read_text(encoding="utf-8")
                                except Exception:
                                    continue
                                if query in text:
                                    lines = []
                                    for i, line in enumerate(text.splitlines(), start=1):
                                        if query in line:
                                            lines.append({"line": i, "text": line})
                                    matches.append({"path": str(p), "matches": lines})
                        if matches:
                            results.append({"task_id": tid, "status": "found", "matches": matches})
                        else:
                            results.append({"task_id": tid, "status": "not_found"})
                        break
                    except Exception as e:
                        results.append({"task_id": tid, "status": "error", "error": str(e)})
                        break
                elif action == "test_runner":
                    target = t.get("target") or t.get("path")
                    timeout = t.get("timeout", 30)
                    if not target:
                        results.append({"task_id": tid, "status": "error", "error": "missing target"})
                        break
                    try:
                        cmd = [sys.executable, "-m", "pytest", target, "-q"]
                        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
                        if completed.returncode != 0 and attempt <= max_retries:
                            retry_history.append({"task_id": tid, "action": action, "attempt": attempt, "reason": completed.stderr or completed.stdout or f"returncode {completed.returncode}"})
                            attempt += 1
                            continue
                        results.append({
                            "task_id": tid,
                            "status": "completed",
                            "returncode": completed.returncode,
                            "stdout": completed.stdout,
                            "stderr": completed.stderr,
                        })
                        break
                    except Exception as e:
                        if attempt <= max_retries:
                            retry_history.append({"task_id": tid, "action": action, "attempt": attempt, "reason": str(e)})
                            attempt += 1
                            continue
                        results.append({"task_id": tid, "status": "error", "error": str(e)})
                        break
                else:
                    results.append({"task_id": tid, "status": "unsupported", "action": action})
                    break

        if return_metadata:
            return {"results": results, "files_touched": files_touched, "retry_history": retry_history}
        return results
