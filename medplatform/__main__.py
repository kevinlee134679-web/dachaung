import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

from .config import ConfigurationError, load_settings
from .database import Database
from .errors import SchemaError
from .journal import Snapshot, append_record, snapshot
from .migrations import migrate, status


def main():
    parser = argparse.ArgumentParser(description="S01 shared foundation: explicit lifecycle")
    parser.add_argument("command", choices=["init-db", "migrate", "db-status", "seed-demo", "expire-receipts", "serve", "journal-snapshot", "journal-append"])
    parser.add_argument("--target", type=int)
    parser.add_argument("--journal", type=Path, default=Path("docs/工作记录.md"))
    parser.add_argument("--entry", type=Path)
    parser.add_argument("--expect-bytes", type=int)
    parser.add_argument("--expect-sha")
    args = parser.parse_args()
    try:
        if args.command == "journal-snapshot":
            from dataclasses import asdict
            print(json.dumps(asdict(snapshot(args.journal))))
        elif args.command == "journal-append":
            if args.entry is None or args.expect_bytes is None or not args.expect_sha:
                parser.error("journal-append requires entry and expected bytes/SHA256")
            print(json.dumps(append_record(args.journal, args.entry.read_text(encoding="utf-8"),
                                          Snapshot(args.expect_bytes, args.expect_sha))))
        else:
            settings = load_settings()
            db = Database(settings.database_path)
            if args.command in {"init-db", "migrate"}:
                version = migrate(db, initialize=args.command == "init-db", target=args.target)
                print(json.dumps({"schema_version": f"{version:04d}", "outcome": "ready"}))
            elif args.command == "db-status":
                print(json.dumps({"schema_version": f"{status(db):04d}", "outcome": "ready"}))
            elif args.command == 'seed-demo':
                from .s02_service import seed_demo
                print(json.dumps({'demo_version':seed_demo(db),'outcome':'ready','is_simulated':True}))
            elif args.command == 'expire-receipts':
                from .idempotency import expire_receipts
                from .documents import now
                status(db)
                print(json.dumps(expire_receipts(db,now)))
            else:
                import uvicorn
                from .web import create_app
                logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
                uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT,
                            workers=1, access_log=False, log_level="info")
        return 0
    except (ConfigurationError, SchemaError, sqlite3.Error, OSError, ValueError):
        # No raw environment values, paths, SQL, entries or credentials in errors.
        print("操作失败：配置、schema、文件或历史校验不满足要求；请核对运行说明。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
