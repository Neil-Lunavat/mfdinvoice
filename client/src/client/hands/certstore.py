"""Windows' certificate store: the signing certificates on this PC's USB tokens, and a signature made with one.

A token's own software copies its certificates into the person's store ("MY") when the token is plugged in, and names
itself as the keeper of each one's key. Asking Windows to sign with such a certificate hands the job to that software,
which shows **its own PIN box**. Our code never sees the PIN, never holds the key, and gets back only the signature.

Two generations of token software exist and both are spoken here: CNG (`NCryptSignHash`) and the older CryptoAPI
(`CryptSignHash`). Windows says which one a certificate's key belongs to when the key is acquired.

Nothing here lists or touches a certificate whose key lives in Windows itself (a file on the disk): those are not
tokens, and offering one as "your DSC" would be wrong. `tokens_only=False` exists for the tests, which sign with a
throwaway certificate of that kind to prove the signing itself.
"""

from __future__ import annotations

import ctypes
import hashlib
import sys
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime

from asn1crypto import x509

STORE = "MY"

# Where Windows itself keeps a key. Anything else named as a certificate's key provider is a token's own software.
IN_WINDOWS = ("microsoft software key storage provider", "microsoft enhanced cryptographic provider",
              "microsoft strong cryptographic provider", "microsoft base cryptographic provider",
              "microsoft enhanced rsa and aes cryptographic provider", "microsoft rsa schannel cryptographic provider",
              "microsoft base dss", "microsoft enhanced dss", "microsoft dh schannel",
              "microsoft platform crypto provider", "microsoft passport key storage provider")

CERT_KEY_PROV_INFO_PROP_ID = 2
CRYPT_ACQUIRE_COMPARE_KEY_FLAG = 0x4
CRYPT_ACQUIRE_SILENT_FLAG = 0x40
CRYPT_ACQUIRE_PREFER_NCRYPT_KEY_FLAG = 0x20000
CERT_NCRYPT_KEY_SPEC = 0xFFFFFFFF
BCRYPT_PAD_PKCS1 = 0x2
CALG = {"sha256": 0x800C, "sha384": 0x800D, "sha512": 0x800E, "sha1": 0x8004}
HP_HASHVAL = 2
PP_CLIENT_HWND = 1

# What a token's software answers when the person, not the software, is why nothing was signed.
CANCELLED = (0x8010006E, 0x800704C7, 0x80090036, 1223)   # SCARD_W_CANCELLED_BY_USER, ERROR_CANCELLED, NTE_USER_CANCELLED
WRONG_PIN = (0x8010006B, 0x8010002A)                     # SCARD_W_WRONG_CHV, SCARD_E_INVALID_CHV
LOCKED = (0x8010006C,)                                   # SCARD_W_CHV_BLOCKED
# No card, card removed, no reader, reader gone, no smart card service, and "the key is not there" twice over.
NO_TOKEN = (0x8010000C, 0x80100069, 0x80100009, 0x8010002E, 0x80100017, 0x8010001D, 0x80090016, 0x8009000D)


class StoreError(Exception):
    """Windows, or the token's software, said no. `why`: cancelled, wrong_pin, locked, no_token or failed."""

    def __init__(self, why: str, said: str = "", code: int = 0):
        self.why, self.said, self.code = why, said, code
        super().__init__(f"{why}: {said}" if said else why)


@dataclass(frozen=True)
class Cert:
    """One signing certificate, as the window shows it and as the app keeps it. Never a key."""

    thumbprint: str          # SHA-1 of the certificate, the way Windows names one
    name: str                # who it is issued to
    issuer: str              # which certifying authority issued it
    expires: str             # ISO date
    provider: str            # the software that keeps its key
    der: bytes = b""

    def view(self) -> dict:
        return {"thumbprint": self.thumbprint, "name": self.name, "issuer": self.issuer, "expires": self.expires}


