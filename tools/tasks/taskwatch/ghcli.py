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
    def __init__(self, repo: Optional[str] = None, runner: Optional[_Runner] = None, retries: int = 5):
        self._repo = repo  # optional override for -R
        self._runner = runner or _Runner()
        self._retries = retries

    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        backoffs = [0.0, 0.5, 1.0, 2.0, 5.0]
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
                _t.sleep(3.0)  # longer pause for secondary rate limits
            elif 'api rate limit exceeded' in err:
                _t.sleep(15.0)
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
        try:
            out = self._run_ok(["gh", "repo", "view", "--json", "owner", "--jq", ".owner.login"])
            return out.strip()
        except Exception:
            # Fallback: parse from git remote
            owner, _ = self._owner_name_from_git()
            if owner:
                return owner
            raise

    def repo_name(self) -> str:
        try:
            out = self._run_ok(["gh", "repo", "view", "--json", "name", "--jq", ".name"])
            return out.strip()
        except Exception:
            # Fallback: parse from git remote
            _, name = self._owner_name_from_git()
            if name:
                return name
            raise

    def _try_repo_owner(self) -> Optional[str]:
        try:
            return self.repo_owner()
        except Exception:
            return None

    def _try_repo_name(self) -> Optional[str]:
        try:
            return self.repo_name()
        except Exception:
            return None

    def _owner_name_from_git(self) -> tuple[Optional[str], Optional[str]]:
        try:
            cp = self._run(["git", "config", "--get", "remote.origin.url"])
            if cp.returncode != 0:
                return None, None
            url = (cp.stdout or "").strip()
            if not url:
                return None, None
            import re
            # git@github.com:owner/name.git or https://github.com/owner/name.git
            m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)(?:\.git)?$", url)
            if not m:
                return None, None
            return m.group(1), m.group(2)
        except Exception:
            return None, None

    def ensure_project(self, title: str) -> GHProject:
        owner = self.repo_owner()
        # Try GraphQL listing for user, then org
        def _list_projects_graphql(owner_login: str) -> List[dict]:
            q = {
                "query": """
                query($owner:String!, $after:String) {
                  user(login:$owner) {
                    projectsV2(first:100, after:$after) {
                      pageInfo { hasNextPage endCursor }
                      nodes { id number title }
                    }
                  }
                  organization(login:$owner) {
                    projectsV2(first:100, after:$after) {
                      pageInfo { hasNextPage endCursor }
                      nodes { id number title }
                    }
                  }
                }
                """,
                "variables": {"owner": owner_login, "after": None}
            }
            out: List[dict] = []
            after = None
            while True:
                q["variables"]["after"] = after
                cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
                if cp.returncode != 0:
                    return []
                data = json.loads(cp.stdout or "{}")
                u = (((data.get("data") or {}).get("user") or {}).get("projectsV2") or {})
                o = (((data.get("data") or {}).get("organization") or {}).get("projectsV2") or {})
                for src in (u, o):
                    for n in (src.get("nodes") or []):
                        out.append(n)
                pi = (u.get("pageInfo") or o.get("pageInfo") or {})
                if not pi.get("hasNextPage"):
                    break
                after = pi.get("endCursor")
            return out
        nodes = _list_projects_graphql(owner)
        for n in nodes:
            if n.get("title") == title:
                return GHProject(owner=owner, number=int(n["number"]), id=n["id"], title=title)
        # Fallback to CLI JSON, tolerate older gh returning non-JSON
        try:
            out = self._run_ok(["gh", "project", "list", "--owner", owner, "--format", "json"])
            arr = json.loads(out or "[]")
            if isinstance(arr, dict):
                arr = arr.get("projects") or []
            if isinstance(arr, list):
                for prj in arr:
                    if isinstance(prj, dict) and prj.get("title") == title:
                        return GHProject(owner=owner, number=int(prj["number"]), id=prj["id"], title=title)
        except Exception:
            pass
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
        """Ensure SLAPS fields exist on the Project and normalize shapes across gh versions.

        This function is intentionally defensive:
        - First attempts GraphQL listing by project node id (stable across user/org owners).
        - Falls back to `gh project field-list` JSON which has varied over gh releases.
        - Normalizes CLI shapes by mapping `type` -> `dataType` and ensuring `options` list exists.
        - Re-creates `slaps-state` if required options are missing.
        """
        # GraphQL listing via node(id: project.id) so we don't depend on owner type
        def _list_fields_by_id(pid: str) -> List[dict]:
            q = {
                "query": """
                query($id:ID!, $after:String) {
                  node(id:$id) {
                    ... on ProjectV2 {
                      fields(first:100, after:$after) {
                        pageInfo { hasNextPage endCursor }
                        nodes {
                          id
                          name
                          dataType
                          ... on ProjectV2SingleSelectField { options { id name } }
                        }
                      }
                    }
                  }
                }
                """,
                "variables": {"id": pid, "after": None}
            }
            out: List[dict] = []
            after = None
            while True:
                q["variables"]["after"] = after
                cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
                if cp.returncode != 0:
                    return []
                data = json.loads(cp.stdout or "{}")
                node = (data.get("data") or {}).get("node") or {}
                fields = (node.get("fields") or {})
                out.extend(fields.get("nodes") or [])
                pi = fields.get("pageInfo") or {}
                if not pi.get("hasNextPage"):
                    break
                after = pi.get("endCursor")
            return out

        existing_map: Dict[str, dict] = {}
        for f in _list_fields_by_id(project.id) or []:
            if isinstance(f, dict) and isinstance(f.get("name"), str):
                existing_map[f["name"]] = f
        # Fallback to CLI JSON if GraphQL fails
        if not existing_map:
            try:
                out = self._run_ok(["gh", "project", "field-list", str(project.number), "--owner", project.owner, "--format", "json"])
                parsed = json.loads(out or "[]")
                if isinstance(parsed, list):
                    for f in parsed:
                        if not isinstance(f, dict):
                            continue
                        # normalize CLI shape
                        if "dataType" not in f and "type" in f:
                            f["dataType"] = f.get("type")
                        if "options" not in f:
                            f["options"] = []
                        if isinstance(f.get("name"), str):
                            existing_map[f["name"]] = f
                elif isinstance(parsed, dict):
                    for f in (parsed.get("fields") or []):
                        if not isinstance(f, dict):
                            continue
                        if "dataType" not in f and "type" in f:
                            f["dataType"] = f.get("type")
                        if "options" not in f:
                            f["options"] = []
                        if isinstance(f.get("name"), str):
                            existing_map[f["name"]] = f
            except Exception:
                existing_map = {}

        fields: Dict[str, GHField] = {}

        def _mk(name: str, dtype: str, options: Optional[List[str]] = None) -> GHField:
            f = existing_map.get(name)
            if f:
                opts = None
                if dtype == "SINGLE_SELECT":
                    opts = {o["name"]: o["id"] for o in (f.get("options") or [])}
                # Older gh may present `type` instead of `dataType` — normalize
                dt = f.get("dataType") or f.get("type") or dtype
                return GHField(id=f.get("id",""), name=f.get("name",""), data_type=str(dt), options=opts)
            # Create via CLI (gh doesn't expose field-create in GraphQL yet)
            args = [
                "gh", "project", "field-create", str(project.number), "--owner", project.owner,
                "--name", name, "--data-type", dtype,
            ]
            if dtype == "SINGLE_SELECT" and options:
                args += ["--single-select-options", ",".join(options)]
            self._run(args)
            # Re-list to capture ids/options
            existing_map.clear()
            for f2 in _list_fields_by_id(project.id) or []:
                if isinstance(f2, dict) and isinstance(f2.get("name"), str):
                    existing_map[f2["name"]] = f2
            f3 = existing_map.get(name) or {}
            opts = None
            if dtype == "SINGLE_SELECT":
                opts = {o["name"]: o["id"] for o in (f3.get("options") or [])}
            dt3 = f3.get("dataType") or f3.get("type") or dtype
            return GHField(id=f3.get("id",""), name=name, data_type=str(dt3), options=opts)

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
            # Try to populate missing single-select options by recreating field
            del_rc = self._run(["gh", "project", "field-delete", str(project.number), "--owner", project.owner, "--field-id", fields["slaps-state"].id]).returncode
            if del_rc != 0:
                # As a fallback when delete is unsupported, log and continue; _mk will return existing field
                pass
            fields["slaps-state"] = _mk("slaps-state", "SINGLE_SELECT", list(required))
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
        # Prefer GraphQL mutation addProjectV2ItemById for consistent JSON
        q = {
            "query": """
            mutation($projectId:ID!, $contentId:ID!) {
              addProjectV2ItemById(input:{projectId:$projectId, contentId:$contentId}) {
                item { id }
              }
            }
            """,
            "variables": {"projectId": project.id, "contentId": content_id}
        }
        last_err = ""
        cp = self._run(["gh", "api", "graphql", "-f", f"query={json.dumps(q['query'])}", "-f", f"variables={json.dumps(q['variables'])}"])
        if cp.returncode == 0:
            try:
                data = json.loads(cp.stdout or "{}")
                item = (((data.get("data") or {}).get("addProjectV2ItemById") or {}).get("item") or {})
                iid = item.get("id")
                if iid:
                    return iid
            except Exception as e:
                last_err = f"graphql parse error: {e}"
        else:
            last_err = cp.stderr or "graphql add failed"
        # Fallback: CLI add by URL (older gh supports this form)
        try:
            url = self._run_ok(self._gh("issue", "view", str(issue_number), "--json", "url", "--jq", ".url")).strip()
            cp3 = self._run(["gh", "project", "item-add", str(project.number), "--owner", project.owner, "--url", url])
            if cp3.returncode == 0:
                iid3 = self.find_item_by_issue(project, issue_number)
                if iid3:
                    return iid3
            else:
                last_err = cp3.stderr or last_err
        except Exception as e:
            last_err = f"url add failed: {e}"
        raise RuntimeError(f"failed to add issue to project (last_err={last_err})")

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
                try:
                    out = self._run_ok(["gh", "project", "item-list", str(project.number), "--owner", project.owner, "--format", "json", "-L", "200"])
                    parsed = json.loads(out or "[]")
                    lst: List[dict] = []
                    if isinstance(parsed, list):
                        lst = [x for x in parsed if isinstance(x, dict)]
                    elif isinstance(parsed, dict):
                        candidates = parsed.get("items") or parsed.get("nodes") or []
                        lst = [x for x in candidates if isinstance(x, dict)]
                    return lst
                except Exception:
                    return []
            data = json.loads(cp.stdout or "{}")
            root = data.get("data") or {}
            pj = (root.get("user") or {}).get("projectV2") or (root.get("organization") or {}).get("projectV2") or {}
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
                # GraphQL for draft items doesn't expose title in our selected fields; keep structure minimal
                items.append({"id": n.get("id"), "content": {"number": num}, "fields": fields})
            page = conn.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        return [x for x in items if isinstance(x, dict)]

    def find_project_item_by_title(self, project: GHProject, title: str) -> str | None:
        # Try CLI list where draft item titles are included
        try:
            out = self._run_ok(["gh", "project", "item-list", str(project.number), "--owner", project.owner, "--format", "json", "-L", "200"])
            parsed = json.loads(out or "[]")
            items: List[dict] = []
            if isinstance(parsed, list):
                items = [x for x in parsed if isinstance(x, dict)]
            elif isinstance(parsed, dict):
                cand = parsed.get("items") or parsed.get("nodes") or []
                items = [x for x in cand if isinstance(x, dict)]
            for it in items:
                if it.get("title") == title:
                    return it.get("id")
        except Exception:
            pass
        return None

    def list_issues_for_wave(self, wave: int) -> List[int]:
        # Query repository issues with label milestone::M{wave}
        owner = self._try_repo_owner()
        name = self._try_repo_name()
        if not owner or not name:
            return []
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
                # Fallback: try gh issue list (open only), then milestone title
                try:
                    out = self._run_ok(["gh", "issue", "list", "--label", label, "--json", "number"])
                    return [x.get("number") for x in json.loads(out or "[]")]
                except Exception:
                    pass
                try:
                    out2 = self._run_ok(["gh", "issue", "list", "--milestone", f"M{wave}", "--state", "all", "--json", "number"])
                    return [x.get("number") for x in json.loads(out2 or "[]")]
                except Exception:
                    return []
            data = json.loads(cp.stdout or "{}")
            iss = (((data.get("repository") or {}).get("issues") or {}))
            for n in iss.get("nodes", []):
                nums.append(n.get("number"))
            page = iss.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        # If none via label, try milestone title via CLI JSON
        if not nums:
            try:
                out2 = self._run_ok(["gh", "issue", "list", "--milestone", f"M{wave}", "--state", "all", "--json", "number"])
                return [x.get("number") for x in json.loads(out2 or "[]")]
            except Exception:
                return []
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
        owner = self._try_repo_owner()
        name = self._try_repo_name()
        if not owner or not name:
            return []
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
            if not isinstance(it, dict):
                continue
            content = it.get("content") or {}
            if isinstance(content, dict) and content.get("number") == issue_number:
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
        owner = self._try_repo_owner()
        name = self._try_repo_name()
        if not owner or not name:
            return []
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
        # Prefer gh api for consistent JSON; fallback to CLI create with URL parsing
        owner = self._try_repo_owner()
        name = self._try_repo_name()
        if owner and name:
            cp = self._run(["gh", "api", f"repos/{owner}/{name}/issues", "-f", f"title={title}", "-f", f"body={body}"])
            if cp.returncode == 0:
                try:
                    data = json.loads(cp.stdout or "{}")
                    num = int(data.get("number", 0))
                    if num:
                        return num
                except Exception:
                    pass
        # Fallback: gh issue create (older gh), parse issue number from stdout URL
        cp2 = self._run(["gh", "issue", "create", "--title", title, "--body", body])
        if cp2.returncode == 0:
            import re
            m = re.search(r"/issues/(\d+)", cp2.stdout or "")
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    pass
        raise RuntimeError("failed to create issue via gh api or cli")

    def find_issue_by_title(self, title: str) -> int | None:
        owner = self._try_repo_owner()
        name = self._try_repo_name()
        if not owner or not name:
            return None
        # Try gh issue list with --search (older gh friendly)
        try:
            out = self._run_ok(["gh", "issue", "list", "--state", "all", "--search", title, "--json", "number,title", "--limit", "50"])
            arr = json.loads(out or "[]")
            for it in arr or []:
                if isinstance(it, dict) and it.get("title") == title:
                    n = it.get("number")
                    if isinstance(n, int):
                        return n
        except Exception:
            pass
        # Try search API
        try:
            q = f"repo:{owner}/{name} is:issue in:title \"{title}\""
            out2 = self._run_ok(["gh", "api", "/search/issues", "-f", f"q={q}"])
            data = json.loads(out2 or "{}")
            for it in (data.get("items") or []):
                if it.get("title") == title and isinstance(it.get("number"), int):
                    return it.get("number")
        except Exception:
            pass
        return None
