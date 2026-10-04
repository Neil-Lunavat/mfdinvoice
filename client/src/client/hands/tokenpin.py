"""A USB token reached through its own driver, with the PIN typed in our window. The second route, used only when a
token cannot be reached through Windows' certificate store (`certstore`).

Every token maker ships a driver file that speaks one common language (PKCS#11). This module looks for the drivers of
the tokens sold with Indian signing certificates, lists the signing certificates on whatever is plugged in (that needs
no PIN), and signs with one once the token has been opened with its PIN.

The PIN is typed by the person, handed straight to the token, and held in this process's memory only for as long as
the run's session is open (`Session`). It is never written anywhere and never leaves this PC. A wrong PIN is the
token's to count: we pass on what it says and never try one ourselves.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from asn1crypto import algos, core, x509

from client.hands.certstore import Cert, StoreError, describe

log = logging.getLogger(__name__)

# The driver files of the tokens Indian certifying authorities issue on, as their installers name them.
DRIVERS = ("eps2003csp11v2.dll", "eps2003csp11.dll",       # ePass2003 (HYP2003)
           "SignatureP11.dll", "wdpkcs.dll",               # ProxKey (Watchdata)
           "CryptoIDA_pkcs11.dll",                         # mToken CryptoID
           "eTPKCS11.dll",                                 # SafeNet eToken
           "TRUSTKEYP11_ND_v34.dll",                       # TrustKey
           "aetpkss1.dll")                                 # Gemalto / StarKey

_libs: dict[str, object] = {}                              # a driver is loaded once per process


def drivers() -> list[Path]:
    """The token drivers installed on this PC."""
    root = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    return [root / name for name in DRIVERS if (root / name).is_file()]


def _lib(driver: str):
    import pkcs11
    if driver not in _libs:
        _libs[driver] = pkcs11.lib(driver)
    return _libs[driver]


def _tokens(driver: str) -> list:
    try:
        return [slot.get_token() for slot in _lib(driver).get_slots(token_present=True)]
    except Exception as e:                                   # a driver with no reader, or one that will not load
        log.info("token driver %s: %s", Path(driver).name, e)
        return []


def certificates() -> list[Cert]:
    """The signing certificates on the tokens plugged in now, read without a PIN. `provider` is the driver that
    reached each one."""
    from pkcs11 import Attribute, ObjectClass
    out: dict[str, Cert] = {}
    for driver in map(str, drivers()):
        for token in _tokens(driver):
            try:
                with token.open() as session:
                    for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                        cert = describe(bytes(obj[Attribute.VALUE]), driver)
                        if cert:
                            out.setdefault(cert.thumbprint, cert)
            except Exception as e:
                log.info("reading a token through %s: %s", Path(driver).name, e)
    return sorted(out.values(), key=lambda c: c.expires, reverse=True)


def here(driver: str, thumbprint: str) -> bool:
    """Is the token with this certificate plugged in? Read without a PIN."""
    return any(c.thumbprint == thumbprint.upper() for c in certificates() if c.provider == driver)


class Session:
    """A token opened with its PIN, for one run. `sign` is the token signing; `close` lets it go and forgets the PIN
    (the token's own session held it, not a variable of ours)."""

    def __init__(self, driver: str, thumbprint: str, pin: str):
        from pkcs11 import Attribute, ObjectClass, exceptions
        self.cert = None
        self._session = None
        for token in _tokens(driver):
            try:
                session = token.open(user_pin=pin)
            except exceptions.PinIncorrect as e:
                raise StoreError("wrong_pin", "The token says that PIN is wrong.") from e
            except (exceptions.PinLenRange, exceptions.PinInvalid) as e:
                raise StoreError("wrong_pin", "The token says that PIN is not the right length.") from e
            except exceptions.PinLocked as e:
                raise StoreError("locked", "The token says its PIN is locked.") from e
            except Exception as e:
                log.info("opening a token through %s: %s", Path(driver).name, e)
                continue
            for obj in session.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}):
                der = bytes(obj[Attribute.VALUE])
                if hashlib.sha1(der).hexdigest().upper() == thumbprint.upper():  # noqa: S324 - a certificate's name
                    self.cert, self._id = der, obj[Attribute.ID]
                    break
            if self.cert is not None:
                self._session = session
                self._key = session.get_key(object_class=ObjectClass.PRIVATE_KEY, id=self._id)
                return
            session.close()
        raise StoreError("no_token")

    def sign(self, digest: bytes, algorithm: str = "sha256") -> bytes:
        from pkcs11 import Mechanism
        try:
            if x509.Certificate.load(self.cert).public_key.algorithm != "rsa":
                return self._key.sign(digest, mechanism=Mechanism.ECDSA)
            wrapped = algos.DigestInfo({"digest_algorithm": {"algorithm": algorithm, "parameters": core.Null()},
                                        "digest": digest}).dump()
            return self._key.sign(wrapped, mechanism=Mechanism.RSA_PKCS)
        except Exception as e:
            gone = type(e).__name__ in ("DeviceRemoved", "TokenNotPresent", "SessionHandleInvalid", "SessionClosed")
            raise StoreError("no_token" if gone else "failed", str(e) or type(e).__name__) from e

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:                                # noqa: S110 - a token pulled out has nothing to close
                pass
            self._session = None
