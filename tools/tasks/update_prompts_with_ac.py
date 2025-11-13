#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path


def extract_ac_markdown(body: str) -> str | None:
    lines = body.splitlines()
    ac_start = None
    for i, line in enumerate(lines):
        if re.match(r"\s*##\s*Acceptance Criteria\b", line, re.IGNORECASE):
            ac_start = i
            break
    if ac_start is None:
        return None
    # Capture until next heading (## ) or end
    ac_lines = []
    for j in range(ac_start, len(lines)):
        if j > ac_start and re.match(r"\s*##\s+", lines[j]):
            break
        ac_lines.append(lines[j])
    return "\n".join(ac_lines).strip()


def ensure_ac_in_prompt(prompt_path: Path, ac_md: str) -> bool:
    try:
        text = prompt_path.read_text(encoding='utf-8')
    except Exception:
        return False
    if re.search(r"^##\s*Acceptance Criteria\b", text, re.MULTILINE):
        return False  # already has AC
    updated = text.rstrip() + "\n\n" + ac_md + "\n"
    prompt_path.write_text(updated, encoding='utf-8')
    return True


def main() -> int:
    raw = Path('.slaps/tasks/raw')
    if not raw.exists():
        print('No raw directory found')
        return 2
    # Collect AC per issue
    ac_map: dict[int, str] = {}
    for jf in sorted(raw.glob('issue-*.json')):
        try:
            data = json.loads(jf.read_text(encoding='utf-8'))
        except Exception:
            continue
        num = data.get('number')
        body = data.get('body') or ''
        if not isinstance(num, int) or not isinstance(body, str):
            continue
        ac = extract_ac_markdown(body)
        if ac:
            ac_map[num] = ac
    # Update prompts in blocked queues (global and wave dirs)
    bases = [Path('.slaps/tasks')] + [Path('.slaps/tasks')/str(n) for n in range(1, 100)]
    updated = 0
    for base in bases:
        blocked = base/'blocked'
        if not blocked.exists():
            continue
        for p in sorted(blocked.glob('*.txt')):
            m = re.search(r"(\d+)", p.name)
            if not m:
                continue
            issue = int(m.group(1))
            ac = ac_map.get(issue)
            if ac and ensure_ac_in_prompt(p, ac):
                updated += 1
    print(f'Updated prompts with AC: {updated}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