if sys.platform == "win32":
    class _Context(ctypes.Structure):
        _fields_ = [("dwCertEncodingType", wintypes.DWORD), ("pbCertEncoded", ctypes.POINTER(ctypes.c_ubyte)),
                    ("cbCertEncoded", wintypes.DWORD), ("pCertInfo", ctypes.c_void_p),
                    ("hCertStore", ctypes.c_void_p)]

    class _ProvInfo(ctypes.Structure):
        _fields_ = [("pwszContainerName", wintypes.LPWSTR), ("pwszProvName", wintypes.LPWSTR),
                    ("dwProvType", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("cProvParam", wintypes.DWORD),
                    ("rgProvParam", ctypes.c_void_p), ("dwKeySpec", wintypes.DWORD)]

    class _Pkcs1(ctypes.Structure):
        _fields_ = [("pszAlgId", wintypes.LPCWSTR)]

    _crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    _ncrypt = ctypes.WinDLL("ncrypt", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    _P = ctypes.POINTER(_Context)
    _crypt32.CertOpenSystemStoreW.restype = ctypes.c_void_p
    _crypt32.CertOpenSystemStoreW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _crypt32.CertEnumCertificatesInStore.restype = _P
    _crypt32.CertEnumCertificatesInStore.argtypes = [ctypes.c_void_p, _P]
    _crypt32.CertDuplicateCertificateContext.restype = _P
    _crypt32.CertDuplicateCertificateContext.argtypes = [_P]
    _crypt32.CertFreeCertificateContext.argtypes = [_P]
    _crypt32.CertCloseStore.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    _crypt32.CertGetCertificateContextProperty.argtypes = [_P, wintypes.DWORD, ctypes.c_void_p,
                                                           ctypes.POINTER(wintypes.DWORD)]
    _crypt32.CryptAcquireCertificatePrivateKey.argtypes = [
        _P, wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.BOOL)]
    _ncrypt.NCryptSignHash.restype = ctypes.c_long
    _ncrypt.NCryptSignHash.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_char_p, wintypes.DWORD,
                                       ctypes.c_char_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    _ncrypt.NCryptSetProperty.restype = ctypes.c_long
    _ncrypt.NCryptSetProperty.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_void_p, wintypes.DWORD,
                                          wintypes.DWORD]
    _ncrypt.NCryptFreeObject.argtypes = [ctypes.c_void_p]
    _advapi32.CryptCreateHash.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                          ctypes.POINTER(ctypes.c_void_p)]
    _advapi32.CryptSetHashParam.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_char_p, wintypes.DWORD]
    _advapi32.CryptSignHashW.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.LPCWSTR, wintypes.DWORD,
                                         ctypes.c_char_p, ctypes.POINTER(wintypes.DWORD)]
    _advapi32.CryptDestroyHash.argtypes = [ctypes.c_void_p]
    _advapi32.CryptSetProvParam.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    _advapi32.CryptReleaseContext.argtypes = [ctypes.c_void_p, wintypes.DWORD]


def available() -> bool:
    """Can this PC reach a certificate store at all? Only Windows has one."""
    return sys.platform == "win32"


# --- what is there ----------------------------------------------------------------------------------------------

def _each(store: str):
    """Every certificate in one of the person's stores, as (context, DER). The context is only good inside the loop."""
    h = _crypt32.CertOpenSystemStoreW(None, store)
    if not h:
        return
    try:
        ctx = _crypt32.CertEnumCertificatesInStore(h, None)
        while ctx:
            yield ctx, ctypes.string_at(ctx.contents.pbCertEncoded, ctx.contents.cbCertEncoded)
            ctx = _crypt32.CertEnumCertificatesInStore(h, ctx)       # frees the one before
    finally:
        _crypt32.CertCloseStore(h, 0)


def _provider(ctx) -> str:
    """The software that keeps this certificate's key, or "" when it has no key on this PC."""
    size = wintypes.DWORD(0)
    if not _crypt32.CertGetCertificateContextProperty(ctx, CERT_KEY_PROV_INFO_PROP_ID, None, ctypes.byref(size)):
        return ""
    buf = ctypes.create_string_buffer(size.value)
    if not _crypt32.CertGetCertificateContextProperty(ctx, CERT_KEY_PROV_INFO_PROP_ID, buf, ctypes.byref(size)):
        return ""
    return ctypes.cast(buf, ctypes.POINTER(_ProvInfo)).contents.pwszProvName or ""


def on_a_token(provider: str) -> bool:
    return bool(provider) and not provider.strip().lower().startswith(IN_WINDOWS)


