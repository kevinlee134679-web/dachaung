import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()

    @contextmanager
    def connection(self, *, readonly: bool = False, create: bool = False):
        mode = "ro" if readonly else ("rwc" if create else "rw")
        conn = sqlite3.connect(self.path.as_uri() + "?mode=" + mode, uri=True,
                               timeout=5, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
