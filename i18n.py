"""Minimales i18n fuer den Last.fm Artist Play Exporter (Deutsch / Englisch).

Eine flache Schluessel->Sprache-Tabelle; `t(key, **kwargs)` liefert den Text
der aktuell gesetzten Sprache und fuellt optionale Platzhalter via str.format.
"""
from __future__ import annotations

LANGUAGES = ("de", "en")
DEFAULT_LANGUAGE = "de"

_current = DEFAULT_LANGUAGE

TRANSLATIONS: dict[str, dict[str, str]] = {
    # Kopf / Fenster
    "app.subtitle": {
        "de": "Artists auswählen, Play-Zahlen festlegen, als JSON exportieren",
        "en": "Select artists, set play counts, export as JSON",
    },
    # Toolbar
    "search.placeholder": {
        "de": "🔍  Artist suchen ...",
        "en": "🔍  Search artist ...",
    },
    "btn.select_all": {"de": "Alle auswählen", "en": "Select all"},
    "btn.deselect_all": {"de": "Auswahl aufheben", "en": "Deselect all"},
    "btn.redistribute": {"de": "⚖  Neu verteilen", "en": "⚖  Redistribute"},
    "btn.add_artist": {"de": "➕  Artist hinzufügen", "en": "➕  Add artist"},
    "btn.merge": {
        "de": "🔄  Spotify-JSONs zusammenführen",
        "en": "🔄  Merge Spotify JSONs",
    },
    "switch.only_selected": {
        "de": "Nur Ausgewählte anzeigen",
        "en": "Show only selected",
    },
    # Zusammenfassung
    "summary.selected": {
        "de": "{n} / {total} Artists ausgewählt",
        "en": "{n} / {total} artists selected",
    },
    "summary.manual": {"de": "{n} {pin} manuell", "en": "{n} {pin} manual"},
    "summary.visible": {"de": "{n} sichtbar", "en": "{n} visible"},
    # Spalten
    "col.artist": {"de": "Artist", "en": "Artist"},
    "col.real_count": {"de": "Echte Plays", "en": "Real plays"},
    "col.target": {"de": "Zielanzahl", "en": "Target"},
    # Hinweis
    "hint.table": {
        "de": ("💡 Klick auf ✓ oder Artist wählt aus und teilt {max} Plays auf "
               "alle Ausgewählten auf  ·  Doppelklick oder Mausrad (Shift = ±10) "
               "setzt die Zielanzahl manuell ({pin}), der Rest passt sich "
               "automatisch an  ·  Klick auf {pin} löst den Pin  ·  Spaltenkopf "
               "sortiert"),
        "en": ("💡 Click ✓ or an artist to select it and split {max} plays "
               "across all selected  ·  Double-click or scroll wheel (Shift = "
               "±10) sets the target manually ({pin}), the rest adjusts "
               "automatically  ·  Click {pin} to release the pin  ·  Column "
               "header sorts"),
    },
    # Fusszeile
    "status.ready": {"de": "Bereit.", "en": "Ready."},
    "btn.scrobble": {"de": "📡  In Account scrobbeln", "en": "📡  Scrobble to account"},
    "btn.export": {"de": "🚀  Finaldatei exportieren", "en": "🚀  Export final file"},
    # Laden
    "load.error_title": {"de": "Fehler beim Laden", "en": "Load error"},
    "load.no_data": {"de": "Keine Daten geladen.", "en": "No data loaded."},
    "load.summary": {
        "de": "{records} Einträge, {artists} Artists geladen.",
        "en": "{records} entries, {artists} artists loaded.",
    },
    # Setup-Dialog
    "setup.title": {"de": "Mit Last.fm verbinden", "en": "Connect to Last.fm"},
    "setup.info_connect": {
        "de": ("Verbinde dein Last.fm-Konto. Es öffnet sich der Browser zur "
               "Freigabe – danach unten „Autorisierung abgeschlossen“ klicken."),
        "en": ("Connect your Last.fm account. The browser opens for you to "
               "authorize – then click “Authorization complete” below."),
    },
    "setup.connect": {
        "de": "🔗  Mit Last.fm verbinden",
        "en": "🔗  Connect Last.fm",
    },
    "setup.authorized": {
        "de": "✓  Autorisierung abgeschlossen",
        "en": "✓  Authorization complete",
    },
    "setup.info": {
        "de": ("Key und Shared Secret stehen beide auf deiner\n"
               "API-Konto-Seite (Anwendung anklicken)."),
        "en": ("Key and shared secret are both on your\n"
               "API account page (click the application)."),
    },
    "setup.open_accounts": {"de": "🔗 API-Konten öffnen", "en": "🔗 Open API accounts"},
    "setup.api_key": {"de": "API-Key", "en": "API key"},
    "setup.api_secret": {"de": "Shared Secret", "en": "Shared secret"},
    "setup.step1": {
        "de": "1)  Browser öffnen & Zugriff erlauben",
        "en": "1)  Open browser & allow access",
    },
    "setup.step2": {"de": "2)  Anmeldung abschließen", "en": "2)  Complete sign-in"},
    "setup.enter_creds": {
        "de": "Bitte API-Key und Shared Secret eintragen.",
        "en": "Please enter API key and shared secret.",
    },
    "setup.confirm_browser": {
        "de": "Im Browser den Zugriff bestätigen und danach hier Schritt 2 klicken.",
        "en": "Confirm access in the browser, then click step 2 here.",
    },
    "setup.creds_changed": {
        "de": "Zugangsdaten geändert – bitte Schritt 1 erneut ausführen.",
        "en": "Credentials changed – please run step 1 again.",
    },
    # Artist hinzufuegen
    "add.title": {"de": "Artist hinzufügen", "en": "Add artist"},
    "add.info": {
        "de": ("Der Artist muss nicht in der JSON stehen – die\n"
               "Top-Tracks werden von Last.fm geholt und gescrobbelt."),
        "en": ("The artist doesn't need to be in the JSON – the\n"
               "top tracks are fetched from Last.fm and scrobbled."),
    },
    "add.artist_placeholder": {"de": "Artist-Name", "en": "Artist name"},
    "add.count_placeholder": {"de": "Anzahl Plays", "en": "Number of plays"},
    "add.button": {"de": "Hinzufügen", "en": "Add"},
    "add.need_name": {
        "de": "Bitte einen Artist-Namen eintragen.",
        "en": "Please enter an artist name.",
    },
    "add.need_count": {
        "de": "Anzahl muss eine positive Zahl sein.",
        "en": "Count must be a positive number.",
    },
    "add.fetching": {
        "de": "Top-Tracks für „{artist}“ werden geholt ...",
        "en": "Fetching top tracks for “{artist}” ...",
    },
    "add.updated": {
        "de": "„{artist}“ war bereits vorhanden – aktualisiert.",
        "en": "“{artist}” already existed – updated.",
    },
    "add.load_failed": {
        "de": "Artist konnte nicht geladen werden.",
        "en": "Could not load artist.",
    },
    "add.not_found_title": {"de": "Artist nicht gefunden", "en": "Artist not found"},
    "add.not_found_msg": {
        "de": ("Für „{artist}“ wurden auf Last.fm keine Tracks gefunden.\n"
               "Bitte den Namen prüfen."),
        "en": ("No tracks were found for “{artist}” on Last.fm.\n"
               "Please check the name."),
    },
    "add.not_found_status": {"de": "Artist nicht gefunden.", "en": "Artist not found."},
    "add.added": {
        "de": "„{artist}“ hinzugefügt ({n} Top-Tracks).",
        "en": "“{artist}” added ({n} top tracks).",
    },
    "lastfm.error_title": {"de": "Last.fm-Fehler", "en": "Last.fm error"},
    # Export
    "export.no_selection_title": {"de": "Keine Auswahl", "en": "No selection"},
    "export.no_selection_msg": {
        "de": "Bitte mindestens einen Artist mit Zielanzahl > 0 auswählen.",
        "en": "Please select at least one artist with a target > 0.",
    },
    "export.done_status": {
        "de": "Exportiert: {n} Einträge -> {file}",
        "en": "Exported: {n} entries -> {file}",
    },
    "export.done_title": {"de": "Export abgeschlossen", "en": "Export complete"},
    "export.done_msg": {
        "de": "{n} Einträge geschrieben:\n{path}\n\nOrdner jetzt öffnen?",
        "en": "{n} entries written:\n{path}\n\nOpen folder now?",
    },
    # Scrobbeln
    "scrobble.confirm_title": {"de": "Scrobbeln bestätigen", "en": "Confirm scrobbling"},
    "scrobble.confirm_msg": {
        "de": ("{total} Plays von {n} Artists jetzt in {user} scrobbeln?\n\n"
               "Die Plays werden zeitlich über die letzten Tage verteilt."),
        "en": ("Scrobble {total} plays from {n} artists to {user} now?\n\n"
               "The plays are spread across the last few days."),
    },
    "scrobble.default_user": {"de": "deinen Account", "en": "your account"},
    "scrobble.progress": {
        "de": "Scrobble {i} / {total} Batches ...",
        "en": "Scrobbling batch {i} / {total} ...",
    },
    "scrobble.aborted_status": {
        "de": "Scrobbeln abgebrochen: {error}",
        "en": "Scrobbling aborted: {error}",
    },
    "scrobble.failed_title": {"de": "Scrobbeln fehlgeschlagen", "en": "Scrobbling failed"},
    "scrobble.failed_msg": {
        "de": "{error}\n\nBereits übertragen: {n} Plays.",
        "en": "{error}\n\nAlready sent: {n} plays.",
    },
    "scrobble.done_summary": {"de": "{n} Plays gescrobbelt", "en": "{n} plays scrobbled"},
    "scrobble.done_ignored": {
        "de": ", {n} von Last.fm ignoriert",
        "en": ", {n} ignored by Last.fm",
    },
    "scrobble.done_title": {"de": "Scrobbeln abgeschlossen", "en": "Scrobbling complete"},
    # Converter / Zusammenfuehren
    "merge.pick_title": {
        "de": "Spotify-JSON-Dateien auswählen",
        "en": "Select Spotify JSON files",
    },
    "merge.save_title": {
        "de": "Zusammengeführte Datei speichern",
        "en": "Save merged file",
    },
    "merge.error_title": {"de": "Fehler beim Zusammenführen", "en": "Merge error"},
    "merge.done_status": {
        "de": "{n} Einträge aus {files} Dateien zusammengeführt.",
        "en": "Merged {n} entries from {files} files.",
    },
    "merge.done_title": {"de": "Zusammenführen abgeschlossen", "en": "Merge complete"},
    "merge.done_msg": {
        "de": "{n} Einträge aus {files} Dateien geschrieben:\n{path}\n\nJetzt laden?",
        "en": "{n} entries from {files} files written:\n{path}\n\nLoad now?",
    },
}


def set_language(lang: str) -> None:
    global _current
    if lang in LANGUAGES:
        _current = lang


def get_language() -> str:
    return _current


def t(key: str, **kwargs) -> str:
    entry = TRANSLATIONS.get(key)
    if entry is None:
        return key
    text = entry.get(_current) or entry.get(DEFAULT_LANGUAGE) or key
    return text.format(**kwargs) if kwargs else text
