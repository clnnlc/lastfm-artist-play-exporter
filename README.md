# 🎧 Last.fm Artist Play Exporter

A small desktop app that turns your **Spotify listening history** into curated
**Last.fm scrobbles**. Pick artists, decide how many plays each should get, and
either export a ready-to-import JSON file or scrobble straight into your Last.fm
account — all from a clean, dark‑themed GUI.

> Available in **English & German** — switch languages live with the `DE / EN`
> toggle in the top‑right corner.

---

## ✨ Features

- **Artist curation** — every artist from your Spotify history in a searchable,
  sortable table with real play counts.
- **500‑play budget** — selecting artists automatically splits a 500‑play budget
  across them. Pin any artist (📌) to a manual value and the rest rebalances
  around it.
- **Add artists that aren't in your history** — type any artist name and the app
  fetches their top tracks from Last.fm, so you can scrobble artists you never
  streamed on Spotify.
- **Built‑in Spotify converter** — merge Spotify's individual yearly
  `Streaming_History_Audio_*.json` files into one combined history file, right
  from the app.
- **Two output modes**
  - 🚀 **Export** a `lastfm_import_*.json` file, or
  - 📡 **Scrobble** directly to your account via the Last.fm API.
- **Realistic timestamps** — generated plays are spread backwards over the last
  few days with randomized gaps, so they stay inside Last.fm's ~14‑day scrobble
  window.
- **Live language switch** — German / English, remembered between sessions.

---

## 🚀 Getting started

### 1. Get your Spotify data

Request your **Extended streaming history** from
[Spotify Privacy settings](https://www.spotify.com/account/privacy/). You'll
receive several files named like `Streaming_History_Audio_2019-2020_0.json`.

Use the app's **🔄 Merge Spotify JSONs** button to combine them into a single
history file, or drop one already‑merged file next to the app.

> The app expects **exactly one** non‑`lastfm_` JSON file in its folder as the
> source history. The converter produces that file for you.

### 2. Connect Last.fm (only needed for scrobbling / adding artists)

1. Create an API account at [last.fm/api/accounts](https://www.last.fm/api/accounts).
2. In the app, click **📡 Scrobble** (or **➕ Add artist**) and paste your
   **API key** and **Shared secret**.
3. Follow the two‑step browser authorization to grant access.

Your credentials are stored **locally** in `lastfm_config.json` and are never
shared.

### 3. Curate & scrobble

- Click an artist (or its ✓) to select it — the 500‑play budget splits across
  your selection.
- Double‑click or scroll on the **Target** column to set a manual count (📌).
- Hit **🚀 Export** for a JSON file, or **📡 Scrobble** to push to Last.fm.

---

## 🛠️ Running from source

```bash
pip install -r requirements.txt
python app.py
```

Requires **Python 3.12+**.

### Building the Windows executable

```bash
pip install pyinstaller
pyinstaller --noconfirm LastfmArtistPlayExporter.spec
```

The bundled `LastfmArtistPlayExporter.exe` appears in `dist/`.

---

## 🧪 Tests

The data and API logic are fully unit‑tested (pure functions, no network):

```bash
pytest
```

---

## 📁 Project structure

| File              | Purpose                                                        |
| ----------------- | ------------------------------------------------------------- |
| `app.py`          | Tkinter / CustomTkinter GUI                                    |
| `logic.py`        | Pure data logic — aggregation, merging, record generation     |
| `lastfm_api.py`   | Last.fm API — auth flow, scrobbling, top‑tracks lookup         |
| `i18n.py`         | German / English translation table                            |
| `theme.py`        | Colors & styling                                              |
| `test_*.py`       | Unit tests                                                     |

---

## 🔒 Privacy

This repository contains **source code only**. Your listening history,
generated exports, and Last.fm credentials (`lastfm_config.json`) stay on your
machine and are excluded via `.gitignore`.

---

## ⚠️ Disclaimer

Scrobbling fabricated plays is against the spirit of Last.fm's stats. Use this
tool responsibly — for migrating your own genuine listening history from Spotify,
not for gaming charts.
