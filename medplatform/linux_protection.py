"""Linux local encryption; private key files are separate from SQLite and Git.

The first explicit protected write initializes a per-UID key. Reads never create
keys. A marker prevents silently replacing a lost key on a later write. This is
filesystem-based local protection, not an OS credential vault or production KMS.
"""
import fcntl
import os
from pathlib import Path
import secrets
import stat
from contextlib import contextmanager

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


KEY_ROOT = Path(__file__).resolve().parent.parent / 'private' / 'local-protection'
PREFIX = b'medplatform-linux-aesgcm-v1\x00'
KEY_FILE = 'key-v1.bin'
MARKER = 'initialized-v1'


def _check(descriptor, *, directory=False, private=True):
    info = os.fstat(descriptor)
    correct_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    mode = stat.S_IMODE(info.st_mode)
    expected_mode = 0o700 if directory else 0o600
    unsafe_mode = mode != expected_mode if private else bool(mode & 0o022)
    if (not correct_type or info.st_uid != os.getuid()
            or unsafe_mode
            or (not directory and info.st_nlink != 1)):
        raise ValueError('Unsafe local key storage')


@contextmanager
def _directory(create):
    # The project owns private/. Refuse a substituted or writable parent, then
    # use directory-relative descriptors so checked paths cannot be swapped.
    if create:
        KEY_ROOT.parent.mkdir(mode=0o700, exist_ok=True)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(KEY_ROOT.parent, flags)
    try:
        _check(parent, directory=True, private=False)
        if create:
            try:
                os.mkdir(KEY_ROOT.name, mode=0o700, dir_fd=parent)
            except FileExistsError:
                pass
        root = os.open(KEY_ROOT.name, flags, dir_fd=parent)
        try:
            _check(root, directory=True)
            name = f'uid-{os.getuid()}'
            if create:
                try:
                    os.mkdir(name, mode=0o700, dir_fd=root)
                except FileExistsError:
                    pass
            directory = os.open(name, flags, dir_fd=root)
            try:
                _check(directory, directory=True)
                fcntl.flock(directory, fcntl.LOCK_EX)
                try:
                    yield directory
                finally:
                    fcntl.flock(directory, fcntl.LOCK_UN)
            finally:
                os.close(directory)
        finally:
            os.close(root)
    finally:
        os.close(parent)


def _key(*, create):
    with _directory(create) as directory:
        try:
            descriptor = os.open(KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        except FileNotFoundError:
            if not create:
                raise
            # Creating the marker first makes interrupted initialization fail
            # closed as well. Other processes serialize on the directory lock.
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
            marker = os.open(MARKER, flags, 0o600, dir_fd=directory)
            try:
                os.fsync(marker)
            finally:
                os.close(marker)
            os.fsync(directory)
            descriptor = os.open(KEY_FILE, flags, 0o600, dir_fd=directory)
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(secrets.token_bytes(32))
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(directory)
            descriptor = os.open(KEY_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        try:
            _check(descriptor)
            key = os.read(descriptor, 33)
            if len(key) != 32:
                raise ValueError('Invalid local key')
            return key
        finally:
            os.close(descriptor)


def transform(raw: bytes, context: str, *, decrypt=False) -> bytes:
    aad = PREFIX + os.getuid().to_bytes(8, 'big') + context.encode('utf8')
    if decrypt:
        if not raw.startswith(PREFIX) or len(raw) < len(PREFIX) + 12 + 16:
            raise ValueError('Unsupported protected payload')
        nonce = raw[len(PREFIX):len(PREFIX) + 12]
        try:
            return AESGCM(_key(create=False)).decrypt(nonce, raw[len(PREFIX) + 12:], aad)
        except InvalidTag:
            raise ValueError('Protected payload authentication failed') from None
    nonce = secrets.token_bytes(12)
    return PREFIX + nonce + AESGCM(_key(create=True)).encrypt(nonce, raw, aad)
