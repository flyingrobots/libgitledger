#!/usr/bin/env python3
import json
import os
import re
import subprocess
from typing import List

SECTIONS = [
    ("## User Stories", "\n|   |    |\n|---|----|\n| **As a...** |  |\n| **I want...** |  |\n| **So that...** |  |\n"),
    ("## Requirements", "\n### Hard Dependencies\n-  \n\n### Soft Dependencies\n-  \n\n### Run-time Dependencies\n-  \n"),
    ("## Acceptance Criteria", "\n- [ ]  \n- [ ]  \n"),
    ("## Test Plan", "\n- Golden path:  \n- Edge cases:  \n- Failure cases:  \n"),
    ("## In-Scope", "\n- [ ]  \n- [ ]  \n"),
    ("## Out-of-Scope", "\n-  \n"),
    ("## Definition of Done", "\n- [ ] Tests green\n- [ ] Docs updated\n- [ ] Activity log updated\n"),
    ("## Remarks/Notes", "\n-  \n"),
]

def run(cmd: List[str], input_text: str | None = None) -> str:
    p = subprocess.run(cmd, input=input_text.encode() if input_text else None,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode())
    return p.stdout.decode()

def has_section(body: str, heading: str) -> bool:
    return re.search(rf"^\s*{re.escape(heading)}\s*$", body, re.M) is not None

def ensure_sections(number: int) -> None:
    data = json.loads(run(["gh","issue","view",str(number),"--json","body"]))
    body = data.get('body') or ''
    additions = []
    for h, template in SECTIONS:
        if not has_section(body, h):
            additions.append(f"\n\n{h}\n{template}")
    if additions:
        new_body = body + "".join(additions)
        run(["gh","issue","edit",str(number),"--body", new_body])

def main():
    # open issues only
    issues = json.loads(run(["gh","issue","list","--state","open","--limit","300","--json","number"]))
    for it in issues:
        try:
            ensure_sections(it['number'])
        except Exception as e:
            print(f"warn: #{it['number']}: {e}")
    print("ensure_issue_template: done")

if __name__ == '__main__':
    main()

