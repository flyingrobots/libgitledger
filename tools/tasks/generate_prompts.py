#!/usr/bin/env python3
"""
Generate LLM-ready task prompts from raw issue JSON files.

Inputs
------
- Raw issues: .slaps/tasks/raw/*.json (GitHub issue JSON or similar schema).
- AGENTS.md at repo root will be embedded under <BRIEFING>.

Outputs
-------
- If task.relationships.blockedBy exists and is non-empty (truthy), write to:
    .slaps/tasks/blocked/{issue}.task.txt
  else write to:
    .slaps/tasks/open/{issue}.task.txt

Prompt format follows the user-provided template (JSONL output contract),
with repository briefing embedded verbatim from AGENTS.md.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, Optional


TEMPLATE = (
    '"You are an expert C programmer. You are a Git expert. You\'re working on a\n'
    'project called "libgitledger", a C library that turns Git into an\n'
    'immutable, append-only ledger. Please reads the following briefing, then\n'
    'execute the subsequent task.\n\n'
    'ALL OUTPUT FROM YOU MUST BE IN THE FORM OF JSONL STRINGS TERMINATED BY A\n'
    'NEW LINE CHARACTER.\n\n'
    'Example 1: success\n\n'
    '```json\n[true,""]\n\n```\n\n'
    'Example 2: error\n\n'
    '```json\n[false, "error message"]\n\n```\n\n'
    'The JSON object is an Array with two elements: the first is a bool to\n'
    'represent whether or not you successfully completed your assignment. The\n'
    'second element in the Array is a string that is either empty or an error\n'
    'message. When you\'re finished, you must either exit 0 to indicate success,\n'
    'or non-zero to indicate a failure.\n\n'
    '<BRIEFING>\n{briefing}\n</BRIEFING>\n\n'
    '<TASK>\n{task}\n</TASK>\n\n'
    'IMPORTANT! You must adhere to the following workflow:\n\n'
    '1. Read the task.\n'
    '2. Write failing test(s) first.\n'
    '3. Solve the problem from the task above.\n'
    '4. Run the test(s):\n'
    '  i. if you pass the test(s), go to 5.\n'
    ' ii. if you fail, go to 3.\n'
    '1. Update/add any documentation to keep the project documents accurate.\n'
    '2. Exit, following the instructions below.\n\n'
    '<EXIT INSTRUCTIONS>\n'
    'if you successfully completed your assignment, then:\n'
    '  print \"[true, \"\"]\\n\" and exit 0\n'
    'else:\n'
    '  print \"[false, \"{reason}\"]\\n\" and exit non-zero\n'
    '</EXIT INSTRUCTIONS>\n'
)


def read_briefing(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "AGENTS.md not found; ensure repository briefing is available."


def get_issue_number(obj: Dict[str, Any]) -> Optional[int]:
    # Accept several shapes: top-level number, or obj["issue"]["number"], etc.
    if isinstance(obj.get("number"), int):
        return obj["number"]
    issue = obj.get("issue")
    if isinstance(issue, dict) and isinstance(issue.get("number"), int):
        return issue["number"]
    return None


def get_blocked_by(obj: Dict[str, Any]) -> Any:
    # Prefer nested task.relationships.blockedBy per spec; fallback to top-level relationships.blockedBy
    task = obj.get("task") if isinstance(obj.get("task"), dict) else obj
    rel = task.get("relationships") if isinstance(task, dict) else None
    if isinstance(rel, dict) and "blockedBy" in rel:
        return rel["blockedBy"]
    # some exports may use kebab or snake case — attempt a couple of fallbacks
    if isinstance(task, dict):
        for key in ("blockedBy", "blocked_by", "blocked-by"):
            if key in task:
                return task[key]
    return None


def is_truthy_blocked(value: Any) -> bool:
    # Valid per spec: not null/undefined/NaN/empty string/zero; arrays must have length>0.
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False
    if isinstance(value, str):
        return len(value.strip()) > 0 and value.strip().lower() not in {"null", "none", "undefined"}
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, dict):
        return len(value) > 0
    if isinstance(value, bool):
        return value
    if isinstance(value, (int,)):
        return value != 0
    return True


def render_task_text(obj: Dict[str, Any]) -> str:
    title = obj.get("title") or (obj.get("issue", {}) or {}).get("title") or "(untitled)"
    body = obj.get("body") or (obj.get("issue", {}) or {}).get("body") or ""
    url = obj.get("url") or (obj.get("issue", {}) or {}).get("url") or ""
    labels = obj.get("labels") or (obj.get("issue", {}) or {}).get("labels") or []
    # Compose a compact task description for the <TASK> section
    lines = []
    lines.append(f"Issue: {title}")
    if url:
        lines.append(f"URL: {url}")
    if labels:
        try:
            # gh export shape: labels is list of objects with name
            names = [l["name"] if isinstance(l, dict) and "name" in l else str(l) for l in labels]
            lines.append("Labels: " + ", ".join(names))
        except Exception:
            lines.append("Labels: " + str(labels))
    if body:
        lines.append("")
        lines.append("Description:")
        lines.append(body)
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", default=str(Path(".slaps") / "tasks" / "raw"), help="Path to raw tasks dir")
    ap.add_argument("--blocked", default=str(Path(".slaps") / "tasks" / "blocked"), help="Path to blocked dir")
    ap.add_argument("--open", dest="open_dir", default=str(Path(".slaps") / "tasks" / "open"), help="Path to open dir")
    ap.add_argument("--agents", default="AGENTS.md", help="Path to AGENTS.md to embed")
    ap.add_argument("--dry-run", action="store_true", help="Parse and print destinations without writing files")
    args = ap.parse_args()

    raw_dir = Path(args.raw)
    blocked_dir = Path(args.blocked)
    open_dir = Path(args.open_dir)
    briefing = read_briefing(Path(args.agents))

    files = sorted(Path(raw_dir).glob("*.json"))
    results = []
    for fp in files:
        try:
            obj = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            results.append({"file": str(fp), "status": "error", "error": f"invalid json: {exc}"})
            continue

        if not isinstance(obj, dict):
            # Skip non-issue JSONs (e.g., relationships-index arrays)
            results.append({"file": str(fp), "status": "skipped", "reason": f"non-object json: {type(obj).__name__}"})
            continue

        num = get_issue_number(obj)
        if num is None:
            results.append({"file": str(fp), "status": "error", "error": "missing issue number"})
            continue

        blocked_val = get_blocked_by(obj)
        dest_dir = blocked_dir if is_truthy_blocked(blocked_val) else open_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        out_path = dest_dir / f"{num}.task.txt"

        task_text = render_task_text(obj)
        prompt = TEMPLATE.format(briefing=briefing, task=task_text, reason="error")

        if args.dry_run:
            results.append({"file": str(fp), "issue": num, "dest": str(out_path), "status": "ok", "blocked": bool(dest_dir is blocked_dir)})
        else:
            out_path.write_text(prompt, encoding="utf-8")
            results.append({"file": str(fp), "issue": num, "dest": str(out_path), "status": "written", "blocked": bool(dest_dir is blocked_dir)})

    print(json.dumps({"count": len(results), "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
