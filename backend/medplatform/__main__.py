import argparse
import json
import sqlite3
import sys
from pathlib import Path

from . import __version__
from .core.backup import LifecycleError, backup
from .core.config import ConfigurationError, load_settings
from .core.database import Database
from .core.errors import AppError, SchemaError
from .core.migrations import migrate, status


def seed(db):
    from .identity.service import seed_demo
    from .identity.sharing import seed_support_recipients
    from .support.catalog.service import seed_catalog
    from .support.peer.fixtures import seed_peer_groups
    from .support.points.service import seed_points
    from .support.rewards.catalog import seed_rewards

    return {
        "demo": seed_demo(db),
        "catalog": seed_catalog(db),
        "recipients": seed_support_recipients(db),
        "peer_groups": seed_peer_groups(db),
        "points": seed_points(db),
        "rewards": seed_rewards(db),
    }


def main():
    parser = argparse.ArgumentParser(description="Platform administration")
    parser.add_argument(
        "command",
        choices=[
            "init-demo",
            "seed",
            "status",
            "serve",
            "worker",
            "backup",
            "migrate",
            "expire-receipts",
            "maintain",
            "run-task",
            "select-support-rule",
            "support-rule-status",
        ],
    )
    parser.add_argument("--database", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--stopped",
        action="store_true",
        help="Confirm all web/worker/CLI writers using this DB are stopped",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--target", type=int)
    parser.add_argument("--profile-id")
    parser.add_argument("--patient-id")
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument("--task-id")
    parser.add_argument("--expect-revision", type=int)
    parser.add_argument("--operation-key")
    args = parser.parse_args()
    try:
        if sys.version_info[:2] != (3, 14):
            raise ConfigurationError("CPython 3.14 required")
        settings = load_settings()
        updates = {}
        if args.database is not None:
            updates["DATABASE_PATH"] = args.database.resolve()
        if args.port is not None:
            updates["PORT"] = args.port
        settings = type(settings)(**(settings.model_dump() | updates))
        db = Database(settings.database_path)
        if args.command == "init-demo":
            if db.path.exists():
                raise LifecycleError(
                    "Database already exists; initialization never resets it. Use status/migrate or choose a new path."
                )
            migrate(db, initialize=True)
            seed(db)
            print(
                json.dumps(
                    {
                        "outcome": "ready",
                        "app_version": __version__,
                        "schema_version": f"{status(db):04d}",
                        "is_simulated": True,
                    }
                )
            )
        elif args.command in {"backup", "migrate"}:
            if not args.stopped:
                raise LifecycleError(
                    "Stop all web, worker and other writers for this DB, then explicitly pass --stopped."
                )
            snapshot = backup(db, directory=args.output)
            print(json.dumps({"backup": str(snapshot), "outcome": "backup_ready"}))
            if args.command == "migrate":
                print(
                    json.dumps(
                        {
                            "schema_version": f"{migrate(db, target=args.target):04d}",
                            "outcome": "ready",
                        }
                    )
                )
        else:
            version = status(db)
            if args.command == "seed":
                print(json.dumps(seed(db), ensure_ascii=False))
            elif args.command == "status":
                print(
                    json.dumps(
                        {
                            "schema_version": f"{version:04d}",
                            "outcome": "ready",
                            "app_version": __version__,
                        }
                    )
                )
            elif args.command == "expire-receipts":
                from .core.documents import now
                from .core.idempotency import expire_receipts

                print(json.dumps(expire_receipts(db, now)))
            elif args.command in ("maintain", "run-task"):
                from .web.app import create_app

                execution = create_app(settings).state.execution
                if args.command == "maintain":
                    if not all((args.patient_id, args.window_start, args.window_end)):
                        parser.error(
                            "maintain requires --patient-id and explicit --window-start/--window-end"
                        )
                    result = execution.maintenance(
                        None, args.patient_id, args.window_start, args.window_end
                    )
                else:
                    if (
                        not args.task_id
                        or not args.expect_revision
                        or not args.operation_key
                    ):
                        parser.error(
                            "run-task requires --task-id, --expect-revision and stable --operation-key"
                        )
                    result = execution.run_once(
                        None, args.task_id, args.expect_revision, args.operation_key
                    ).data
                print(json.dumps(result, ensure_ascii=False))
            elif args.command in ("select-support-rule", "support-rule-status"):
                from .dialogue import rules

                if args.command == "support-rule-status":
                    with db.connection(readonly=True) as conn:
                        result = {
                            "profile_id": rules.active(conn),
                            "is_simulated": True,
                        }
                else:
                    if not args.profile_id:
                        parser.error("select-support-rule requires --profile-id")
                    result = rules.select(db, args.profile_id)
                print(json.dumps(result))
            elif args.command == "worker":
                from .medication.runner import Runner
                from .web.app import create_app

                Runner(create_app(settings)).run(once=args.once)
            else:
                import uvicorn

                from .web.app import create_app

                uvicorn.run(
                    create_app(settings),
                    host=settings.HOST,
                    port=settings.PORT,
                    workers=1,
                    access_log=False,
                    log_level="info",
                )
        return 0
    except AppError as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": {"code": error.code, "message": error.message},
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except (
        ConfigurationError,
        SchemaError,
        sqlite3.Error,
        OSError,
        ValueError,
    ) as error:
        print(
            str(error)
            if isinstance(error, LifecycleError)
            else "Lifecycle operation failed; check configuration, schema and the preceding diagnostic. Original data were not reset.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
