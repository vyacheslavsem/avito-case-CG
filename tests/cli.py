"""Exercise the submission entry point, sharing identical live responses across assertions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


RUN = Path(__file__).resolve().parents[1] / "run"
_responses = {}
_last_start = 0.0


def run_case(catalog_path, request, timeout=120):
    global _last_start
    payload = json.dumps(request, ensure_ascii=False).encode("utf-8")
    key = (Path(catalog_path).read_bytes(), payload)
    if key not in _responses:
        # The team gateway accepts 20 generation attempts per rolling minute.
        time.sleep(max(0, 3.2 - (time.monotonic() - _last_start)))
        command = [sys.executable, str(RUN)] if os.name == "nt" else [str(RUN)]
        _last_start = time.monotonic()
        result = subprocess.run(
            [*command, "--catalog", str(catalog_path)],
            input=payload, capture_output=True, timeout=timeout,
        )
        assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        _responses[key] = result.stdout
    return json.loads(_responses[key].decode("utf-8"))
