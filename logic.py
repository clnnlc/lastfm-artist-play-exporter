"""Reine Datenlogik fuer den Last.fm Artist Play Exporter."""
from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from datetime import datetime, timedelta

# Last.fm akzeptiert nur Scrobbles aus den letzten ~14 Tagen: enge Abstaende,
# damit auch 500 Plays sicher im Fenster liegen (500 * 25min ~ 8,7 Tage).
MIN_GAP_MINUTES = 2
MAX_GAP_MINUTES = 25


def find_source_json(folder: str) -> str:
    """Findet die einzige Quell-JSON-Datei in `folder`.

    Eigene Dateien der App (lastfm_import_*.json, lastfm_config.json)
    werden ignoriert.
    Wirft FileNotFoundError wenn keine, ValueError wenn mehrere existieren.
    """
    candidates = sorted(
        f for f in os.listdir(folder)
        if f.lower().endswith(".json")
        and not f.lower().startswith("lastfm_"))
    if not candidates:
        raise FileNotFoundError(f"Keine JSON-Datei in {folder} gefunden.")
    if len(candidates) > 1:
        raise ValueError(f"Mehrere JSON-Dateien gefunden: {', '.join(candidates)}")
    return os.path.join(folder, candidates[0])


def load_source_records(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ValueError(
            f"{os.path.basename(path)} ist keine Spotify-History "
            "(Liste von Eintraegen erwartet).")
    return data


def merge_spotify_histories(paths: list[str]) -> list[dict]:
    """Fuehrt mehrere Spotify-History-JSONs zu einer einzigen, chronologisch
    sortierten Liste zusammen.

    Spotify exportiert die erweiterte Streaming-History als mehrere Dateien
    (pro Jahr / je ~10 000 Eintraege). Jede Datei muss eine Liste von
    dict-Eintraegen sein (wird von `load_source_records` geprueft).
    """
    merged: list[dict] = []
    for path in paths:
        merged.extend(load_source_records(path))
    merged.sort(key=lambda r: r.get("ts") or "")
    return merged


def aggregate_by_artist(records: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        artist = record.get("master_metadata_album_artist_name")
        if artist:
            grouped[artist].append(record)
    return dict(grouped)


def artist_summary(grouped: dict[str, list[dict]]) -> list[dict]:
    return [{"artist": artist, "real_count": len(recs)}
            for artist, recs in grouped.items()]


def synthetic_records(
    artist: str,
    track_names: list[str],
    album: str | None = None,
) -> list[dict]:
    """Baut history-artige Eintraege fuer einen Artist, der nicht in der
    Spotify-History steht (z.B. Tracks aus artist.getTopTracks).

    Die Eintraege tragen dieselben Schluessel wie echte History-Eintraege,
    damit `generate_export_records` und `record_to_scrobble` sie unveraendert
    verarbeiten. `ts` wird spaeter von `generate_export_records` gesetzt.
    """
    records: list[dict] = []
    for name in track_names:
        if not name:
            continue
        records.append({
            "ts": "",
            "master_metadata_album_artist_name": artist,
            "master_metadata_track_name": name,
            "master_metadata_album_album_name": album,
            "ms_played": 0,
        })
    return records


def generate_export_records(
    grouped: dict[str, list[dict]],
    selections: dict[str, int],
    now: datetime,
    rng: random.Random | None = None,
    min_gap_minutes: int = MIN_GAP_MINUTES,
    max_gap_minutes: int = MAX_GAP_MINUTES,
) -> list[dict]:
    """Erzeugt Eintraege pro Artist, rueckwaerts ab `now` mit zufaelligen
    Abstaenden zwischen `min_gap_minutes` und `max_gap_minutes`.

    `now` muss UTC sein (die ts-Werte werden mit "Z" markiert)."""
    rng = rng or random.Random()
    generated: list[dict] = []
    started = False
    for artist, target_count in selections.items():
        if target_count <= 0:
            continue
        source_records = grouped.get(artist)
        if not source_records:
            continue
        current_ts = now
        # Ketten weiterer Artists versetzt starten, sonst teilen alle
        # Artists denselben neuesten Zeitstempel.
        if started:
            current_ts -= timedelta(
                minutes=rng.randint(min_gap_minutes, max_gap_minutes))
        started = True
        for _ in range(target_count):
            template = rng.choice(source_records)
            entry = dict(template)
            entry["ts"] = current_ts.strftime("%Y-%m-%dT%H:%M:%SZ")
            generated.append(entry)
            current_ts -= timedelta(
                minutes=rng.randint(min_gap_minutes, max_gap_minutes))
    generated.sort(key=lambda r: r["ts"])
    return generated


def rebalance_targets(
    targets: dict[str, int],
    manual: set[str],
    max_total: int,
    pinned: str | None = None,
) -> dict[str, int]:
    """Passt die Zielwerte so an, dass ihre Summe `max_total` nie uebersteigt.

    - `pinned` (der zuletzt manuell bearbeitete Artist) behaelt seinen Wert,
      hoechstens jedoch `max_total`.
    - Uebrige manuelle Werte bleiben erhalten; reicht das Budget nicht,
      werden sie proportional verkleinert (Summe trifft das Budget exakt).
    - Nicht-manuelle Artists teilen sich das Restbudget gleichmaessig.
    """
    if not targets:
        return {}
    order = list(targets)
    result: dict[str, int] = {}
    budget = max_total

    if pinned is not None and pinned in targets:
        pinned_value = min(max(0, targets[pinned]), max_total)
        result[pinned] = pinned_value
        budget -= pinned_value

    other_manual = [a for a in order if a in manual and a != pinned]
    manual_sum = sum(max(0, targets[a]) for a in other_manual)
    if manual_sum <= budget:
        for artist in other_manual:
            result[artist] = max(0, targets[artist])
        budget -= manual_sum
    else:
        shares = [(a, max(0, targets[a]) * budget / manual_sum)
                  for a in other_manual]
        scaled = {a: int(share) for a, share in shares}
        leftover = budget - sum(scaled.values())
        by_fraction = sorted(shares, key=lambda t: t[1] - int(t[1]),
                             reverse=True)
        for artist, _ in by_fraction[:leftover]:
            scaled[artist] += 1
        result.update(scaled)
        budget = 0

    autos = [a for a in order if a not in result]
    if autos:
        base, remainder = divmod(budget, len(autos))
        for i, artist in enumerate(autos):
            result[artist] = base + (1 if i < remainder else 0)
    return {artist: result[artist] for artist in order}


def default_export_filename(now: datetime) -> str:
    return f"lastfm_import_{now.strftime('%Y%m%d_%H%M%S')}.json"


def write_export_json(records: list[dict], output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
