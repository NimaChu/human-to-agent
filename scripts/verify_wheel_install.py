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
    with tempfile.TemporaryDirectory(prefix="hta-wheel-") as temporary:
        environment = Path(temporary) / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", str(wheels[0])], check=True)
        cli = [str(python), "-c", "from human_to_agent.cli.app import main; main()"]

        def run_cli(*arguments: str) -> dict[str, object]:
            completed = subprocess.run(
                [*cli, *arguments], check=True, capture_output=True, text=True
            )
            payload = json.loads(completed.stdout)
            if not isinstance(payload, dict) or payload.get("exit_code") != 0:
                raise SystemExit("installed wheel smoke test failed")
            return payload

        if run_cli("version", "--format", "json").get("command") != "version":
            raise SystemExit("installed wheel version smoke test failed")

        workspace_root = Path(temporary) / "workspace-root"
        if run_cli("init", "--root", str(workspace_root), "--format", "json").get(
            "command"
        ) != "init":
            raise SystemExit("installed wheel init smoke test failed")
        if run_cli(
            "workspace",
            "new",
            "wheel-smoke",
            "--root",
            str(workspace_root),
            "--format",
            "json",
        ).get("command") != "workspace new":
            raise SystemExit("installed wheel workspace smoke test failed")
        if not (workspace_root / "workspaces" / "wheel-smoke" / "workspace.yaml").is_file():
            raise SystemExit("installed wheel did not render child workspace templates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
