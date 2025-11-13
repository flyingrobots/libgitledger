from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, Tuple


@dataclass
class Paths:
    base: Path              # wave base or global base for queue dirs
    open: Path
    blocked: Path
    claimed: Path
    closed: Path
    failed: Path
    dead: Path
    raw: Path               # always global under .slaps/tasks/raw
    admin: Path             # always global under .slaps/tasks/admin
    admin_closed: Path
    edges_csv: Path
    failure_reasons: Path
    attempts: Path


class FilePort(Protocol):
    def mkdirs(self, d: Path) -> None: ...
    def list_files(self, d: Path) -> List[Path]: ...
    def read_text(self, p: Path) -> str: ...
    def write_text(self, p: Path, text: str) -> None: ...
    def append_text(self, p: Path, text: str) -> None: ...
    def move_atomic(self, src: Path, dst: Path) -> bool: ...
    def exists(self, p: Path) -> bool: ...


class LLMPort(Protocol):
    def exec(self, prompt: str, timeout: float | None = None) -> Tuple[int, str, str]: ...  # rc, stdout, stderr


class SleepPort(Protocol):
    def sleep(self, seconds: float) -> None: ...


class ReporterPort(Protocol):
    def report(self, text: str) -> None: ...
