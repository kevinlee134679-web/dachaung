"""Explicit local lifecycle; serving never initializes, migrates or starts a worker."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import uuid

from . import __version__
from .config import ROOT, ConfigurationError, load_settings
from .database import Database
from .errors import AppError, SchemaError
from .migrations import migrate, status

SEEDS = ('seed-demo', 'seed-support-catalog', 'seed-support-recipients', 'seed-peer-groups',
         'seed-points', 'seed-rewards', 'seed-support-rules')


class LifecycleError(ValueError):
    pass


def private_copy(source, destination):
    if source.is_symlink():
        raise LifecycleError('Backup refuses symbolic links')
    if source.is_dir():
        destination.mkdir(mode=0o700)
        for child in source.iterdir():
            private_copy(child, destination / child.name)
    elif source.is_file():
        with source.open('rb') as src, destination.open('xb') as dst:
            os.chmod(destination, 0o600)
            shutil.copyfileobj(src, dst)
    else:
        raise LifecycleError('Backup refuses special files')


def backup(db, *, directory=None):
    """Call only after stopping all writers; SQLite's online backup also captures WAL."""
    parent = Path(directory or ROOT / 'private' / 'backups')
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = parent / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    target.mkdir(mode=0o700)
    with db.connection(readonly=True) as conn:
        version = conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]
        destination = target / 'database.sqlite3'
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(descriptor)
        with closing(sqlite3.connect(destination)) as copy:
            conn.backup(copy)
            if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise LifecycleError('Backup integrity failed')
    files = db.path.parent / 'files-demo'
    if files.exists():
        private_copy(files, target / 'files-demo')
    if sys.platform == 'linux':
        from .linux_protection import KEY_ROOT, _key
        key_dir = KEY_ROOT / f'uid-{os.getuid()}'
        if key_dir.exists():
            _key(create=False)  # Refuse lost/unsafe/corrupt key before a migration.
            private_copy(key_dir, target / 'linux-key')
    if (ROOT / '.env').exists():
        private_copy(ROOT / '.env', target / 'configuration.env')
    manifest = dict(application=__version__, schema_version=f'{version:04d}',
                    source_database=str(db.path), created_at=datetime.now(timezone.utc).isoformat(),
                    protection='same Windows user/machine DPAPI' if os.name == 'nt' else 'same Linux UID and original AES-GCM key',
                    files={str(f.relative_to(target)): hashlib.sha256(f.read_bytes()).hexdigest()
                           for f in target.rglob('*') if f.is_file()})
    manifest_file = target / 'manifest.json'
    manifest_file.touch(mode=0o600)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['init-demo', 'status', 'serve', 'worker', 'backup', 'migrate', 'test', 'inventory'])
    parser.add_argument('--database', type=Path)
    parser.add_argument('--port', type=int)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--stopped', action='store_true', help='Confirm all web/worker/CLI writers using this DB are stopped')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if sys.version_info[:2] != (3, 14):
            raise ConfigurationError('CPython 3.14 required')
        settings = load_settings()
        updates = {}
        if args.database is not None:
            updates['DATABASE_PATH'] = args.database.resolve()
        if args.port is not None:
            updates['PORT'] = args.port
        # Revalidate overrides, including loopback host, port and mock-only modes.
        settings = type(settings)(**(settings.model_dump() | updates))
        db = Database(settings.database_path)
        env = dict(os.environ, DATABASE_PATH=str(db.path), PORT=str(settings.PORT))
        child = lambda *cmd: subprocess.run([sys.executable, '-B', '-X', 'utf8', '-m', 'medplatform', *cmd], cwd=ROOT, env=env, check=True)
        if args.command == 'init-demo':
            if db.path.exists():
                raise LifecycleError('Database already exists; initialization never resets it. Use status/migrate or choose a new path.')
            migrate(db, initialize=True)
            for seed in SEEDS:
                child(seed)
            print(json.dumps(dict(outcome='ready', app_version=__version__, schema_version=f'{status(db):04d}', is_simulated=True)))
        elif args.command in {'backup', 'migrate'}:
            if not args.stopped:
                raise LifecycleError('Stop all web, worker and other writers for this DB, then explicitly pass --stopped.')
            snapshot = backup(db, directory=args.output)
            print(json.dumps(dict(backup=str(snapshot), outcome='backup_ready')))
            if args.command == 'migrate':
                print(json.dumps(dict(schema_version=f'{migrate(db):04d}', outcome='ready')))
        elif args.command == 'test':
            if not shutil.which('node'):
                raise LifecycleError('Node.js is required to run the frontend regression suite; verified with Node 24.22.1.')
            subprocess.run([sys.executable, '-m', 'pip', 'check'], cwd=ROOT, check=True)
            return subprocess.call([sys.executable, '-B', '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'tests', '-v'], cwd=ROOT)
        elif args.command == 'inventory':
            from .inventory import export
            print(json.dumps(export(args.output or ROOT / 'docs' / 'S07'), ensure_ascii=False))
        else:
            status(db)
            if args.command == 'status':
                print(json.dumps(dict(schema_version=f'{status(db):04d}', outcome='ready', app_version=__version__)))
            else:
                os.environ.update(DATABASE_PATH=str(db.path), PORT=str(settings.PORT))
                if args.command == 'serve':
                    import uvicorn
                    from .web import create_app
                    uvicorn.run(create_app(settings), host=settings.HOST, port=settings.PORT,
                                workers=1, access_log=False, log_level='info')
                else:
                    from .s06_runner import Runner
                    from .web import create_app
                    Runner(create_app(settings)).run(once=args.once)
        return 0
    except (ConfigurationError, SchemaError, AppError, sqlite3.Error, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error) if isinstance(error, LifecycleError)
              else 'Lifecycle operation failed; check configuration, schema and the preceding diagnostic. Original data were not reset.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
