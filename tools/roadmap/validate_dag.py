import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

MMD = Path('docs/ROADMAP-DAG.mmd')

def run(cmd: Sequence[str]) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{p.stderr}")
    return p.stdout

def parse_mmd(text: str) -> tuple[set, list[tuple[str, str]], list[tuple[str, str]]]:
    nodes = set()
    edges_hard: list[tuple[str, str]] = []
    edges_soft: list[tuple[str, str]] = []
    for ln in text.splitlines():
        m = re.match(r"\s*(N\d+)\[\"#(\d+) ", ln)
        if m:
            nodes.add((m.group(1), int(m.group(2))))
        m = re.match(r"\s*(N\d+)\s*==>\s*(N\d+)", ln)
        if m:
            edges_hard.append((m.group(1), m.group(2)))
        m = re.match(r"\s*(N\d+)\s*-->\s*(N\d+)", ln)
        if m:
            edges_hard.append((m.group(1), m.group(2)))
        m = re.match(r"\s*(N\d+)\s*-.->\s*(N\d+)", ln)
        if m:
            edges_soft.append((m.group(1), m.group(2)))
    return nodes, edges_hard, edges_soft

def gh_json(args: Sequence[str]) -> dict:
    out = run(["gh", *args])
    return json.loads(out)

def main():
    if not MMD.exists():
        print("validate_dag: missing docs/ROADMAP-DAG.mmd", file=sys.stderr)
        return 1
    text = MMD.read_text(encoding='utf-8')
    nodes, edges_hard, _ = parse_mmd(text)
    # Map node id -> issue number
    node_to_issue = dict(nodes)

    # Basic syntax lint via mermaid-cli if available (optional)
    try:
        run(["docker", "run", "--rm", "-v", f"{MMD.parent.resolve()}:/data", "minlag/mermaid-cli", "-i", "/data/ROADMAP-DAG.mmd", "-o", "/data/.lint.svg"])
    except (RuntimeError, FileNotFoundError) as e:
        print(f"validate_dag: warning: mermaid lint skipped ({type(e).__name__}): {e}")

    # Sanity: all issue numbers exist
    missing: list[int] = []
    for num in node_to_issue.values():
        try:
            gh_json(["issue", "view", str(num), "--json", "number" ])
        except RuntimeError as e:
            msg = str(e).lower()
            if ("not found" in msg) or ("could not resolve" in msg) or (" 404" in msg):
                missing.append(num)
            else:
                print(f"validate_dag: GitHub API error while checking issue {num}: {e}", file=sys.stderr)
                return 2
    if missing:
        print(f"validate_dag: missing issues in DAG: {sorted(set(missing))}", file=sys.stderr)
        return 2

    # Validate edges reference existing nodes
    invalid_edges: list[tuple[str, str]] = []
    for src, dst in edges_hard:
        if src not in node_to_issue or dst not in node_to_issue:
            invalid_edges.append((src, dst))
    if invalid_edges:
        print(f"validate_dag: edges reference non-existent nodes: {invalid_edges}", file=sys.stderr)
        return 3

    # Optional: detect cycles in hard-edge graph (DAG requirement)
    adj: dict[str, list[str]] = {}
    nodes_set = {n for (n, _) in nodes}
    for n in nodes_set:
        adj.setdefault(n, [])
    for s, d in edges_hard:
        adj.setdefault(s, []).append(d)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = dict.fromkeys(nodes_set, WHITE)
    stack: list[str] = []
    cycle_path: list[str] = []

    def dfs(u: str) -> bool:
        nonlocal cycle_path
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, []):
            if color.get(v, WHITE) == WHITE:
                if dfs(v):
                    return True
            elif color.get(v) == GRAY:
                # Found a back-edge; reconstruct simple cycle snippet
                if v in stack:
                    i = stack.index(v)
                    cycle_path = [*stack[i:], v]
                else:
                    cycle_path = [v, u, v]
                return True
        stack.pop()
        color[u] = BLACK
        return False

    for n in nodes_set:
        if color[n] == WHITE and dfs(n):
            print(f"validate_dag: cycle detected in hard edges: {cycle_path}", file=sys.stderr)
            return 4

    # Success
    print("validate_dag: OK")
    return 0

if __name__ == '__main__':
    sys.exit(main())
