import hashlib
import io
import urllib.error

import pytest

import lastfm_api
from lastfm_api import (
    LastfmError,
    api_signature,
    auth_url,
    build_scrobble_params,
    chunked,
    load_config,
    record_to_scrobble,
    save_config,
    ts_to_unix,
)

SAMPLE_RECORD = {
    "ts": "2026-07-01T10:00:00Z",
    "master_metadata_album_artist_name": "Artist A",
    "master_metadata_track_name": "Song A1",
    "master_metadata_album_album_name": "Album A",
    "ms_played": 100000,
}


def test_api_signature_concatenates_sorted_params_plus_secret():
    params = {"method": "auth.getToken", "api_key": "abc"}
    expected = hashlib.md5(
        "api_keyabcmethodauth.getTokensec".encode("utf-8")).hexdigest()
    assert api_signature(params, "sec") == expected


def test_api_signature_excludes_format_and_callback():
    base = {"method": "x", "api_key": "k"}
    with_format = dict(base, format="json", callback="cb")
    assert api_signature(with_format, "s") == api_signature(base, "s")


def test_ts_to_unix_treats_timestamp_as_utc():
    assert ts_to_unix("1970-01-01T00:00:00Z") == 0
    assert ts_to_unix("1970-01-02T00:00:00Z") == 86400


def test_record_to_scrobble_maps_fields():
    scrobble = record_to_scrobble(SAMPLE_RECORD)
    assert scrobble == {
        "artist": "Artist A",
        "track": "Song A1",
        "album": "Album A",
        "timestamp": ts_to_unix("2026-07-01T10:00:00Z"),
    }


def test_record_to_scrobble_omits_missing_album():
    record = dict(SAMPLE_RECORD, master_metadata_album_album_name=None)
    scrobble = record_to_scrobble(record)
    assert "album" not in scrobble


def test_chunked_splits_into_batches():
    assert chunked(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]
    assert chunked([], 3) == []


def test_build_scrobble_params_indexes_each_scrobble():
    scrobbles = [
        {"artist": "A", "track": "T1", "album": "X", "timestamp": 100},
        {"artist": "B", "track": "T2", "timestamp": 200},
    ]
    params = build_scrobble_params(scrobbles, api_key="k", session_key="sk",
                                   secret="sec")
    assert params["method"] == "track.scrobble"
    assert params["api_key"] == "k"
    assert params["sk"] == "sk"
    assert params["artist[0]"] == "A" and params["artist[1]"] == "B"
    assert params["track[0]"] == "T1" and params["track[1]"] == "T2"
    assert params["timestamp[0]"] == "100" and params["timestamp[1]"] == "200"
    assert params["album[0]"] == "X"
    assert "album[1]" not in params
    assert params["format"] == "json"
    unsigned = {k: v for k, v in params.items()
                if k not in ("api_sig", "format")}
    assert params["api_sig"] == api_signature(unsigned, "sec")


def test_auth_url_contains_key_and_token():
    url = auth_url("mykey", "mytoken")
    assert "api_key=mykey" in url and "token=mytoken" in url
    assert url.startswith("https://www.last.fm/api/auth")


def test_config_roundtrip(tmp_path):
    path = str(tmp_path / "lastfm_config.json")
    config = {"api_key": "k", "api_secret": "s", "session_key": "sk",
              "username": "user"}
    save_config(config, path)
    assert load_config(path) == config


def test_load_config_returns_empty_dict_when_missing(tmp_path):
    assert load_config(str(tmp_path / "nope.json")) == {}


def test_load_config_returns_empty_dict_when_corrupt(tmp_path):
    path = tmp_path / "lastfm_config.json"
    path.write_text('{"api_key": "k"', encoding="utf-8")  # abgeschnitten
    assert load_config(str(path)) == {}


def test_load_config_returns_empty_dict_for_non_dict_json(tmp_path):
    path = tmp_path / "lastfm_config.json"
    path.write_text('[1, 2]', encoding="utf-8")
    assert load_config(str(path)) == {}


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_get_artist_top_tracks_returns_names(monkeypatch):
    payload = {"toptracks": {"track": [{"name": "T1"}, {"name": "T2"}]}}
    monkeypatch.setattr(lastfm_api, "_call", lambda params, **k: payload)
    assert lastfm_api.get_artist_top_tracks("Artist", "key") == ["T1", "T2"]


def test_get_artist_top_tracks_handles_single_track_dict(monkeypatch):
    payload = {"toptracks": {"track": {"name": "Only"}}}
    monkeypatch.setattr(lastfm_api, "_call", lambda params, **k: payload)
    assert lastfm_api.get_artist_top_tracks("Artist", "key") == ["Only"]


def test_get_artist_top_tracks_returns_empty_for_unknown_artist(monkeypatch):
    monkeypatch.setattr(lastfm_api, "_call",
                        lambda params, **k: {"toptracks": {"track": []}})
    assert lastfm_api.get_artist_top_tracks("Nope", "key") == []


def test_get_artist_top_tracks_sends_expected_params(monkeypatch):
    captured = {}

    def fake_call(params, **k):
        captured.update(params)
        return {"toptracks": {"track": []}}

    monkeypatch.setattr(lastfm_api, "_call", fake_call)
    lastfm_api.get_artist_top_tracks("My Artist", "mykey", limit=10)
    assert captured["method"] == "artist.getTopTracks"
    assert captured["artist"] == "My Artist"
    assert captured["api_key"] == "mykey"
    assert captured["limit"] == "10"


def test_call_raises_lastfm_error_on_non_json_success_body(monkeypatch):
    monkeypatch.setattr(lastfm_api.urllib.request, "urlopen",
                        lambda *a, **k: _FakeResponse(b"<html>wartung</html>"))
    with pytest.raises(LastfmError):
        lastfm_api._call({"method": "x"})


def test_call_raises_lastfm_error_on_http_error_without_error_key(monkeypatch):
    def raise_http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://ws.audioscrobbler.com/2.0/", 502, "Bad Gateway", None,
            io.BytesIO(b'{"message": "down"}'))

    monkeypatch.setattr(lastfm_api.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(LastfmError, match="502"):
        lastfm_api._call({"method": "x"})


def test_call_uses_lastfm_error_payload_from_http_error(monkeypatch):
    def raise_http_error(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://ws.audioscrobbler.com/2.0/", 403, "Forbidden", None,
            io.BytesIO(b'{"error": 9, "message": "Invalid session key"}'))

    monkeypatch.setattr(lastfm_api.urllib.request, "urlopen", raise_http_error)
    with pytest.raises(LastfmError, match="Invalid session key"):
        lastfm_api._call({"method": "x"})