def describe(der: bytes, provider: str = "") -> Cert | None:
    """A certificate as the person would recognise it. None for one that cannot sign a document, or is past its date."""
    try:
        cert = x509.Certificate.load(der)
        usage = cert.key_usage_value
        if usage is not None and not ({"digital_signature", "non_repudiation"} & usage.native):
            return None                                  # an encryption certificate: tokens carry one beside the signing one
        if cert.ca:
            return None
        if cert.not_valid_after < datetime.now(UTC) or cert.not_valid_before > datetime.now(UTC):
            return None
        subject, issuer = cert.subject.native, cert.issuer.native
        return Cert(thumbprint=hashlib.sha1(der).hexdigest().upper(),  # noqa: S324 - Windows' own name for a certificate
                    name=_one(subject.get("common_name")) or cert.subject.human_friendly,
                    issuer=_one(issuer.get("common_name")) or _one(issuer.get("organization_name")) or "",
                    expires=cert.not_valid_after.date().isoformat(), provider=provider, der=der)
    except Exception:                                    # a certificate we cannot read is one we do not offer
        return None


def _one(value) -> str:
    return str(value[0] if isinstance(value, list) and value else value or "")


def certificates(tokens_only: bool = True) -> list[Cert]:
    """The certificates this PC can sign a document with right now, soonest to expire last."""
    if not available():
        return []
    out = []
    for ctx, der in _each(STORE):
        provider = _provider(ctx)
        if not provider or (tokens_only and not on_a_token(provider)):
            continue
        cert = describe(der, provider)
        if cert:
            out.append(cert)
    return sorted(out, key=lambda c: c.expires, reverse=True)


def find(thumbprint: str) -> Cert | None:
    """The certificate the person picked, if Windows still has it (a token's software takes it away with the token)."""
    if not available():
        return None
    for ctx, der in _each(STORE):
        if hashlib.sha1(der).hexdigest().upper() == thumbprint.upper():  # noqa: S324
            return describe(der, _provider(ctx)) or Cert(thumbprint.upper(), "", "", "", _provider(ctx), der)
    return None


def chain(der: bytes) -> list[bytes]:
    """The certificates that issued this one, nearest first, as far as Windows knows them, without the root. They go
    into the signature beside the signer's own, so whoever opens the PDF can follow it back to the authority."""
    if not available():
        return []
    pool: dict[bytes, list[x509.Certificate]] = {}
    for store in ("CA", "Root"):
        for _ctx, raw in _each(store):
            try:
                c = x509.Certificate.load(raw)
                pool.setdefault(c.subject.dump(), []).append(c)
            except Exception:                            # noqa: S112 - an unreadable authority is skipped
                continue
    out, at = [], x509.Certificate.load(der)
    for _ in range(6):
        if at.self_issued in ("yes", "maybe") and at.subject == at.issuer:
            break
        issuers = pool.get(at.issuer.dump(), [])
        aki = at.authority_key_identifier
        nxt = next((c for c in issuers if aki is None or c.key_identifier == aki), issuers[0] if issuers else None)
        if nxt is None or nxt.subject == nxt.issuer:
            break
        out.append(nxt.dump())
        at = nxt
    return out


# --- signing ----------------------------------------------------------------------------------------------------

