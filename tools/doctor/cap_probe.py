#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def gh_version() -> str:
    cp = run(["gh", "--version"])
    if cp.returncode == 0:
        return (cp.stdout or "").splitlines()[0].strip()
    return "unknown"


def rate_limit() -> Dict[str, Any]:
    cp = run(["gh", "api", "/rate_limit"])
    if cp.returncode != 0:
        return {"error": cp.stderr.strip() or "rate_limit query failed"}
    try:
        data = json.loads(cp.stdout or "{}")
        return {
            "core": data.get("resources", {}).get("core", {}),
            "graphql": data.get("resources", {}).get("graphql", {}),
        }
    except Exception as e:
        return {"error": f"parse: {e}"}


@dataclass
class CapabilityDoc:
    gh_version: str
    owner: str
    repo: str
    project: Dict[str, Any]
    fields: Dict[str, Any]
    rate_limit: Dict[str, Any]


def main() -> int:
    # Ensure we can import the GH adapter
    from tools.tasks.taskwatch.ghcli import GHCLI
    from tools.tasks.taskwatch.logjson import JsonlLogger

    root = Path.cwd()
    events = JsonlLogger(path=Path('.slaps/logs/events.jsonl'))

    gh = GHCLI()
    try:
        owner = gh.repo_owner()
    except Exception:
        # Fallback via git remote parsing
        try:
            cp = run(["git", "config", "--get", "remote.origin.url"])
            import re
            m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", cp.stdout or "")
            owner = m.group(1) if m else "unknown"
        except Exception:
            owner = "unknown"
    try:
        repo = gh.repo_name()
    except Exception:
        repo = "unknown"

    # Ensure project exists
    try:
        project_title = f"SLAPS-{repo}"
        project = gh.ensure_project(project_title)
    except Exception as e:
        events.emit("doctor_fail", step="ensure_project", error=str(e))
        print(f"doctor: ensure_project failed: {e}", file=sys.stderr)
        return 1

    # Ensure fields and capture shapes
    try:
        required = ["open", "closed", "claimed", "failure", "dead", "blocked"]
        fields = gh.ensure_fields(project, required)
        fields_doc = {k: {"id": v.id, "name": v.name, "data_type": v.data_type, "options": v.options} for k, v in fields.items()}
        # quick validation of slaps-state options
        st = fields["slaps-state"]
        have = set((st.options or {}).keys())
        missing = set(required) - have
        if missing:
            raise RuntimeError(f"slaps-state missing options: {sorted(missing)}")
    except Exception as e:
        events.emit("doctor_fail", step="ensure_fields", error=str(e))
        print(f"doctor: ensure_fields failed: {e}", file=sys.stderr)
        return 1

    # Draft item round‑trip (best effort; tolerate older gh)
    draft_id = None
    try:
        draft_id = gh.project_item_create_draft(project, title="[SLAPS][DOCTOR] Probe", body="temporary")
        # Set a couple fields and read back
        gh.set_item_number_field(project, draft_id, fields["slaps-attempt-count"], 1)
        gh.set_item_single_select(project, draft_id, fields["slaps-state"], "open")
        got = gh.get_item_fields(project, draft_id)
        if str(got.get("slaps-attempt-count")) != "1" or str(got.get("slaps-state")) != "open":
            raise RuntimeError(f"round-trip mismatch: {got}")
    except Exception as e:
        # Don’t fail hard; record degraded mutation capability
        events.emit("doctor_warn", step="draft_roundtrip", error=str(e))
    finally:
        # Try to delete the draft to avoid clutter (ignore failure)
        if draft_id:
            q = {
                "query": "mutation($id:ID!){ deleteProjectV2Item(input:{itemId:$id}){ deletedItemId }}",
                "variables": {"id": draft_id},
            }
            _ = run(["gh", "api", "graphql", "-f", f"query={q['query']}", "-f", f"variables={json.dumps(q['variables'])}"])

    caps = CapabilityDoc(
        gh_version=gh_version(),
        owner=owner,
        repo=repo,
        project={"owner": project.owner, "id": project.id, "number": project.number, "title": project.title},
        fields=fields_doc,
        rate_limit=rate_limit(),
    )
    out_path = Path('.slaps/logs/capabilities.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(asdict(caps), indent=2), encoding="utf-8")
    events.emit("doctor_pass", project=project.title, project_number=project.number, owner=owner, repo=repo)
    print(f"doctor: PASS — capabilities written to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
