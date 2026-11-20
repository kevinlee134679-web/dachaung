import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from .. import __version__
from .config import ROOT


class LifecycleError(ValueError):
    pass


def private_copy(source, destination):
    if source.is_symlink() or source.is_junction():
        raise LifecycleError("Backup refuses symbolic links and directory junctions")
    if source.is_dir():
        destination.mkdir(mode=0o700)
        for child in source.iterdir():
            private_copy(child, destination / child.name)
    elif source.is_file():
        with source.open("rb") as src, destination.open("xb") as dst:
            os.chmod(destination, 0o600)
            shutil.copyfileobj(src, dst)
    else:
        raise LifecycleError("Backup refuses special files")


def backup(db, *, directory=None):
    """Call only after stopping all writers; SQLite's online backup also captures WAL."""
    parent = Path(directory or ROOT / "private" / "backups")
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = parent / (
        datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    )
    target.mkdir(mode=0o700)
    with db.connection(readonly=True) as conn:
        version = conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[
            0
        ]
        destination = target / "database.sqlite3"
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(destination)) as copy:
            conn.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise LifecycleError("Backup integrity failed")
    files = db.path.parent / "files-demo"
    if files.exists(follow_symlinks=False):
        private_copy(files, target / "files-demo")
    if os.name == "posix":
        from .posix_protection import KEY_ROOT, _key

        key_dir = KEY_ROOT / f"uid-{os.getuid()}"
        if key_dir.exists():
            _key(create=False)
            private_copy(key_dir, target / "linux-key")
    if (ROOT / ".env").exists(follow_symlinks=False):
        private_copy(ROOT / ".env", target / "configuration.env")
    manifest = {
        "application": __version__,
        "schema_version": f"{version:04d}",
        "source_database": str(db.path),
        "created_at": datetime.now(UTC).isoformat(),
        "protection": "same Windows user/machine DPAPI"
        if os.name == "nt"
        else "same POSIX UID and original AES-GCM key",
        "files": {
            str(f.relative_to(target)): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in target.rglob("*")
            if f.is_file()
        },
    }
    manifest_file = target / "manifest.json"
    manifest_file.touch(mode=0o600)
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    return target
