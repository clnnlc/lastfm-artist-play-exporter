"""Secret boundary: application key resolution and per-user session storage.

No GUI, no network. Application credentials come from the environment or a
bundled file; the per-user session key is stored encrypted (Windows DPAPI).
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from ctypes import wintypes

APP_CREDENTIALS_FILENAME = "app_credentials.json"
SESSION_FILENAME = "lastfm_session.dat"

_CRYPTPROTECT_UI_FORBIDDEN = 0x01


# --------------------------------------------------------------------- #
# Application credentials (api_key / api_secret)
# --------------------------------------------------------------------- #
def _resource_path(name: str) -> str:
    """Path to a bundled resource, working both frozen and from source."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), name)


def app_credentials() -> tuple[str, str] | None:
    """(api_key, api_secret) from env, then bundled file, else None."""
    key = os.environ.get("LASTFM_API_KEY")
    secret = os.environ.get("LASTFM_API_SECRET")
    if key and secret:
        return key, secret
    try:
        with open(_resource_path(APP_CREDENTIALS_FILENAME),
                  encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    key, secret = data.get("api_key"), data.get("api_secret")
    if key and secret:
        return key, secret
    return None


# --------------------------------------------------------------------- #
# Windows DPAPI backend
# --------------------------------------------------------------------- #
class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob_in(data: bytes) -> _DataBlob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _blob_bytes(blob: _DataBlob) -> bytes:
    out = ctypes.create_string_buffer(blob.cbData)
    ctypes.memmove(out, blob.pbData, blob.cbData)
    return out.raw


def _dpapi_protect(data: bytes) -> bytes:
    out = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(_blob_in(data)), None, None, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("CryptProtectData failed")
    try:
        return _blob_bytes(out)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    out = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(_blob_in(data)), None, None, None, None,
            _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return _blob_bytes(out)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


# --------------------------------------------------------------------- #
# Per-user session storage
# --------------------------------------------------------------------- #
def _session_path(base_dir: str) -> str:
    return os.path.join(base_dir, SESSION_FILENAME)


def save_session(base_dir: str, session_key: str, username: str,
                 api_key: str | None = None, api_secret: str | None = None,
                 protect=None) -> None:
    """Encrypt and store the session (and optional BYO api creds)."""
    protect = protect or _dpapi_protect
    blob = {"session_key": session_key, "username": username}
    if api_key and api_secret:
        blob["api_key"] = api_key
        blob["api_secret"] = api_secret
    raw = json.dumps(blob).encode("utf-8")
    with open(_session_path(base_dir), "wb") as f:
        f.write(protect(raw))


def load_session(base_dir: str, unprotect=None) -> dict | None:
    """Decrypt the stored session; missing/corrupt/foreign-user -> None."""
    unprotect = unprotect or _dpapi_unprotect
    try:
        with open(_session_path(base_dir), "rb") as f:
            raw = unprotect(f.read())
        blob = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(blob, dict) or not blob.get("session_key"):
        return None
    return blob


def clear_session(base_dir: str) -> None:
    try:
        os.remove(_session_path(base_dir))
    except OSError:
        pass


# --------------------------------------------------------------------- #
# Effective credential resolution
# --------------------------------------------------------------------- #
def resolve_credentials(app_creds, stored):
    """Combine the app key with a stored session into ready-to-use creds.

    Stored api_key/api_secret (bring-your-own path) take precedence over the
    bundled app_creds. Returns None unless a session_key is present.
    """
    if stored and stored.get("api_key") and stored.get("api_secret"):
        api_key, api_secret = stored["api_key"], stored["api_secret"]
    elif app_creds:
        api_key, api_secret = app_creds
    else:
        return None
    if not (stored and stored.get("session_key")):
        return None
    return {"api_key": api_key, "api_secret": api_secret,
            "session_key": stored["session_key"],
            "username": stored.get("username", "")}
