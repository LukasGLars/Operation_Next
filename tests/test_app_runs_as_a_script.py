# -*- coding: utf-8 -*-
"""The app is started with `python app/app.py`, not as an imported package.

Every other test imports `app.app` with the repo root already on sys.path, so
none of them can see an import that only breaks under the real entry point. A
`from pipeline import ...` added in v0.7.1 shipped exactly that way and took the
UI down until someone tried to open it.

`python app/app.py` puts *app/* on sys.path, not the repo root — which is why
`python -c "...run_path('app/app.py')"` does not reproduce it: -c puts the
working directory on the path and hides the bug. The real command is the test.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_app_starts_under_its_real_entry_point():
    proc = subprocess.Popen([sys.executable, "app/app.py"], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    try:
        # Starting successfully means it blocks serving; that timeout is the pass.
        output, _ = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        return
    assert "ModuleNotFoundError" not in output, output[-800:]
    assert False, f"app exited instead of serving:\n{output[-800:]}"
