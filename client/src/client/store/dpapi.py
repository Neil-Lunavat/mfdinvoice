"""Windows DPAPI (CryptProtectData) via ctypes: secrets are only readable by this Windows user on this machine."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

_crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_ENTROPY = b"client.gst.cams"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _take(blob: _Blob) -> bytes:
    try:
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        _kernel32.LocalFree(blob.pbData)


def protect(plain: str) -> bytes:
    out = _Blob()
    if not _crypt32.CryptProtectData(ctypes.byref(_blob(plain.encode())), None, ctypes.byref(_blob(_ENTROPY)),
                                     None, None, 0x1, ctypes.byref(out)):  # CRYPTPROTECT_UI_FORBIDDEN
        raise ctypes.WinError(ctypes.get_last_error())
    return _take(out)


def unprotect(cipher: bytes) -> str:
    out = _Blob()
    if not _crypt32.CryptUnprotectData(ctypes.byref(_blob(cipher)), None, ctypes.byref(_blob(_ENTROPY)),
                                       None, None, 0x1, ctypes.byref(out)):
        raise ctypes.WinError(ctypes.get_last_error())
    return _take(out).decode()
