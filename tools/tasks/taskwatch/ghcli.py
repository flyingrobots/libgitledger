from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .ports import GHPort, GHProject, GHField


class _Runner:
    def run(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(args, capture_output=True, text=True)


class GHCLI(GHPort):
    def __init__(self, repo: Optional[str] = None, runner: Optional[_Runner] = None, retries: int = 2):
        self._repo = repo  # optional override for -R
        self._runner = runner or _Runner()
        self._retries = retries

    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        backoffs = [0.0, 0.2, 0.5]
        last = None
        for i in range(self._retries + 1):
            cp = self._runner.run(args)
            if cp.returncode == 0:
                return cp
            last = cp
            # simple jitterless backoff
            import time as _t
            err = (cp.stderr or '').lower()
            if 'secondary rate limit' in err:
                _t.sleep(0.8)  # longer pause for rate limits
            else:
                _t.sleep(backoffs[min(i, len(backoffs) - 1)])
        return last or subprocess.CompletedProcess(args, 1, '', 'retry failed')

    def _run_ok(self, args: List[str]) -> str:
        cp = self._run(args)
        if cp.returncode != 0:
            raise RuntimeError(f"command failed: {' '.join(args)}\n{cp.stderr}")
        return cp.stdout

    def _gh(self, *args: str) -> List[str]:
        base = ["gh", *args]
        if self._repo and args[:1] == ["issue"]:
            base = ["gh", "-R", self._repo, *args]
        return base

    def repo_owner(self) -> str:
        out = self._run_ok(["gh", "repo", "view", "--json", "owner", "--jq", ".owner.login"])
        return out.strip()

    def repo_name(self) -> str:
        out = self._run_ok(["gh", "repo", "view", "--json", "name", "--jq", ".name"])
        return out.strip()

    def ensure_project(self, title: str) -> GHProject:
        owner = self.repo_owner()
        # Try to find existing
        out = self._run_ok(["gh", "project", "list", "--owner", owner, "--format", "json"])
        arr = json.loads(out or "[]")
        for prj in arr:
            if prj.get("title") == title:
                return GHProject(owner=owner, number=int(prj["number"]), id=prj["id"], title=title)
        # Create
        out = self._run_ok(["gh", "project", "create", "--owner", owner, "--title", title, "--format", "json"])
        prj = json.loads(out)
        return GHProject(owner=owner, number=int(prj["number"]), id=prj["id"], title=title)

    def ensure_labels(self, labels: List[str]) -> None:
        try:
            out = self._run_ok(["gh", "label", "list", "--json", "name"])
            have = {x["name"] for x in json.loads(out or "[]")}
        except Exception:
            have = set()
        for lab in labels:
            if lab in have:
                continue
            # Create label with a deterministic color when possible
            color = "bfd4f2" if lab.endswith("wip") else ("c2f0c2" if lab.endswith("did-it") else "f9d0c4")
            self._run(["gh", "label", "create", lab, "--color", color])

    def ensure_fields(self, project: GHProject, single_select_state_values: List[str]) -> Dict[str, GHField]:
        out = self._run_ok(["gh", "project", "field-list", str(project.number), "--owner", project.owner, "--format", "json"])
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
            out = self._run_ok(args + ["--format", "json"])
            f = json.loads(out)
            opts = None
            if dtype == "SINGLE_SELECT":
                opts = {o["name"]: o["id"] for o in (f.get("options") or [])}
            return GHField(id=f["id"], name=f["name"], data_type=f["dataType"], options=opts)

        fields["slaps-state"] = _mk("slaps-state", "SINGLE_SELECT", single_select_state_values)
        fields["slaps-worker"] = _mk("slaps-worker", "NUMBER")
        fields["slaps-attempt-count"] = _mk("slaps-attempt-count", "NUMBER")
        fields["slaps-wave"] = _mk("slaps-wave", "NUMBER")
        # Guard required slaps-state options
        required = {"open", "closed", "claimed", "failure", "dead", "blocked"}
        st = fields["slaps-state"]
        have = set((st.options or {}).keys())
        missing = required - have
        if missing:
            raise RuntimeError(f"slaps-state field missing options: {sorted(missing)}")
        return fields

    def issue_node_id(self, issue_number: int) -> str:
        out = self._run_ok(self._gh("issue", "view", str(issue_number), "--json", "id", "--jq", ".id"))
        return out.strip()

    def ensure_issue_in_project(self, project: GHProject, issue_number: int) -> str:
        # See if already present
        item_id = self.find_item_by_issue(project, issue_number)
        if item_id:
            return item_id
        content_id = self.issue_node_id(issue_number)
        out = self._run_ok(["gh", "project", "item-add", "--project-id", project.id, "--content-id", content_id, "--format", "json"])
        data = json.loads(out)
        return data["id"]

    def list_items(self, project: GHProject) -> List[dict]:
        # Use GraphQL to page through items and normalize to gh project item-list JSON-ish shape
        owner = project.owner
        number = project.number
        items: List[dict] = []
        cursor = None
        while True:
            q = {
                "query": """
                query($owner:String!, $number:Int!, $after:String) {
                  user(login:$owner) { # owner may also be org; attempt user then org
                    projectV2(number:$number) {
                      id
                      items(first:100, after:$after) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                          id
                          content { ... on Issue { number } }
                          fieldValues(first:50) {
                            nodes {
                              ... on ProjectV2ItemFieldSingleSelectValue { field { name dataType }
                                name
                              }
                              ... on ProjectV2ItemFieldNumberValue { field { name dataType }
                                number
                              }
                              ... on ProjectV2ItemFieldTextValue { field { name dataType }
                                text
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                  organization(login:$owner) {
                    projectV2(number:$number) {
                      id
                      items(first:100, after:$after) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                          id
                          content { ... on Issue { number } }
                          fieldValues(first:50) {
                            nodes {
                              ... on ProjectV2ItemFieldSingleSelectValue { field { name dataType }
                                name
                              }
                              ... on ProjectV2ItemFieldNumberValue { field { name dataType }
                                number
                              }
                              ... on ProjectV2ItemFieldTextValue { field { name dataType }
                                text
                              }
                            }
                          }
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"owner": owner, "number": number, "after": cursor}
            }
            cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
            if cp.returncode != 0:
                # Fallback to CLI for small projects
                out = self._run_ok(["gh", "project", "item-list", str(project.number), "--owner", project.owner, "--format", "json", "-L", "200"])
                return json.loads(out or "[]")
            data = json.loads(cp.stdout or "{}")
            pj = (data.get("user") or {}).get("projectV2") or (data.get("organization") or {}).get("projectV2") or {}
            conn = pj.get("items") or {}
            for n in conn.get("nodes", []):
                content = n.get("content") or {}
                num = content.get("number")
                fields = []
                for fv in (n.get("fieldValues") or {}).get("nodes", []):
                    fld = (fv.get("field") or {})
                    nm = fld.get("name")
                    dt = fld.get("dataType")
                    if dt == "SINGLE_SELECT":
                        fields.append({"name": nm, "value": {"name": fv.get("name")}})
                    elif dt == "NUMBER":
                        fields.append({"name": nm, "value": fv.get("number")})
                    elif dt == "TEXT":
                        fields.append({"name": nm, "value": fv.get("text")})
                items.append({"id": n.get("id"), "content": {"number": num}, "fields": fields})
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        return items

    def list_issues_for_wave(self, wave: int) -> List[int]:
        # Query repository issues with label milestone::M{wave}
        owner = self.repo_owner()
        name = self.repo_name()
        nums: List[int] = []
        cursor = None
        label = f"milestone::M{wave}"
        while True:
            q = {
                "query": """
                query($owner:String!, $name:String!, $label:String!, $after:String) {
                  repository(owner:$owner, name:$name) {
                    issues(first:100, after:$after, labels: [$label], states:[OPEN,CLOSED]) {
                      pageInfo { hasNextPage endCursor }
                      nodes { number labels(first:50){nodes{name}} }
                    }
                  }
                }
                """,
                "variables": {"owner": owner, "name": name, "label": label, "after": cursor}
            }
            cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
            if cp.returncode != 0:
                # Fallback: try gh issue list (open only)
                out = self._run_ok(["gh", "issue", "list", "--label", label, "--json", "number"])
                return [x.get("number") for x in json.loads(out or "[]")]
            data = json.loads(cp.stdout or "{}")
            iss = (((data.get("repository") or {}).get("issues") or {}))
            for n in iss.get("nodes", []):
                nums.append(n.get("number"))
            page = iss.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        return nums

    def get_issue_wave_by_label(self, issue_number: int) -> int | None:
        data = self.fetch_issue_json(issue_number)
        for lab in data.get("labels") or []:
            name = lab.get("name")
            if isinstance(name, str) and name.startswith("milestone::M"):
                try:
                    return int(name.split("M", 1)[1])
                except Exception:
                    pass
        return None

    def get_blockers(self, issue_number: int) -> List[int]:
        # Try GraphQL dependencies: blockedBy issues
        owner = self.repo_owner()
        name = self.repo_name()
        q = {
            "query": """
            query($owner:String!, $name:String!, $number:Int!, $after:String) {
              repository(owner:$owner, name:$name) {
                issue(number:$number) {
                  id
                  blockedBy(first:100, after:$after) {
                    pageInfo { hasNextPage endCursor }
                    nodes { number }
                  }
                }
              }
            }
            """,
            "variables": {"owner": owner, "name": name, "number": issue_number, "after": None}
        }
        nums: List[int] = []
        after = None
        while True:
            q["variables"]["after"] = after
            cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
            if cp.returncode != 0:
                return []  # fallback: unknown
            data = json.loads(cp.stdout or "{}")
            repo = (data.get("data") or {}).get("repository") or {}
            blocked = ((repo.get("issue") or {}).get("blockedBy") or {})
            for n in blocked.get("nodes", []):
                try:
                    nums.append(int(n.get("number")))
                except Exception:
                    pass
            pi = blocked.get("pageInfo") or {}
            if not pi.get("hasNextPage"):
                break
            after = pi.get("endCursor")
        return nums

    def _edit_item_field(self, project: GHProject, item_id: str, field: GHField, **kv) -> None:
        args = [
            "gh", "project", "item-edit",
            "--id", item_id,
            "--field-id", field.id,
            "--project-id", project.id,
        ]
        for k, v in kv.items():
            args += [f"--{k}", str(v)]
        cp = self._run(args)
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
        self._run(self._gh("issue", "edit", str(issue_number), "--add-label", label))

    def remove_label(self, issue_number: int, label: str) -> None:
        self._run(self._gh("issue", "edit", str(issue_number), "--remove-label", label))

    def add_comment(self, issue_number: int, body_markdown: str) -> None:
        cp = self._run(self._gh("issue", "comment", str(issue_number), "--body", body_markdown))
        if cp.returncode != 0:
            # swallow errors but surface in logs
            raise RuntimeError(cp.stderr)

    def list_issue_comments(self, issue_number: int) -> List[dict]:
        # GraphQL pagination of comments to ensure we see the latest
        owner = self.repo_owner()
        name = self.repo_name()
        cursor = None
        out_arr: List[dict] = []
        while True:
            q = {
                "query": """
                query($owner:String!, $name:String!, $number:Int!, $after:String) {
                  repository(owner:$owner, name:$name) {
                    issue(number:$number) {
                      comments(first:100, after:$after) {
                        pageInfo { hasNextPage endCursor }
                        nodes { createdAt body }
                      }
                    }
                  }
                }
                """,
                "variables": {"owner": owner, "name": name, "number": issue_number, "after": cursor}
            }
            cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
            if cp.returncode != 0:
                # Fallback to CLI JSON
                out = self._run_ok(self._gh("issue", "view", str(issue_number), "--json", "comments", "--jq", ".comments"))
                try:
                    arr = json.loads(out)
                    return [{"createdAt": (c.get("createdAt") or c.get("created_at") or ""), "body": (c.get("body") or "")} for c in arr or []]
                except Exception:
                    return []
            data = json.loads(cp.stdout or "{}")
            comm = (((data.get("repository") or {}).get("issue") or {}).get("comments") or {})
            for n in comm.get("nodes", []):
                out_arr.append({"createdAt": n.get("createdAt") or "", "body": n.get("body") or ""})
            page = comm.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        return out_arr

    def fetch_issue_json(self, issue_number: int) -> dict:
        out = self._run_ok(self._gh("issue", "view", str(issue_number), "--json", "number,title,body,labels,url,state"))
        return json.loads(out or "{}")

    def project_item_create_draft(self, project: GHProject, title: str, body: str) -> str:
        out = self._run_ok(["gh", "project", "item-create", str(project.number), "--owner", project.owner, "--title", title, "--body", body, "--format", "json"])
        data = json.loads(out or "{}")
        return data.get("id", "")

    def create_issue(self, title: str, body: str) -> int:
        out = self._run_ok(["gh", "issue", "create", "--title", title, "--body", body, "--json", "number"])
        data = json.loads(out or "{}")
        return int(data.get("number", 0))
