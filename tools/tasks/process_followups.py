#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List


def parse_wave_map(roadmap: Path) -> dict[int, int]:
    mapping: dict[int, int] = {}
    if not roadmap.exists():
        return mapping
    current: int | None = None
    node_re = re.compile(r"\bN(\d+)\[")
    with roadmap.open('r', encoding='utf-8') as f:
        for line in f:
            m = re.search(r"subgraph\s+Phase(\d+)", line)
            if m:
                current = int(m.group(1))
                continue
            if line.strip() == 'end':
                current = None
                continue
            if current is not None:
                nm = node_re.search(line)
                if nm:
                    try:
                        mapping[int(nm.group(1))] = current
                    except Exception:
                        pass
    return mapping


def collect_followups(workers_dir: Path) -> Dict[int, List[str]]:
    results: Dict[int, List[str]] = {}
    pattern = re.compile(r"I just (finished|failed) task (\d+)\. Follow-ups: (.*)")
    for f in sorted(workers_dir.glob("*/follow-up-log.txt")):
        try:
            text = f.read_text(encoding='utf-8')
        except Exception:
            continue
        for line in text.splitlines():
            m = pattern.search(line)
            if not m:
                continue
            issue = int(m.group(2))
            msg = m.group(3).strip()
            results.setdefault(issue, []).append(msg)
    return results


def build_prompt(wave: int, issues: Dict[int, List[str]]) -> str:
    header = (
        "POLICY (READ CAREFULLY):\n"
        "- DO NOT PERFORM GIT OPERATIONS. Do not run git/gh, do not commit, branch, rebase, or push.\n"
        "- DO NOT RUN TESTS. Write failing tests first if needed for follow-ups, then implement fixes, but do not execute the test suite.\n"
        "- You are performing a follow-up sweep after wave {wave}.\n\n"
    ).format(wave=wave)
    body = [
        "You are the Follow-Up Sweeper. Review the notes below and address them with minimal, surgical changes.",
        "For each item: (1) add or update tests to cover the follow-up, (2) implement the change, (3) keep changes small and focused.",
        "After addressing an item, append a line to the relevant worker follow-up log in the format: 'Resolved task {issue}: <brief note>'.",
        "Do not run tests or git commands. The Quality Guardian will do that next.",
        "\nFollow-ups by issue:\n",
    ]
    for issue, notes in sorted(issues.items()):
        body.append(f"- Task {issue}:")
        for n in notes:
            body.append(f"  - {n}")
    return header + "\n" + "\n".join(body) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--wave', type=int, required=True)
    args = ap.parse_args()

    wave = args.wave
    base = Path('.slaps/tasks')
    workers_dir = base.parent / 'workers'
    roadmap = Path('docs/ROADMAP-DAG.md')
    wave_map = parse_wave_map(roadmap)
    if wave <= 0 or not wave_map:
        print('Invalid wave or roadmap not found')
        return 2
    fu = collect_followups(workers_dir)
    # Filter to issues that belong to this wave
    fu_wave = {iss: msgs for iss, msgs in fu.items() if wave_map.get(iss) == wave and msgs}
    if not fu_wave:
        print('No follow-ups for this wave')
        return 0
    # Write a single follow-up prompt to the wave's open queue
    wave_open = base / str(wave) / 'open'
    wave_open.mkdir(parents=True, exist_ok=True)
    out = wave_open / '0000-followups.txt'
    prompt = build_prompt(wave, fu_wave)
    out.write_text(prompt, encoding='utf-8')
    print(f'Enqueued follow-ups prompt at {out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

