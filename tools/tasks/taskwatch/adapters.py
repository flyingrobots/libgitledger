from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Tuple

from .ports import FilePort, LLMPort, ReporterPort, SleepPort


class LocalFS(FilePort):
    def mkdirs(self, d: Path) -> None:
        d.mkdir(parents=True, exist_ok=True)

    def list_files(self, d: Path) -> List[Path]:
        try:
            return sorted([p for p in d.iterdir() if p.is_file()])
        except FileNotFoundError:
            return []

    def read_text(self, p: Path) -> str:
        return p.read_text(encoding='utf-8', errors='replace')

    def write_text(self, p: Path, text: str) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')

    def append_text(self, p: Path, text: str) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open('a', encoding='utf-8') as f:
            f.write(text)

    def move_atomic(self, src: Path, dst: Path) -> bool:
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(str(src), str(dst))
            return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def exists(self, p: Path) -> bool:
        return p.exists()


class CodexLLM(LLMPort):
    def exec(self, prompt: str, timeout: float | None = None) -> Tuple[int, str, str]:
        try:
            proc = subprocess.run(["codex", "exec", prompt], capture_output=True, text=True, timeout=timeout)
            return proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired:
            return 124, "", f"timeout after {timeout} seconds" if timeout else "timeout"
        except FileNotFoundError as e:
            return 127, "", f"codex not found: {e}"
        except Exception as e:
            return 1, "", f"exception invoking codex: {e}"


class StdoutReporter(ReporterPort):
    def report(self, text: str) -> None:
        print(text, flush=True)


class RealSleeper(SleepPort):
    def sleep(self, seconds: float) -> None:
        import time

        time.sleep(seconds)
