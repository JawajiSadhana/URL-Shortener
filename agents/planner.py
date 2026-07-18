from typing import List, Dict


class PlannerAgent:
    """Minimal Planner agent that converts a high-level goal into structured tasks.

    This is a simple, rule-based prototype intended to be a starting point for
    an agentic workflow. It inspects keywords in the goal and emits a small
    ordered list of actionable tasks.
    """

    def plan(self, goal: str) -> List[Dict]:
        goal_text = (goal or "").strip()
        tasks: List[Dict] = []
        if not goal_text:
            return tasks

        tid = 1

        def add(title: str, description: str):
            nonlocal tid
            tasks.append({"id": tid, "title": title, "description": description})
            tid += 1

        add("Define requirements", f"Clarify and scope the goal: '{goal_text}'")
        add("Design architecture", "Propose API routes, data model, and components (DB, services, templates)")
        add("Implement core APIs", "Create endpoints for shortening and redirecting URLs")
        add("Add persistence", "Wire the database and repository layer to persist shortened URLs")

        low = goal_text.lower()
        if "analytics" in low or "click" in low or "metrics" in low:
            add("Add analytics", "Instrument redirects to record clicks, timestamps, and unique visitors")

        if "admin" in low or "admin" in goal_text:
            add("Admin interface", "Add protected admin routes and basic UI for overview")

        if "observability" in low or "logging" in low or "metrics" in low:
            add("Observability", "Add logging, metrics endpoint and request tracing middleware")

        add("Write tests", "Add unit and integration tests for key flows")
        add("Dockerize", "Provide Dockerfile and compose for running the service")

        return tasks
