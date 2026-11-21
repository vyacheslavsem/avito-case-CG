"""
CLI Wrapper — обёртка над runner.py для вызова через subprocess/API.
Принимает список messages, вызывает src/runner.py и парсит JSON-ответ.
"""

import json
import os
import subprocess
from pathlib import Path

RUNNER_PATH = Path(__file__).parent / "src" / "runner.py"
DEFAULT_CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"
PROJECT_ROOT = Path(__file__).parent


def call_cli(messages: list[dict], catalog_path: Path | str | None = None, timeout: int = 60) -> dict:
    """
    Вызывает src/runner.py с переданными messages и возвращает распарсенный ответ.

    Args:
        messages: массив сообщений диалога (как в request.schema.json)
        catalog_path: путь к каталогу (по умолчанию data/catalog.json)
        timeout: таймаут в секундах

    Returns:
        dict с полем status ("ok", "clarify", "no_match") и данными
    """
    if catalog_path is None:
        catalog_path = DEFAULT_CATALOG_PATH

    request_body = json.dumps({"messages": messages}).encode("utf-8")

    cmd = ["python", str(RUNNER_PATH), "--catalog", str(catalog_path)]

    # Устанавливаем рабочую директорию проекта для корректного импорта модулей
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    result = subprocess.run(
        cmd,
        input=request_body,
        capture_output=True,
        text=False,  # bytes для stdin/stdout
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
        env=env,
    )

    if result.returncode != 0:
        error_msg = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"runner.py exited with code {result.returncode}: {error_msg}")

    output = json.loads(result.stdout.decode("utf-8"))
    return output
