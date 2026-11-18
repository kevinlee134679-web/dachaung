import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

from .config import ConfigurationError, load_settings
from .database import Database
from .errors import AppError, SchemaError
from .journal import Snapshot, append_record, snapshot
from .migrations import migrate, status


def main():
    parser = argparse.ArgumentParser(description="Shared platform: explicit lifecycle and S03 maintenance")
    parser.add_argument("command", choices=["init-db", "migrate", "db-status", "seed-demo", "seed-support-catalog", "seed-support-recipients", "seed-peer-groups",
                                          "seed-points", "seed-rewards", "expire-receipts", "s03-maintain", "run-task", "serve",
                                          "journal-snapshot", "journal-append"])
    parser.add_argument("--target", type=int)
    parser.add_argument("--journal", type=Path, default=Path("docs/工作记录.md"))
    parser.add_argument("--entry", type=Path)
    parser.add_argument("--expect-bytes", type=int)
    parser.add_argument("--expect-sha")
    parser.add_argument("--patient-id")
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument("--task-id")
    parser.add_argument("--expect-revision",type=int)
    parser.add_argument("--operation-key")
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
            elif args.command == 'seed-support-catalog':
                from .s05_catalog import seed_catalog
                print(json.dumps({'versions_added':seed_catalog(db),'outcome':'ready','is_simulated':True}))
            elif args.command == 'seed-support-recipients':
                from .o_sharing import seed_support_recipients
                print(json.dumps({'recipients_added':seed_support_recipients(db),'outcome':'ready','is_simulated':True}))
            elif args.command == 'seed-peer-groups':
                from .s05_peer_fixtures import seed_peer_groups
                print(json.dumps(seed_peer_groups(db) | {'outcome':'ready','is_simulated':True}))
            elif args.command == 'seed-points':
                from .s05_points import seed_points
                print(json.dumps({'accounts_added':seed_points(db),'outcome':'ready','is_simulated':True}))
            elif args.command == 'seed-rewards':
                from .s05_reward_catalog import seed_rewards
                print(json.dumps({'versions_added':seed_rewards(db),'outcome':'ready','is_simulated':True}))
            elif args.command == 'expire-receipts':
                from .idempotency import expire_receipts
                from .documents import now
                status(db)
                print(json.dumps(expire_receipts(db,now)))
            elif args.command in ('s03-maintain','run-task'):
                from .web import create_app
                status(db)
                execution=create_app(settings).state.s03_execution
                if args.command=='s03-maintain':
                    if not all((args.patient_id,args.window_start,args.window_end)):
                        parser.error('s03-maintain requires --patient-id and explicit --window-start/--window-end')
                    result=execution.maintenance(None,args.patient_id,args.window_start,args.window_end)
                else:
                    if not args.task_id or not args.expect_revision or not args.operation_key:
                        parser.error('run-task requires --task-id, --expect-revision and stable --operation-key')
                    result=execution.run_once(None,args.task_id,args.expect_revision,args.operation_key).data
                print(json.dumps(result,ensure_ascii=False))
            else:
                import uvicorn
                from .web import create_app
                logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
                uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT,
                            workers=1, access_log=False, log_level="info")
        return 0
    except AppError as error:
        print(json.dumps({'status':'error','error':{'code':error.code,'message':error.message}},ensure_ascii=False),file=sys.stderr)
        return 2
    except (ConfigurationError, SchemaError, sqlite3.Error, OSError, ValueError):
        # No raw environment values, paths, SQL, entries or credentials in errors.
        print("操作失败：配置、schema、文件或历史校验不满足要求；请核对运行说明。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
