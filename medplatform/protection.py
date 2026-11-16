"""Windows per-user DPAPI. No plaintext or machine-wide fallback."""
import ctypes
import os
from ctypes import wintypes

from .errors import AppError


class Blob(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]


def _blob(raw):
    buffer = ctypes.create_string_buffer(raw)
    return Blob(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def transform(raw: bytes, context: str, *, decrypt=False) -> bytes:
    if os.name != 'nt':
        raise AppError(503, 'SENSITIVE_RECEIPT_UNAVAILABLE', '当前系统不支持本地受保护会话，请使用已验证的Windows环境')
    source, keep_source = _blob(raw)
    entropy, keep_entropy = _blob(context.encode('utf8'))
    output = Blob()
    crypt = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    fn = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not fn(ctypes.byref(source), None, ctypes.byref(entropy), None, None, 1, ctypes.byref(output)):
        raise AppError(503, 'SENSITIVE_RECEIPT_UNAVAILABLE', '受保护会话或回执不可解密，请核对原Windows账户及当前资源')
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        kernel.LocalFree(ctypes.cast(output.data, ctypes.c_void_p))


def protect(raw, context):
    return transform(raw, context)


def unprotect(raw, context):
    return transform(raw, context, decrypt=True)
