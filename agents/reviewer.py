import re
from pathlib import Path
from typing import List, Dict


class ReviewerAgent:
    """Simple reviewer that checks files for basic acceptance and security issues.

    Checks implemented:
    - Detect TODO/FIXME markers
    - Detect usage of dangerous builtins: exec, eval
    - Detect subprocess usage
    - Heuristic secret patterns (AWS keys, generic secrets like "password=", "api_key")
    - Optionally run a provided 'tests' check by ensuring pytest passed (not implemented here)
    """

    SECRET_PATTERNS = [
        re.compile(r"AKIA[0-9A-Z]{16}"),
        re.compile(r"api[_-]?key\W*[:=]\W*['\"]?[A-Za-z0-9-_]{16,}['\"]?", re.I),
        re.compile(r"password\W*[:=]\W*['\"]?.{4,}['\"]?", re.I),
    ]

    FORBIDDEN_PATTERNS = [
        re.compile(r"\bexec\b"),
        re.compile(r"\beval\b"),
        re.compile(r"\bsubprocess\b"),
    ]

    def review_paths(self, paths: List[str]) -> List[Dict]:
        results: List[Dict] = []
        for p in paths:
            item = {"path": p, "issues": []}
            try:
                path = Path(p)
                if not path.exists():
                    item["issues"].append({"type": "missing", "message": "File not found"})
                    results.append(item)
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")

                # TODO/FIXME
                for m in re.finditer(r"\b(TODO|FIXME)\b", text, re.I):
                    item["issues"].append({"type": "todo", "message": f"Found {m.group(0)}"})

                # Forbidden patterns
                for pat in self.FORBIDDEN_PATTERNS:
                    if pat.search(text):
                        item["issues"].append({"type": "forbidden", "message": f"Pattern {pat.pattern} matched"})

                # Secrets
                for pat in self.SECRET_PATTERNS:
                    for m in pat.finditer(text):
                        item["issues"].append({"type": "secret", "message": f"Potential secret: {m.group(0)}"})

            except Exception as e:
                item["issues"].append({"type": "error", "message": str(e)})

            results.append(item)

        return results
