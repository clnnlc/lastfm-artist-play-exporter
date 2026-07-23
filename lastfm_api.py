"""Last.fm-API-Anbindung: Auth-Flow und Scrobbeln (nur Standardbibliothek)."""
from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from calendar import timegm
from datetime import datetime

API_URL = "https://ws.audioscrobbler.com/2.0/"
AUTH_URL = "https://www.last.fm/api/auth"
SCROBBLE_BATCH_SIZE = 50
CONFIG_FILENAME = "lastfm_config.json"
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class LastfmError(Exception):
    """Fehlerantwort der Last.fm-API."""


# --------------------------------------------------------------------- #
# Reine Hilfsfunktionen
# --------------------------------------------------------------------- #
def api_signature(params: dict[str, str], secret: str) -> str:
    """MD5-Signatur nach Last.fm-Spezifikation (format/callback ausgenommen)."""
    raw = "".join(k + str(params[k]) for k in sorted(params)
                  if k not in ("format", "callback"))
    return hashlib.md5((raw + secret).encode("utf-8")).hexdigest()


def ts_to_unix(ts: str) -> int:
    """ISO-Zeitstempel (UTC, z.B. aus dem Export) -> Unix-Timestamp."""
    return timegm(datetime.strptime(ts, TS_FORMAT).timetuple())


def record_to_scrobble(record: dict) -> dict:
    scrobble = {
        "artist": record["master_metadata_album_artist_name"],
        "track": record["master_metadata_track_name"],
        "timestamp": ts_to_unix(record["ts"]),
    }
    album = record.get("master_metadata_album_album_name")
    if album:
        scrobble["album"] = album
    return scrobble


def chunked(items: list, size: int = SCROBBLE_BATCH_SIZE) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_scrobble_params(
    scrobbles: list[dict],
    api_key: str,
    session_key: str,
    secret: str,
) -> dict[str, str]:
    """Baut die signierten POST-Parameter fuer einen track.scrobble-Batch."""
    params = {"method": "track.scrobble", "api_key": api_key,
              "sk": session_key}
    for i, s in enumerate(scrobbles):
        params[f"artist[{i}]"] = s["artist"]
        params[f"track[{i}]"] = s["track"]
        params[f"timestamp[{i}]"] = str(s["timestamp"])
        if s.get("album"):
            params[f"album[{i}]"] = s["album"]
    params["api_sig"] = api_signature(params, secret)
    params["format"] = "json"
    return params


def auth_url(api_key: str, token: str) -> str:
    return f"{AUTH_URL}?api_key={api_key}&token={token}"


# --------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------- #
def load_config(path: str) -> dict:
    """Laedt die Konfiguration; fehlende oder defekte Dateien zaehlen als leer."""
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, ValueError):
        return {}
    return config if isinstance(config, dict) else {}


def save_config(config: dict, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------- #
# API-Aufrufe (Netzwerk)
# --------------------------------------------------------------------- #
def _call(params: dict[str, str], timeout: int = 15) -> dict:
    data = urllib.parse.urlencode(params).encode("utf-8")
    request = urllib.request.Request(API_URL, data=data, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        try:
            payload = json.loads(err.read().decode("utf-8"))
        except (ValueError, OSError):
            payload = None
        if not isinstance(payload, dict) or "error" not in payload:
            raise LastfmError(f"HTTP {err.code}: {err.reason}") from err
    except OSError as err:
        raise LastfmError(f"Netzwerkfehler: {err}") from err
    else:
        try:
            payload = json.loads(body)
        except ValueError as err:
            raise LastfmError(
                "Ungueltige Antwort von Last.fm (kein JSON).") from err
    if isinstance(payload, dict) and "error" in payload:
        raise LastfmError(
            f"Last.fm-Fehler {payload['error']}: "
            f"{payload.get('message', 'unbekannt')}")
    return payload


def get_token(api_key: str, secret: str) -> str:
    params = {"method": "auth.getToken", "api_key": api_key}
    params["api_sig"] = api_signature(params, secret)
    params["format"] = "json"
    return _call(params)["token"]


def get_artist_top_tracks(
    artist: str,
    api_key: str,
    limit: int = 50,
) -> list[str]:
    """Holt die Top-Tracks eines Artists (artist.getTopTracks).

    Reine Lesemethode -> weder Signatur noch Session noetig. Rueckgabe:
    Track-Namen (beliebteste zuerst); leere Liste, wenn der Artist auf
    Last.fm unbekannt ist.
    """
    params = {"method": "artist.getTopTracks", "artist": artist,
              "api_key": api_key, "autocorrect": "1", "limit": str(limit),
              "format": "json"}
    payload = _call(params)
    tracks = payload.get("toptracks", {}).get("track", [])
    if isinstance(tracks, dict):  # ein einzelnes Ergebnis kommt nicht als Liste
        tracks = [tracks]
    return [t["name"] for t in tracks if isinstance(t, dict) and t.get("name")]


def get_session(api_key: str, secret: str, token: str) -> dict:
    """Tauscht den bestaetigten Token gegen einen Session-Key.

    Rueckgabe: {"name": <username>, "key": <session_key>}
    """
    params = {"method": "auth.getSession", "api_key": api_key,
              "token": token}
    params["api_sig"] = api_signature(params, secret)
    params["format"] = "json"
    return _call(params)["session"]


def scrobble_batch(
    scrobbles: list[dict],
    api_key: str,
    secret: str,
    session_key: str,
) -> tuple[int, int]:
    """Sendet einen Batch (max. 50). Rueckgabe: (akzeptiert, ignoriert)."""
    params = build_scrobble_params(scrobbles, api_key, session_key, secret)
    payload = _call(params)
    attr = payload.get("scrobbles", {}).get("@attr", {})
    return int(attr.get("accepted", 0)), int(attr.get("ignored", 0))
