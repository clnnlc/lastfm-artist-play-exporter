import random
from datetime import datetime, timedelta

import pytest

from logic import (
    aggregate_by_artist,
    artist_summary,
    default_export_filename,
    find_source_json,
    generate_export_records,
    load_source_records,
    merge_spotify_histories,
    rebalance_targets,
    synthetic_records,
    write_export_json,
)

SAMPLE_RECORDS = [
    {"ts": "2020-01-01T10:00:00Z", "master_metadata_album_artist_name": "Artist A",
     "master_metadata_track_name": "Song A1", "ms_played": 100000},
    {"ts": "2020-01-02T10:00:00Z", "master_metadata_album_artist_name": "Artist A",
     "master_metadata_track_name": "Song A2", "ms_played": 150000},
    {"ts": "2020-01-03T10:00:00Z", "master_metadata_album_artist_name": "Artist B",
     "master_metadata_track_name": "Song B1", "ms_played": 200000},
]


def test_find_source_json_returns_the_only_json_file(tmp_path):
    json_file = tmp_path / "data.json"
    json_file.write_text("[]", encoding="utf-8")
    (tmp_path / "readme.txt").write_text("hi", encoding="utf-8")
    assert find_source_json(str(tmp_path)) == str(json_file)


def test_find_source_json_raises_when_no_json_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_source_json(str(tmp_path))


def test_find_source_json_raises_when_multiple_json_files(tmp_path):
    (tmp_path / "a.json").write_text("[]", encoding="utf-8")
    (tmp_path / "b.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        find_source_json(str(tmp_path))


def test_find_source_json_ignores_own_export_files(tmp_path):
    source = tmp_path / "streaming_history.json"
    source.write_text("[]", encoding="utf-8")
    (tmp_path / "lastfm_import_20260702_121452.json").write_text(
        "[]", encoding="utf-8")
    assert find_source_json(str(tmp_path)) == str(source)


def test_find_source_json_ignores_config_file(tmp_path):
    source = tmp_path / "streaming_history.json"
    source.write_text("[]", encoding="utf-8")
    (tmp_path / "lastfm_config.json").write_text("{}", encoding="utf-8")
    assert find_source_json(str(tmp_path)) == str(source)


def test_load_source_records_returns_parsed_list(tmp_path):
    json_file = tmp_path / "data.json"
    json_file.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert load_source_records(str(json_file)) == [{"a": 1}, {"a": 2}]


def test_load_source_records_rejects_non_list_json(tmp_path):
    json_file = tmp_path / "data.json"
    json_file.write_text('{"a": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_records(str(json_file))


def test_load_source_records_rejects_list_of_non_dicts(tmp_path):
    json_file = tmp_path / "data.json"
    json_file.write_text('[1, 2, 3]', encoding="utf-8")
    with pytest.raises(ValueError):
        load_source_records(str(json_file))


def test_aggregate_by_artist_groups_records_by_artist_name():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    assert set(grouped.keys()) == {"Artist A", "Artist B"}
    assert len(grouped["Artist A"]) == 2
    assert len(grouped["Artist B"]) == 1


def test_aggregate_by_artist_skips_records_without_artist():
    records = SAMPLE_RECORDS + [
        {"ts": "2020-01-04T10:00:00Z", "master_metadata_album_artist_name": None}]
    grouped = aggregate_by_artist(records)
    assert sum(len(v) for v in grouped.values()) == 3


def test_artist_summary_returns_counts_per_artist():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    summary = artist_summary(grouped)
    as_dict = {row["artist"]: row["real_count"] for row in summary}
    assert as_dict == {"Artist A": 2, "Artist B": 1}


def test_generate_export_records_produces_requested_count_per_artist():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 5}, now, rng=random.Random(42))
    assert len(result) == 5
    assert all(r["master_metadata_album_artist_name"] == "Artist A" for r in result)


def test_generate_export_records_only_uses_records_from_selected_artist():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist B": 10}, now, rng=random.Random(1))
    track_names = {r["master_metadata_track_name"] for r in result}
    assert track_names == {"Song B1"}


def test_generate_export_records_ignores_zero_or_negative_counts():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 0, "Artist B": -3}, now)
    assert result == []


def test_generate_export_records_sorted_chronologically_ascending():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 4, "Artist B": 4}, now, rng=random.Random(7))
    timestamps = [r["ts"] for r in result]
    assert timestamps == sorted(timestamps)


def test_generate_export_records_preserves_source_schema_keys():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 1}, now, rng=random.Random(3))
    assert set(result[0].keys()) == set(SAMPLE_RECORDS[0].keys())


def test_generate_export_records_ignores_unknown_artist():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Unknown Artist": 5}, now)
    assert result == []


def test_generate_export_records_respects_gap_bounds():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(
        grouped, {"Artist A": 10}, now,
        rng=random.Random(5), min_gap_minutes=1, max_gap_minutes=1)
    oldest = min(r["ts"] for r in result)
    assert oldest == "2026-07-02T11:51:00Z"  # now - 9 * 1min


