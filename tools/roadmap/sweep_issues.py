#!/usr/bin/env python3
"""
Sweep GitHub issues to:
- Normalize milestones and milestone::M# labels from docs/ROADMAP-DAG.mmd subgraphs
- Wire hard dependencies using GraphQL addBlockedBy based on '==>' edges
- Post a per-issue "Dependencies" comment with hard/soft relations and a mini Mermaid graph

Requirements:
- gh CLI authenticated (GH_TOKEN or user session)
- Network access enabled
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple


MMD_PATH = Path("docs/ROADMAP-DAG.mmd")


@dataclass
class Dag:
    label_by_node: Dict[str, str] = field(default_factory=dict)
    issue_by_node: Dict[str, int] = field(default_factory=dict)
    milestone_by_node: Dict[str, str] = field(default_factory=dict)
    hard_edges: List[Tuple[str, str]] = field(default_factory=list)  # (a, b) means a depends on b
    soft_edges: List[Tuple[str, str]] = field(default_factory=list)  # (parent, child)

    def roots(self) -> Set[str]:
        targets = {b for (_, b) in self.hard_edges} | {b for (_, b) in self.soft_edges}
        nodes = set(self.label_by_node.keys())
        return nodes - targets


def run(cmd: List[str], input_text: str | None = None) -> str:
    proc = subprocess.run(cmd, input=input_text.encode() if input_text else None,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{proc.stderr.decode()}")
    return proc.stdout.decode()


def parse_mmd(path: Path) -> Dag:
    src = path.read_text(encoding="utf-8")
    dag = Dag()
    current_ms = None
    # Capture subgraph titles to propagate milestone names
    subgraph_re = re.compile(r"^\s*subgraph\s+\"([^\"]+)\"\s*$")
    node_re = re.compile(r"^\s*(N\d+)\[\"(#(\d+)\s+[^\"]*)\"\]\s*$")
    hard_re = re.compile(r"^\s*(N\d+)\s*==>\s*(N\d+)\s*$")
    soft_re = re.compile(r"^\s*(N\d+)\s*-.->\s*(N\d+)\s*$")

    for line in src.splitlines():
        m = subgraph_re.match(line)
        if m:
            current_ms = m.group(1)
            continue
        if line.strip() == "end":
            current_ms = None
            continue
        m = node_re.match(line)
        if m:
            node = m.group(1)
            label = m.group(2)
            issue_num = int(m.group(3))
            dag.label_by_node[node] = label
            dag.issue_by_node[node] = issue_num
            if current_ms:
                dag.milestone_by_node[node] = current_ms
            continue
        m = hard_re.match(line)
        if m:
            dag.hard_edges.append((m.group(1), m.group(2)))
            continue
        m = soft_re.match(line)
        if m:
            dag.soft_edges.append((m.group(1), m.group(2)))
            continue
    return dag


def repo_owner_name() -> Tuple[str, str]:
    out = run(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()
    owner, name = out.split("/")
    return owner, name


def rest_issue_numeric_id(number: int) -> int:
    owner, repo = repo_owner_name()
    data = json.loads(run(["gh", "api", f"repos/{owner}/{repo}/issues/{number}"]))
    return int(data["id"])  # internal numeric issue id (not the visible number)


def ensure_milestone(number: int, milestone_title: str, milestone_label: str | None = None) -> None:
    # Assign milestone if missing or different
    info = json.loads(run(["gh", "issue", "view", str(number), "--json", "milestone,labels"]))
    current = info.get("milestone", {}).get("title") if info.get("milestone") else None
    if current != milestone_title:
        # Ensure milestone exists; create if missing
        owner, repo = repo_owner_name()
        existing = json.loads(run(["gh", "api", f"repos/{owner}/{repo}/milestones?state=all"]))
        titles = {m["title"] for m in existing}
        if milestone_title not in titles:
            # Create milestone
            run(["gh", "api", f"repos/{owner}/{repo}/milestones", "-f", f"title={milestone_title}", "-f", "state=open"])
        run(["gh", "issue", "edit", str(number), "--milestone", milestone_title])
    # Ensure milestone::M# label present if requested
    if milestone_label:
        labels = [l["name"] for l in info.get("labels", [])]
        if milestone_label not in labels:
            run(["gh", "issue", "edit", str(number), "--add-label", milestone_label])


def add_blocked_by(blocked_number: int, blocking_number: int) -> None:
    """Wire a hard dependency using the REST Issue Dependencies API.

    blocked_number: the visible issue number that is blocked
    blocking_number: the visible issue number that blocks it
    """
    owner, repo = repo_owner_name()
    blocking_id = rest_issue_numeric_id(blocking_number)
    try:
        run([
            "gh", "api", "-X", "POST",
            f"repos/{owner}/{repo}/issues/{blocked_number}/dependencies/blocked_by",
            "-f", f"issue_id={blocking_id}",
            "-H", "X-GitHub-Api-Version: 2022-11-28",
        ])
    except RuntimeError as e:
        msg = str(e)
        # 422 if dependency already exists or invalid
        if "422" in msg or "Validation failed" in msg or "already exists" in msg:
            return
        # 404/403: ignore silently to keep sweep idempotent for private/missing issues
        if "404" in msg or "403" in msg:
            return
        # Do not block the sweep
        print(f"warn: REST add blocked-by #{blocked_number} <- #{blocking_number}: {msg}")


def post_dependencies_comment(number: int, hard_prereqs: List[int], parents: List[int], children: List[int]) -> None:
    lines = []
    lines.append("### Dependencies (auto-generated from ROADMAP-DAG.mmd)")
    lines.append("")
    if hard_prereqs:
        lines.append("- Hard (blocked by): " + ", ".join(f"#{n}" for n in hard_prereqs))
    else:
        lines.append("- Hard (blocked by): none")
    if parents:
        lines.append("- Soft (parent/epic): " + ", ".join(f"#{n}" for n in parents))
    if children:
        lines.append("- Soft (children): " + ", ".join(f"#{n}" for n in children))
    lines.append("")
    # Mini mermaid (neighbors only)
    lines.append("```mermaid")
    lines.append("flowchart LR")
    for b in hard_prereqs:
        lines.append(f"  I{number}==>I{b}")
    for p in parents:
        lines.append(f"  I{p}-.->I{number}")
    for c in children:
        lines.append(f"  I{number}-.->I{c}")
    lines.append("```")
    body = "\n".join(lines)
    run(["gh", "issue", "comment", str(number), "--body", body])


def main() -> int:
    if not MMD_PATH.exists():
        print(f"missing {MMD_PATH}", file=sys.stderr)
        return 2
    dag = parse_mmd(MMD_PATH)

    # Build quick reverse indexes
    hard_by_src: Dict[str, List[str]] = {}
    soft_parent_to_children: Dict[str, List[str]] = {}
    soft_child_to_parents: Dict[str, List[str]] = {}
    for a, b in dag.hard_edges:
        hard_by_src.setdefault(a, []).append(b)
    for p, c in dag.soft_edges:
        soft_parent_to_children.setdefault(p, []).append(c)
        soft_child_to_parents.setdefault(c, []).append(p)

    # Normalize milestones and labels; wire hard deps; comment dependencies
    # Map milestone label short form (e.g., M3) from title
    ms_code_re = re.compile(r"^(M\d+)\s+—\s+")
    for node, issue in dag.issue_by_node.items():
        milestone_title = dag.milestone_by_node.get(node)
        ms_label = None
        if milestone_title:
            m = ms_code_re.match(milestone_title)
            if m:
                ms_label = f"milestone::{m.group(1)}"
            ensure_milestone(issue, milestone_title, ms_label)

        hard_targets = [dag.issue_by_node[b] for b in hard_by_src.get(node, [])]
        for dep in hard_targets:
            try:
                add_blocked_by(issue, dep)
            except RuntimeError as e:
                # Keep going, but print a short note
                print(f"warn: addBlockedBy #{issue} <- #{dep}: {e}")

        parents = [dag.issue_by_node[p] for p in soft_child_to_parents.get(node, [])]
        children = [dag.issue_by_node[c] for c in soft_parent_to_children.get(node, [])]
        try:
            post_dependencies_comment(issue, hard_targets, parents, children)
        except RuntimeError as e:
            print(f"warn: comment on #{issue} failed: {e}")

    print("sweep done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
