"""Verify and prepare the audited demo in a new directory using offline wheels."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys
import tarfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    if sys.version_info[:3] != (3, 14, 10) or sys.implementation.name != "cpython":
        parser.error("Use CPython 3.14.10 for the audited environment")
    if sys.maxsize <= 2**32 or platform.machine().lower() not in {"amd64", "x86_64"}:
        parser.error("This wheel archive targets x86-64")
    platform_folder = {"win32": "windows-x64", "linux": "linux-x64"}.get(sys.platform)
    if platform_folder is None:
        parser.error("This delivery was prepared for Windows and Linux")

    here = Path(__file__).resolve().parent
    checksums = json.loads((here / "package-checksums.json").read_text(encoding="utf-8"))
    for name in ("project-source.tar.gz", "dependencies.zip"):
        with (here / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != checksums[name]:
                raise SystemExit(f"SHA-256 mismatch: {name}")

    target = args.target.resolve()
    target.mkdir(parents=True, exist_ok=False)
    app = target / "app"
    app.mkdir()
    with tarfile.open(here / "project-source.tar.gz", "r:gz") as source:
        source.extractall(app, filter="data")
    dependencies = target / "dependencies"
    with zipfile.ZipFile(here / "dependencies.zip") as bundle:
        for entry in bundle.infolist():
            relative = PurePosixPath(entry.filename)
            if (len(relative.parts) != 2 or relative.parts[0] not in {"windows-x64", "linux-x64", "playwright"}
                    or ".." in relative.parts or "\\" in entry.filename or ":" in entry.filename):
                raise SystemExit(f"Unexpected dependency archive entry: {entry.filename}")
            if relative.parts[0] in {platform_folder, "playwright"}:
                bundle.extract(entry, dependencies)

    wheels = (dependencies / platform_folder).as_uri()
    env = dict(os.environ, PIP_NO_INDEX="1", PIP_FIND_LINKS=wheels,
               PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK="1")
    subprocess.run([sys.executable, "-B", "-X", "utf8", "run.py", "setup"],
                   cwd=app, env=env, check=True)
    print(f"APP_READY_PATH={app}")


if __name__ == "__main__":
    main()