def test_generate_export_records_defaults_fit_scrobble_window():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 500}, now,
                                     rng=random.Random(5))
    oldest = min(r["ts"] for r in result)
    window_start = (now - timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert oldest >= window_start  # Last.fm ignoriert Scrobbles > ~14 Tage


def test_generate_export_records_staggers_artist_chain_starts():
    grouped = aggregate_by_artist(SAMPLE_RECORDS)
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"Artist A": 3, "Artist B": 3},
                                     now, rng=random.Random(2))
    newest = {}
    for r in result:
        artist = r["master_metadata_album_artist_name"]
        newest[artist] = max(newest.get(artist, ""), r["ts"])
    assert newest["Artist A"] != newest["Artist B"]


def test_merge_spotify_histories_concatenates_and_sorts_by_ts(tmp_path):
    f1 = tmp_path / "2020.json"
    f1.write_text('[{"ts": "2020-05-01T00:00:00Z", "x": 1}]', encoding="utf-8")
    f2 = tmp_path / "2019.json"
    f2.write_text('[{"ts": "2019-01-01T00:00:00Z", "x": 2}, '
                  '{"ts": "2019-06-01T00:00:00Z", "x": 3}]', encoding="utf-8")
    merged = merge_spotify_histories([str(f1), str(f2)])
    assert len(merged) == 3
    assert [r["ts"] for r in merged] == [
        "2019-01-01T00:00:00Z", "2019-06-01T00:00:00Z", "2020-05-01T00:00:00Z"]


def test_merge_spotify_histories_rejects_non_list_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"a": 1}', encoding="utf-8")
    with pytest.raises(ValueError):
        merge_spotify_histories([str(bad)])


def test_merge_spotify_histories_empty_paths_returns_empty():
    assert merge_spotify_histories([]) == []


def test_synthetic_records_carry_source_schema_keys():
    records = synthetic_records("New Artist", ["T1", "T2"], album="Alb")
    assert len(records) == 2
    assert all(r["master_metadata_album_artist_name"] == "New Artist"
               for r in records)
    assert {r["master_metadata_track_name"] for r in records} == {"T1", "T2"}
    assert records[0]["master_metadata_album_album_name"] == "Alb"


def test_synthetic_records_skip_empty_track_names():
    records = synthetic_records("A", ["T1", "", None])
    assert [r["master_metadata_track_name"] for r in records] == ["T1"]


def test_synthetic_records_feed_generate_export_for_artist_absent_from_json():
    grouped = {"New Artist": synthetic_records("New Artist", ["T1", "T2"])}
    now = datetime(2026, 7, 2, 12, 0, 0)
    result = generate_export_records(grouped, {"New Artist": 5}, now,
                                     rng=random.Random(1))
    assert len(result) == 5
    assert all(r["master_metadata_album_artist_name"] == "New Artist"
               for r in result)
    assert {r["master_metadata_track_name"] for r in result} <= {"T1", "T2"}


def test_default_export_filename_includes_timestamp():
    now = datetime(2026, 7, 2, 9, 30, 15)
    assert default_export_filename(now) == "lastfm_import_20260702_093015.json"


def test_rebalance_targets_splits_budget_evenly_without_manual():
    result = rebalance_targets(
        {"A": 0, "B": 0, "C": 0}, manual=set(), max_total=500)
    assert result == {"A": 167, "B": 167, "C": 166}


def test_rebalance_targets_keeps_manual_value_and_splits_rest():
    result = rebalance_targets(
        {"A": 300, "B": 0, "C": 0}, manual={"A"}, max_total=500)
    assert result["A"] == 300
    assert result["B"] + result["C"] == 200


def test_rebalance_targets_clamps_pinned_value_to_max_total():
    result = rebalance_targets(
        {"A": 900, "B": 100}, manual={"A", "B"}, max_total=500, pinned="A")
    assert result == {"A": 500, "B": 0}


def test_rebalance_targets_scales_other_manual_values_proportionally():
    result = rebalance_targets(
        {"A": 300, "B": 200, "C": 200}, manual={"A", "B", "C"},
        max_total=500, pinned="A")
    assert result["A"] == 300
    assert result["B"] == 100
    assert result["C"] == 100


def test_rebalance_targets_keeps_manual_values_when_under_budget():
    result = rebalance_targets(
        {"A": 100, "B": 50}, manual={"A", "B"}, max_total=500)
    assert result == {"A": 100, "B": 50}


def test_rebalance_targets_never_exceeds_max_total():
    result = rebalance_targets(
        {"A": 450, "B": 450, "C": 0, "D": 0}, manual={"A", "B"},
        max_total=500, pinned="B")
    assert sum(result.values()) <= 500
    assert result["B"] == 450
    assert result["A"] == 50
    assert result["C"] == 0 and result["D"] == 0


def test_rebalance_targets_empty_input_returns_empty():
    assert rebalance_targets({}, manual=set(), max_total=500) == {}


def test_rebalance_targets_scaled_sum_hits_budget_exactly():
    result = rebalance_targets(
        {"A": 200, "B": 333, "C": 333, "D": 334}, manual={"A", "B", "C", "D"},
        max_total=500, pinned="A")
    assert result["A"] == 200
    assert sum(result.values()) == 500


def test_write_export_json_writes_valid_json_readable_back(tmp_path):
    output_path = tmp_path / "out.json"
    records = [{"ts": "2020-01-01T00:00:00Z", "artist": "X"}]
    write_export_json(records, str(output_path))
    loaded = load_source_records(str(output_path))
    assert loaded == records
