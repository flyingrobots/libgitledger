from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .ports import GHPort, GHProject, GHField


def _run(args: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True)


def _run_ok(args: List[str]) -> str:
    cp = _run(args)
    if cp.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}\n{cp.stderr}")
    return cp.stdout


class GHCLI(GHPort):
    def __init__(self, repo: Optional[str] = None):
        self._repo = repo  # optional override for -R

    def _gh(self, *args: str) -> List[str]:
        base = ["gh", *args]
        if self._repo and args[:1] == ["issue"]:
            base = ["gh", "-R", self._repo, *args]
        return base

    def repo_owner(self) -> str:
        out = _run_ok(["gh", "repo", "view", "--json", "owner", "--jq", ".owner.login"])
        return out.strip()

    def repo_name(self) -> str:
        out = _run_ok(["gh", "repo", "view", "--json", "name", "--jq", ".name"])
        return out.strip()

    def ensure_project(self, title: str) -> GHProject:
        owner = self.repo_owner()
        # Try to find existing
        out = _run_ok(["gh", "project", "list", "--owner", owner, "--format", "json"])
        arr = json.loads(out or "[]")
        for prj in arr:
            if prj.get("title") == title:
                return GHProject(owner=owner, number=int(prj["number"]), id=prj["id"], title=title)
        # Create
        out = _run_ok(["gh", "project", "create", "--owner", owner, "--title", title, "--format", "json"])
        prj = json.loads(out)
        return GHProject(owner=owner, number=int(prj["number"]), id=prj["id"], title=title)

    def ensure_labels(self, labels: List[str]) -> None:
        try:
            out = _run_ok(["gh", "label", "list", "--json", "name"])
            have = {x["name"] for x in json.loads(out or "[]")}
        except Exception:
            have = set()
        for lab in labels:
            if lab in have:
                continue
            # Create label with a deterministic color when possible
            color = "bfd4f2" if lab.endswith("wip") else ("c2f0c2" if lab.endswith("did-it") else "f9d0c4")
            _run(["gh", "label", "create", lab, "--color", color])

    def ensure_fields(self, project: GHProject, single_select_state_values: List[str]) -> Dict[str, GHField]:
        out = _run_ok(["gh", "project", "field-list", str(project.number), "--owner", project.owner, "--format", "json"])
        existing = {f["name"]: f for f in json.loads(out or "[]")}

        fields: Dict[str, GHField] = {}

        def _mk(name: str, dtype: str, options: Optional[List[str]] = None) -> GHField:
            if name in existing:
                f = existing[name]
                opts = None
                if dtype == "SINGLE_SELECT":
                    # options: list of {id,name}
                    opts = {o["name"]: o["id"] for o in (f.get("options") or [])}
                return GHField(id=f["id"], name=f["name"], data_type=f["dataType"], options=opts)
            args = [
                "gh", "project", "field-create", str(project.number), "--owner", project.owner,
                "--name", name, "--data-type", dtype,
            ]
            if dtype == "SINGLE_SELECT" and options:
                args += ["--single-select-options", ",".join(options)]
            out = _run_ok(args + ["--format", "json"])
            f = json.loads(out)
            opts = None
            if dtype == "SINGLE_SELECT":
                opts = {o["name"]: o["id"] for o in (f.get("options") or [])}
            return GHField(id=f["id"], name=f["name"], data_type=f["dataType"], options=opts)

        fields["slaps-state"] = _mk("slaps-state", "SINGLE_SELECT", single_select_state_values)
        fields["slaps-worker"] = _mk("slaps-worker", "NUMBER")
        fields["slaps-attempt-count"] = _mk("slaps-attempt-count", "NUMBER")
        fields["slaps-wave"] = _mk("slaps-wave", "NUMBER")
        return fields

    def issue_node_id(self, issue_number: int) -> str:
        out = _run_ok(self._gh("issue", "view", str(issue_number), "--json", "id", "--jq", ".id"))
        return out.strip()

    def ensure_issue_in_project(self, project: GHProject, issue_number: int) -> str:
        # See if already present
        item_id = self.find_item_by_issue(project, issue_number)
        if item_id:
            return item_id
        content_id = self.issue_node_id(issue_number)
        out = _run_ok(["gh", "project", "item-add", "--project-id", project.id, "--content-id", content_id, "--format", "json"])
        data = json.loads(out)
        return data["id"]

    def list_items(self, project: GHProject) -> List[dict]:
        out = _run_ok(["gh", "project", "item-list", str(project.number), "--owner", project.owner, "--format", "json", "-L", "200"])
        arr = json.loads(out or "[]")
        return arr

    def _edit_item_field(self, project: GHProject, item_id: str, field: GHField, **kv) -> None:
        args = [
            "gh", "project", "item-edit",
            "--id", item_id,
            "--field-id", field.id,
            "--project-id", project.id,
        ]
        for k, v in kv.items():
            args += [f"--{k}", str(v)]
        cp = _run(args)
        if cp.returncode != 0:
            raise RuntimeError(f"item-edit failed: {cp.stderr}")

    def set_item_number_field(self, project: GHProject, item_id: str, field: GHField, value: float) -> None:
        self._edit_item_field(project, item_id, field, number=value)

    def set_item_text_field(self, project: GHProject, item_id: str, field: GHField, value: str) -> None:
        self._edit_item_field(project, item_id, field, text=value)

    def set_item_single_select(self, project: GHProject, item_id: str, field: GHField, option_value: str) -> None:
        if not field.options or option_value not in field.options:
            raise ValueError(f"unknown option '{option_value}' for field {field.name}")
        self._edit_item_field(project, item_id, field, **{"single-select-option-id": field.options[option_value]})

    def get_item_fields(self, project: GHProject, item_id: str) -> Dict[str, str]:
        # There is no direct “view one item” command; list and filter.
        for it in self.list_items(project):
            if it.get("id") == item_id:
                vals: Dict[str, str] = {}
                for f in it.get("fields") or []:
                    nm = (f.get("name") or f.get("field", {}).get("name") or "").strip()
                    val = f.get("value")
                    if isinstance(val, dict) and "name" in val:  # single-select
                        vals[nm] = val.get("name")
                    elif val is None:
                        pass
                    else:
                        vals[nm] = str(val)
                return vals
        return {}

    def find_item_by_issue(self, project: GHProject, issue_number: int) -> Optional[str]:
        # For each item, compare content.number if present
        for it in self.list_items(project):
            content = it.get("content") or {}
            if content.get("number") == issue_number:
                return it.get("id")
        return None

    def add_label(self, issue_number: int, label: str) -> None:
        _run(self._gh("issue", "edit", str(issue_number), "--add-label", label))

    def remove_label(self, issue_number: int, label: str) -> None:
        _run(self._gh("issue", "edit", str(issue_number), "--remove-label", label))

    def add_comment(self, issue_number: int, body_markdown: str) -> None:
        cp = _run(self._gh("issue", "comment", str(issue_number), "--body", body_markdown))
        if cp.returncode != 0:
            # swallow errors but surface in logs
            raise RuntimeError(cp.stderr)

    def list_issue_comments(self, issue_number: int) -> List[dict]:
        # Use issue view with JSON comments
        out = _run_ok(self._gh("issue", "view", str(issue_number), "--json", "comments", "--jq", ".comments"))
        try:
            arr = json.loads(out)
            # map minimal fields
            out2: List[dict] = []
            for c in arr or []:
                out2.append({
                    "createdAt": c.get("createdAt") or c.get("created_at") or "",
                    "body": c.get("body") or "",
                })
            return out2
        except Exception:
            return []

    def fetch_issue_json(self, issue_number: int) -> dict:
        out = _run_ok(self._gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,url"))
        return json.loads(out or "{}")

    def project_item_create_draft(self, project: GHProject, title: str, body: str) -> str:
        out = _run_ok(["gh", "project", "item-create", str(project.number), "--owner", project.owner, "--title", title, "--body", body, "--format", "json"])
        data = json.loads(out or "{}")
        return data.get("id", "")
