"""Byte-preserving, optimistic and OS-locked append-only Markdown history."""
import hashlib
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Snapshot:
    bytes: int
    sha256: str


def snapshot(path: Path) -> Snapshot:
    data = Path(path).read_bytes()
    return Snapshot(len(data), sha(data))


@contextmanager
def locked(stream, size):
    stream.seek(0)
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, max(1, size))
    else:
        import fcntl
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield
    finally:
        stream.seek(0)
        if os.name == "nt":
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, max(1, size))
        else:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def append_bytes(path: Path, addition: bytes, expected: Snapshot) -> dict:
    path = Path(path)
    # O_APPEND makes every write append; omitting O_CREAT refuses missing histories.
    descriptor = os.open(path, os.O_RDWR | os.O_APPEND | getattr(os, "O_BINARY", 0))
    with os.fdopen(descriptor, "a+b") as stream, locked(stream, expected.bytes):
        before = stream.read()
        if len(before) != expected.bytes or sha(before) != expected.sha256:
            raise ValueError("历史已变化，拒绝追加")
        stream.seek(0, 2)
        stream.write(addition)
        stream.flush()
        os.fsync(stream.fileno())
        stream.seek(0)
        after = stream.read()
        if after != before + addition:
            raise RuntimeError("历史前缀校验失败")
        return {"before": asdict(expected), "after": {"bytes": len(after), "sha256": sha(after)},
                "prefix_sha256": sha(after[:len(before)]), "prefix_bytes_equal": True}


def record_ids(text):
    return re.findall(r"^记录 ID：\s*(R\d{4})\s*$", text, re.M)


def validate_entry(entry: str, previous: str):
    ids = record_ids(previous)
    if ids != [f"R{i:04d}" for i in range(1, len(ids) + 1)]:
        raise ValueError("旧记录编号不连续或重复")
    if record_ids(entry) != [f"R{len(ids)+1:04d}"]:
        raise ValueError("新记录编号必须唯一递增")
    sections = ["一 本阶段代码编写完成情况", "二 本阶段未完成情况", "三 验证与证据",
                "四 下阶段代码编写要求", "五 代码编写总体约束快照", "六 本次变更与后续处理"]
    if any(section not in entry for section in sections):
        raise ValueError("新记录缺少必需章节")
    if "记录类型：更正" in entry:
        target = re.search(r"^更正引用：(R\d{4})\s*$", entry, re.M)
        if not target or target[1] not in ids:
            raise ValueError("更正必须引用已存在记录")


def append_record(path: Path, entry: str, expected: Snapshot) -> dict:
    previous = Path(path).read_text(encoding="utf-8")
    validate_entry(entry, previous)
    return append_bytes(path, ("\n\n" + entry.rstrip() + "\n").encode("utf-8"), expected)


def initialize(path: Path, entry: str):
    validate_entry(entry, "")
    with Path(path).open("xb") as stream:
        stream.write((entry.rstrip() + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())
