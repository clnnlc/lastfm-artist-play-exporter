import json
import sys

import pytest

import credentials


# --------------------------------------------------------------------- #
# app_credentials
# --------------------------------------------------------------------- #
def test_app_credentials_env_wins(monkeypatch):
    monkeypatch.setenv("LASTFM_API_KEY", "envkey")
    monkeypatch.setenv("LASTFM_API_SECRET", "envsecret")
    assert credentials.app_credentials() == ("envkey", "envsecret")


def test_app_credentials_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.delenv("LASTFM_API_SECRET", raising=False)
    f = tmp_path / "app_credentials.json"
    f.write_text(json.dumps({"api_key": "fk", "api_secret": "fs"}),
                 encoding="utf-8")
    monkeypatch.setattr(credentials, "_resource_path", lambda name: str(f))
    assert credentials.app_credentials() == ("fk", "fs")


def test_app_credentials_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    monkeypatch.delenv("LASTFM_API_SECRET", raising=False)
    monkeypatch.setattr(credentials, "_resource_path",
                        lambda name: str(tmp_path / "missing.json"))
    assert credentials.app_credentials() is None


# --------------------------------------------------------------------- #
# session storage (identity cipher seam)
# --------------------------------------------------------------------- #
def _identity(data):
    return data


def test_session_round_trip(tmp_path):
    credentials.save_session(str(tmp_path), "sk", "alice", protect=_identity)
    assert credentials.load_session(str(tmp_path), unprotect=_identity) == {
        "session_key": "sk", "username": "alice"}


def test_session_round_trip_with_api_creds(tmp_path):
    credentials.save_session(str(tmp_path), "sk", "alice",
                             api_key="k", api_secret="s", protect=_identity)
    assert credentials.load_session(str(tmp_path), unprotect=_identity) == {
        "session_key": "sk", "username": "alice",
        "api_key": "k", "api_secret": "s"}


def test_load_missing_returns_none(tmp_path):
    assert credentials.load_session(str(tmp_path), unprotect=_identity) is None


def test_load_corrupt_returns_none(tmp_path):
    (tmp_path / credentials.SESSION_FILENAME).write_bytes(b"not-json")
    assert credentials.load_session(str(tmp_path), unprotect=_identity) is None


def test_clear_session(tmp_path):
    credentials.save_session(str(tmp_path), "sk", "alice", protect=_identity)
    credentials.clear_session(str(tmp_path))
    assert credentials.load_session(str(tmp_path), unprotect=_identity) is None


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_dpapi_round_trip():
    blob = credentials._dpapi_protect(b"secret-bytes")
    assert blob != b"secret-bytes"
    assert credentials._dpapi_unprotect(blob) == b"secret-bytes"


# --------------------------------------------------------------------- #
# resolve_credentials
# --------------------------------------------------------------------- #
def test_resolve_uses_app_creds():
    assert credentials.resolve_credentials(
        ("ak", "as"), {"session_key": "sk", "username": "u"}) == {
        "api_key": "ak", "api_secret": "as",
        "session_key": "sk", "username": "u"}


def test_resolve_prefers_stored_api_creds():
    r = credentials.resolve_credentials(
        ("ak", "as"),
        {"session_key": "sk", "username": "u",
         "api_key": "bk", "api_secret": "bs"})
    assert r["api_key"] == "bk" and r["api_secret"] == "bs"


def test_resolve_none_without_session():
    assert credentials.resolve_credentials(("ak", "as"), None) is None
    assert credentials.resolve_credentials(("ak", "as"), {"username": "u"}) is None


def test_resolve_none_without_any_creds():
    assert credentials.resolve_credentials(None, {"session_key": "sk"}) is None
