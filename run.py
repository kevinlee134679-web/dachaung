"""One portable entry point. Bootstrap uses only the Python standard library."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description='Dachaung local demo lifecycle')
    parser.add_argument('--venv', type=Path, default=ROOT / '.venv')
    parser.add_argument('command', choices=['setup', 'init-demo', 'status', 'serve', 'worker', 'backup', 'migrate', 'test', 'inventory'])
    args, rest = parser.parse_known_args()
    args.venv = args.venv.resolve()
    target = args.venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    os.chdir(ROOT)
    try:
        if args.command == 'setup':
            if rest:
                parser.error('setup accepts only --venv')
            if sys.version_info[:2] != (3, 14):
                raise ValueError('Setup requires CPython 3.14; verified version is 3.14.10.')
            if not target.exists():
                if args.venv.exists():
                    raise ValueError('Existing environment is incomplete; choose a new --venv path.')
                subprocess.run([sys.executable, '-m', 'venv', str(args.venv)], check=True)
        if not target.is_file():
            raise ValueError('Run setup with CPython 3.14 first, or select the existing --venv.')
        subprocess.run([str(target), '-B', '-c', "import sys; assert sys.version_info[:2] == (3,14), 'CPython 3.14 required'"], check=True)
        if args.command == 'setup':
            subprocess.run([str(target), '-m', 'pip', 'install', '-r', 'requirements.txt'], check=True)
            return subprocess.call([str(target), '-m', 'pip', 'check'])
        command = [str(target), '-B', '-X', 'utf8', '-m', 'medplatform.lifecycle', args.command, *rest]
        if os.name == 'nt':
            # Windows has no POSIX process replacement: keep the .cmd launcher
            # waiting for the application and propagate its real exit status.
            return subprocess.call(command)
        os.execv(str(target), command)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error) if isinstance(error, ValueError) else 'Environment command failed; check the preceding diagnostic.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
