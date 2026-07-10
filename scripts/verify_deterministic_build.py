from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

from harness_foundry.domain.builds import BuildMode
from harness_foundry.services.build import Builder


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(item for item in path.rglob("*") if item.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_deterministic_build.py WORKSPACE")
    builder = Builder(Path.cwd())
    with tempfile.TemporaryDirectory(prefix="hf-determinism-") as temporary:
        root = Path(temporary)
        first = builder.build(builder.plan(sys.argv[1], BuildMode.release, root / "one"))
        second = builder.build(builder.plan(sys.argv[1], BuildMode.release, root / "two"))
        if digest_tree(first.path) != digest_tree(second.path):
            raise SystemExit("release builds differ")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
