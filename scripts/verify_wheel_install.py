from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_wheel_install.py DIST_DIRECTORY")
    wheels = sorted(Path(sys.argv[1]).glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("expected exactly one wheel")
    with tempfile.TemporaryDirectory(prefix="hf-wheel-") as temporary:
        environment = Path(temporary) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", str(wheels[0])], check=True)
        command = [
            str(python),
            "-c",
            "from harness_foundry.cli.app import main; main()",
            "version",
            "--format",
            "json",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
        if payload["command"] != "version" or payload["exit_code"] != 0:
            raise SystemExit("installed wheel smoke test failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
