from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

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
    def exec(self, prompt: str, timeout: float | None = None, out_path: Optional[Path] = None, err_path: Optional[Path] = None) -> Tuple[int, str, str]:
        try:
            # If paths provided, stream outputs to files while capturing
            if out_path is not None or err_path is not None:
                if out_path is not None:
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    out_f = open(out_path, 'w', encoding='utf-8')
                else:
                    out_f = None
                if err_path is not None:
                    err_path.parent.mkdir(parents=True, exist_ok=True)
                    err_f = open(err_path, 'w', encoding='utf-8')
                else:
                    err_f = None
                try:
                    proc = subprocess.Popen(["codex", "exec", prompt], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                    out_buf: List[str] = []
                    err_buf: List[str] = []

                    def _drain(stream, sink, buf):
                        for line in stream:
                            if sink:
                                sink.write(line)
                                sink.flush()
                            buf.append(line)

                    import threading, time as _time
                    th_out = threading.Thread(target=_drain, args=(proc.stdout, out_f, out_buf)) if proc.stdout else None
                    th_err = threading.Thread(target=_drain, args=(proc.stderr, err_f, err_buf)) if proc.stderr else None
                    if th_out: th_out.start()
                    if th_err: th_err.start()
                    start = _time.time()
                    while True:
                        rc = proc.poll()
                        if rc is not None:
                            break
                        if timeout is not None and (_time.time() - start) > timeout:
                            proc.kill()
                            if th_out: th_out.join()
                            if th_err: th_err.join()
                            return 124, ''.join(out_buf), ''.join(err_buf) + (f"\n(timeout after {timeout} seconds)")
                        _time.sleep(0.1)
                    if th_out: th_out.join()
                    if th_err: th_err.join()
                    return rc, ''.join(out_buf), ''.join(err_buf)
                finally:
                    if out_f:
                        out_f.close()
                    if err_f:
                        err_f.close()
            else:
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