class Key:
    """A certificate's key, held open for as long as a run signs with it. The key itself stays in the token: this is
    only Windows' handle on it, and every signature is the token's own software doing the work."""

    def __init__(self, thumbprint: str, hwnd: int = 0, silent: bool = False):
        if not available():
            raise StoreError("failed", "This PC has no certificate store.")
        self.cert = None
        for ctx, der in _each(STORE):
            if hashlib.sha1(der).hexdigest().upper() == thumbprint.upper():  # noqa: S324
                self._ctx, self.cert = _crypt32.CertDuplicateCertificateContext(ctx), der
                break
        if self.cert is None:
            raise StoreError("no_token")
        handle, spec, ours = ctypes.c_void_p(), wintypes.DWORD(), wintypes.BOOL()
        flags = CRYPT_ACQUIRE_PREFER_NCRYPT_KEY_FLAG | CRYPT_ACQUIRE_COMPARE_KEY_FLAG
        if not _crypt32.CryptAcquireCertificatePrivateKey(self._ctx, flags | (CRYPT_ACQUIRE_SILENT_FLAG if silent else 0),
                                                          None, ctypes.byref(handle), ctypes.byref(spec),
                                                          ctypes.byref(ours)):
            code = ctypes.get_last_error()
            _crypt32.CertFreeCertificateContext(self._ctx)
            raise _error(code)
        self._handle, self._spec, self._ours = handle, spec.value, bool(ours.value)
        self.cng = self._spec == CERT_NCRYPT_KEY_SPEC
        if hwnd:                                         # the token's PIN box opens over our window, not behind it
            h = wintypes.HWND(hwnd)
            if self.cng:
                _ncrypt.NCryptSetProperty(self._handle, "HWND Handle", ctypes.byref(h), ctypes.sizeof(h), 0)
            else:
                _advapi32.CryptSetProvParam(self._handle, PP_CLIENT_HWND, ctypes.byref(h), 0)

    def sign(self, digest: bytes, algorithm: str = "sha256") -> bytes:
        """Sign a digest already made (RSA, PKCS#1 v1.5; an elliptic-curve key answers r then s). This is the call the
        token's software answers with its PIN box the first time."""
        return self._sign_cng(digest, algorithm) if self.cng else self._sign_capi(digest, algorithm)

    def _sign_cng(self, digest: bytes, algorithm: str) -> bytes:
        rsa = x509.Certificate.load(self.cert).public_key.algorithm == "rsa"
        pad = _Pkcs1(algorithm.upper()) if rsa else None
        flags = BCRYPT_PAD_PKCS1 if rsa else 0
        info = ctypes.byref(pad) if rsa else None
        size = wintypes.DWORD(0)
        status = _ncrypt.NCryptSignHash(self._handle, info, digest, len(digest), None, 0, ctypes.byref(size), flags)
        if status:
            raise _error(status)
        buf = ctypes.create_string_buffer(size.value)
        status = _ncrypt.NCryptSignHash(self._handle, info, digest, len(digest), buf, size.value, ctypes.byref(size),
                                        flags)
        if status:
            raise _error(status)
        return buf.raw[:size.value]

    def _sign_capi(self, digest: bytes, algorithm: str) -> bytes:
        if algorithm not in CALG:
            raise StoreError("failed", f"This token's software cannot sign with {algorithm}.")
        h = ctypes.c_void_p()
        if not _advapi32.CryptCreateHash(self._handle, CALG[algorithm], None, 0, ctypes.byref(h)):
            raise _error(ctypes.get_last_error())
        try:
            if not _advapi32.CryptSetHashParam(h, HP_HASHVAL, digest, 0):
                raise _error(ctypes.get_last_error())
            size = wintypes.DWORD(0)
            if not _advapi32.CryptSignHashW(h, self._spec, None, 0, None, ctypes.byref(size)):
                raise _error(ctypes.get_last_error())
            buf = ctypes.create_string_buffer(size.value)
            if not _advapi32.CryptSignHashW(h, self._spec, None, 0, buf, ctypes.byref(size)):
                raise _error(ctypes.get_last_error())
            return buf.raw[:size.value][::-1]            # CryptoAPI answers little-endian; a signature is big-endian
        finally:
            _advapi32.CryptDestroyHash(h)

    def close(self) -> None:
        if getattr(self, "_handle", None) and self._ours:
            if self.cng:
                _ncrypt.NCryptFreeObject(self._handle)
            else:
                _advapi32.CryptReleaseContext(self._handle, 0)
        if getattr(self, "_ctx", None):
            _crypt32.CertFreeCertificateContext(self._ctx)
        self._handle = self._ctx = None


def _error(code: int) -> StoreError:
    code &= 0xFFFFFFFF
    why = ("cancelled" if code in CANCELLED else "wrong_pin" if code in WRONG_PIN else "locked" if code in LOCKED
           else "no_token" if code in NO_TOKEN else "failed")
    return StoreError(why, ctypes.FormatError(code).strip(), code)


def here(thumbprint: str) -> bool:
    """Is this certificate's token plugged in, as far as can be told without bothering the person? Only a plain no
    counts as no: Windows no longer lists the certificate, or its software says the token is not there. Software that
    will not answer without showing something is taken as yes, and the run finds out at Sign."""
    try:
        Key(thumbprint, silent=True).close()
        return True
    except StoreError as e:
        return e.why != "no_token"
