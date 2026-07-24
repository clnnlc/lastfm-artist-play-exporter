"""GUI zum Kuratieren von Last.fm-Import-Play-Zahlen aus Spotify-History."""
from __future__ import annotations

import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta, timezone
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

import credentials
import i18n
import lastfm_api
import theme
from i18n import t
from logic import (
    aggregate_by_artist,
    default_export_filename,
    find_source_json,
    generate_export_records,
    load_source_records,
    merge_spotify_histories,
    rebalance_targets,
    synthetic_records,
    write_export_json,
)

theme.apply()

CHECKED = "☑"
UNCHECKED = "☐"
ARROW_ASC = " ▲"
ARROW_DESC = " ▼"
MAX_TOTAL_PLAYS = 500
PIN = "📌"


def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _font(size: int, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


class ScrobbleSetupDialog(ctk.CTkToplevel):
    """Last.fm-Verknuepfung. Mit mitgeliefertem App-Key nur Browser-Freigabe;
    ohne (Source-Build) Fallback mit eigenem Key/Secret."""

    def __init__(self, master: ctk.CTk, app_creds: tuple[str, str] | None,
                 base_dir: str) -> None:
        super().__init__(master)
        self.title(t("setup.title"))
        self.geometry("520x360")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(master)
        self.after(250, self._safe_grab)

        self.app_creds = app_creds
        self.base_dir = base_dir
        self.result: dict | None = None
        self._token: str | None = None
        self._token_creds: tuple[str, str] | None = None
        self.key_entry: ctk.CTkEntry | None = None
        self.secret_entry: ctk.CTkEntry | None = None

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t("setup.title"),
                     font=_font(18, "bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 2))

        info_key = "setup.info_connect" if app_creds else "setup.info"
        ctk.CTkLabel(self, text=t(info_key), justify="left", font=_font(12),
                     text_color=theme.TEXT_MUTED, wraplength=460).grid(
            row=1, column=0, sticky="w", padx=24, pady=(0, 12))

        row = 2
        if app_creds is None:
            acct = ctk.CTkFrame(self, fg_color="transparent")
            acct.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 8))
            acct.grid_columnconfigure(0, weight=1)
            ctk.CTkButton(acct, text=t("setup.open_accounts"), height=30,
                          width=150, font=_font(12), fg_color=theme.SURFACE_2,
                          hover_color=theme.BORDER, text_color=theme.TEXT,
                          command=lambda: webbrowser.open(
                              "https://www.last.fm/api/accounts")
                          ).grid(row=0, column=1)
            row += 1
            self.key_entry = ctk.CTkEntry(self, height=38,
                                          placeholder_text=t("setup.api_key"))
            self.key_entry.grid(row=row, column=0, sticky="ew", padx=24,
                                pady=(0, 8))
            row += 1
            self.secret_entry = ctk.CTkEntry(
                self, height=38, placeholder_text=t("setup.api_secret"))
            self.secret_entry.grid(row=row, column=0, sticky="ew", padx=24,
                                   pady=(0, 14))
            row += 1

        self.step1_btn = ctk.CTkButton(
            self, text=t("setup.connect") if app_creds else t("setup.step1"),
            height=40, command=self._start_auth)
        self.step1_btn.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 8))
        row += 1

        self.step2_btn = ctk.CTkButton(
            self, text=t("setup.authorized") if app_creds else t("setup.step2"),
            height=40, state="disabled", fg_color=theme.SURFACE_2,
            hover_color=theme.BORDER, text_color=theme.TEXT,
            command=self._finish_auth)
        self.step2_btn.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 10))
        row += 1

        self.status = ctk.CTkLabel(self, text="", font=_font(12),
                                   wraplength=460, justify="left",
                                   text_color=theme.TEXT_MUTED)
        self.status.grid(row=row, column=0, sticky="ew", padx=24, pady=(0, 16))

    def _safe_grab(self) -> None:
        # CTkToplevel ist direkt nach dem Erstellen kurz unsichtbar;
        # grab_set schlaegt auf unsichtbaren Fenstern fehl.
        try:
            self.grab_set()
        except tk.TclError:
            self.after(250, self._safe_grab)

    def _credentials(self) -> tuple[str, str] | None:
        if self.app_creds:
            return self.app_creds
        key = self.key_entry.get().strip()
        secret = self.secret_entry.get().strip()
        if not key or not secret:
            self.status.configure(text=t("setup.enter_creds"),
                                  text_color=theme.ERROR)
            return None
        return key, secret

    def _start_auth(self) -> None:
        creds = self._credentials()
        if not creds:
            return
        key, secret = creds
        try:
            self._token = lastfm_api.get_token(key, secret)
        except lastfm_api.LastfmError as err:
            self.status.configure(text=str(err), text_color=theme.ERROR)
            return
        self._token_creds = creds
        webbrowser.open(lastfm_api.auth_url(key, self._token))
        self.step2_btn.configure(state="normal", fg_color=theme.ACCENT,
                                 hover_color=theme.ACCENT_HOVER,
                                 text_color="#ffffff")
        self.status.configure(text=t("setup.confirm_browser"),
                              text_color=theme.WARNING)

    def _finish_auth(self) -> None:
        creds = self._credentials()
        if not creds or not self._token:
            return
        if creds != self._token_creds:
            # Der Token gehoert zu den Schritt-1-Zugangsdaten und ist mit
            # geaenderten Daten wertlos.
            self._token = None
            self.step2_btn.configure(state="disabled",
                                     fg_color=theme.SURFACE_2,
                                     hover_color=theme.BORDER,
                                     text_color=theme.TEXT)
            self.status.configure(text=t("setup.creds_changed"),
                                  text_color=theme.WARNING)
            return
        key, secret = creds
        try:
            session = lastfm_api.get_session(key, secret, self._token)
        except lastfm_api.LastfmError as err:
            self.status.configure(text=str(err), text_color=theme.ERROR)
            return
        # Nur der selbst eingegebene Key/Secret wird mitverschluesselt;
        # ein mitgelieferter App-Key kommt beim Start aus dem Bundle.
        store_key = None if self.app_creds else key
        store_secret = None if self.app_creds else secret
        credentials.save_session(self.base_dir, session["key"],
                                 session.get("name", ""),
                                 api_key=store_key, api_secret=store_secret)
        self.result = {"api_key": key, "api_secret": secret,
                       "session_key": session["key"],
                       "username": session.get("name", "")}
        self.destroy()


class AddArtistDialog(ctk.CTkToplevel):
    """Fragt Artist-Name und gewuenschte Play-Zahl ab (auch fuer Artists,
    die nicht in der JSON stehen)."""

    def __init__(self, master: ctk.CTk, default_count: int) -> None:
        super().__init__(master)
        self.title(t("add.title"))
        self.geometry("440x300")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.transient(master)
        self.after(250, self._safe_grab)

        self.result: dict | None = None
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=t("add.title"),
                     font=_font(18, "bold")).grid(
            row=0, column=0, sticky="w", padx=24, pady=(20, 2))
        ctk.CTkLabel(self, text=t("add.info"),
                     justify="left", font=_font(12),
                     text_color=theme.TEXT_MUTED).grid(
            row=1, column=0, sticky="w", padx=24, pady=(0, 12))

        self.artist_entry = ctk.CTkEntry(
            self, height=38, placeholder_text=t("add.artist_placeholder"))
        self.artist_entry.grid(row=2, column=0, sticky="ew", padx=24,
                               pady=(0, 8))
        self.count_entry = ctk.CTkEntry(
            self, height=38, placeholder_text=t("add.count_placeholder"))
        self.count_entry.grid(row=3, column=0, sticky="ew", padx=24,
                              pady=(0, 12))
        self.count_entry.insert(0, str(default_count))

        ctk.CTkButton(self, text=t("add.button"), height=40,
                      command=self._confirm).grid(
            row=4, column=0, sticky="ew", padx=24, pady=(0, 8))

        self.status = ctk.CTkLabel(self, text="", font=_font(12),
                                   wraplength=380, justify="left",
                                   text_color=theme.ERROR)
        self.status.grid(row=5, column=0, sticky="ew", padx=24, pady=(0, 12))

        self.artist_entry.focus_set()
        self.bind("<Return>", lambda *_: self._confirm())

    def _safe_grab(self) -> None:
        try:
            self.grab_set()
        except tk.TclError:
            self.after(250, self._safe_grab)

    def _confirm(self) -> None:
        artist = self.artist_entry.get().strip()
        if not artist:
            self.status.configure(text=t("add.need_name"))
            return
        try:
            count = int(self.count_entry.get().strip())
            if count <= 0:
                raise ValueError
        except ValueError:
            self.status.configure(text=t("add.need_count"))
            return
        self.result = {"artist": artist, "count": count}
        self.destroy()


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Last.fm Artist Play Exporter")
        self.geometry("960x720")
        self.minsize(780, 560)
        self.configure(fg_color=theme.BG)

        self.folder = app_base_dir()
        self.grouped: dict[str, list[dict]] = {}
        # Manuell hinzugefuegte Artists (nicht in der JSON): Name -> Top-Track-
        # Eintraege, die von Last.fm geholt wurden.
        self.custom_records: dict[str, list[dict]] = {}
        self.artist_state: dict[str, dict] = {}
        self.sort_column = "artist"
        self.sort_reverse = False
        self.only_selected = tk.BooleanVar(value=False)

        stored_lang = lastfm_api.load_config(self._config_path()).get("language")
        if stored_lang in i18n.LANGUAGES:
            i18n.set_language(stored_lang)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._style_treeview()
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_footer()
        self._load_data()

    # ------------------------------------------------------------------ #
    # Styling
    # ------------------------------------------------------------------ #
    def _style_treeview(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Lastfm.Treeview",
                        background=theme.SURFACE,
                        fieldbackground=theme.SURFACE,
                        foreground=theme.TEXT,
                        rowheight=32,
                        borderwidth=0,
                        relief="flat",
                        bordercolor=theme.SURFACE,
                        lightcolor=theme.SURFACE,
                        darkcolor=theme.SURFACE,
                        font=("Segoe UI", 11))
        style.map("Lastfm.Treeview",
                  background=[("selected", theme.SURFACE)],
                  foreground=[("selected", theme.TEXT)])
        style.configure("Lastfm.Treeview.Heading",
                        background=theme.SURFACE_2,
                        foreground=theme.TEXT_MUTED,
                        font=("Segoe UI", 10, "bold"),
                        borderwidth=0,
                        relief="flat")
        style.map("Lastfm.Treeview.Heading",
                  background=[("active", theme.BORDER)])

    # ------------------------------------------------------------------ #
    # Aufbau
    # ------------------------------------------------------------------ #
    def _column_labels(self) -> dict[str, str]:
        return {"artist": t("col.artist"), "real_count": t("col.real_count"),
                "target": t("col.target")}

    def _build_header(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", padx=24, pady=(22, 10))
        bar.grid_columnconfigure(1, weight=1)
        self._header = bar

        badge = ctk.CTkLabel(bar, text="🎧", font=_font(28), width=58, height=58,
                             fg_color=theme.SURFACE_2, corner_radius=16,
                             text_color=theme.TEXT)
        badge.grid(row=0, column=0, rowspan=2, padx=(0, 18))

        ctk.CTkLabel(bar, text="Last.fm Artist Play Exporter", anchor="w",
                     font=_font(22, "bold")).grid(row=0, column=1, sticky="sw")
        ctk.CTkLabel(bar, text=t("app.subtitle"),
                     anchor="w", font=_font(13), text_color=theme.TEXT_MUTED
                     ).grid(row=1, column=1, sticky="nw")

        lang_switch = ctk.CTkSegmentedButton(
            bar, values=["DE", "EN"], width=110, font=_font(12, "bold"),
            command=self._on_language_change)
        lang_switch.set(i18n.get_language().upper())
        lang_switch.grid(row=0, column=2, rowspan=2, padx=(12, 0))

    def _build_toolbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=14,
                           border_width=1, border_color=theme.BORDER)
        bar.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 14))
        bar.grid_columnconfigure(0, weight=1)
        self._toolbar = bar

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        inner.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(inner, height=38,
                                         placeholder_text=t("search.placeholder"))
        self.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.search_entry.bind("<KeyRelease>", lambda *_: self._refresh_rows())

        ctk.CTkButton(inner, text=t("btn.select_all"), height=38, width=130,
                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT,
                      command=lambda: self._set_all_selected(True)
                      ).grid(row=0, column=1, padx=(0, 8))
        ctk.CTkButton(inner, text=t("btn.deselect_all"), height=38, width=140,
                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT,
                      command=lambda: self._set_all_selected(False)
                      ).grid(row=0, column=2, padx=(0, 8))
        ctk.CTkButton(inner, text=t("btn.redistribute"), height=38, width=140,
                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT,
                      command=self._reset_distribution
                      ).grid(row=0, column=3, padx=(0, 8))
        ctk.CTkButton(inner, text=t("btn.add_artist"), height=38, width=160,
                      command=self._add_custom_artist
                      ).grid(row=0, column=4)

        meter_row = ctk.CTkFrame(bar, fg_color="transparent")
        meter_row.grid(row=1, column=0, sticky="ew", padx=16, pady=(2, 0))
        meter_row.grid_columnconfigure(0, weight=1)
        self.meter = ctk.CTkProgressBar(meter_row, height=10)
        self.meter.set(0)
        self.meter.grid(row=0, column=0, sticky="ew")
        self.meter_label = ctk.CTkLabel(meter_row, text=f"0 / {MAX_TOTAL_PLAYS}",
                                        font=_font(12, "bold"), width=90,
                                        anchor="e", text_color=theme.TEXT_MUTED)
        self.meter_label.grid(row=0, column=1, padx=(12, 0))

        summary_row = ctk.CTkFrame(bar, fg_color="transparent")
        summary_row.grid(row=2, column=0, sticky="ew", padx=16, pady=(6, 12))
        summary_row.grid_columnconfigure(0, weight=1)
        self.summary_var = tk.StringVar(
            value=t("summary.selected", n=0, total=0))
        ctk.CTkLabel(summary_row, textvariable=self.summary_var, anchor="w",
                     font=_font(12, "bold"), text_color=theme.ACCENT_SOFT
                     ).grid(row=0, column=0, sticky="ew")
        ctk.CTkSwitch(summary_row, text=t("switch.only_selected"),
                      variable=self.only_selected, font=_font(12),
                      command=self._refresh_rows,
                      ).grid(row=0, column=1, padx=(12, 0))

    def _build_table(self) -> None:
        wrap = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=14,
                            border_width=1, border_color=theme.BORDER)
        wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self._table_wrap = wrap

        columns = ("sel", "artist", "real_count", "target", "pin")
        self.tree = ttk.Treeview(wrap, columns=columns, show="headings",
                                  selectmode="none", style="Lastfm.Treeview")
        self.tree.heading("sel", text="✓")
        self.tree.heading("pin", text=PIN)
        for col in ("artist", "real_count", "target"):
            self.tree.heading(col, command=lambda c=col: self._sort_by(c))
        self._apply_sort_headings()
        self.tree.column("sel", width=40, anchor="center", stretch=False)
        self.tree.column("artist", width=420, anchor="w")
        self.tree.column("real_count", width=120, anchor="e", stretch=False)
        self.tree.column("target", width=120, anchor="e", stretch=False)
        self.tree.column("pin", width=40, anchor="center", stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)

        scrollbar = ctk.CTkScrollbar(wrap, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns", padx=(4, 8), pady=8)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.tag_configure("odd", background=theme.SURFACE,
                                 foreground=theme.TEXT)
        self.tree.tag_configure("even", background=theme.SURFACE_2,
                                 foreground=theme.TEXT)
        self.tree.tag_configure("chosen", background=theme.ROW_SELECTED_BG,
                                 foreground=theme.ROW_SELECTED_FG)

        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<MouseWheel>", self._on_tree_wheel)

        hint = ctk.CTkLabel(
            self, text=t("hint.table", max=MAX_TOTAL_PLAYS, pin=PIN),
            anchor="w", justify="left", wraplength=880,
            font=_font(11), text_color=theme.TEXT_FAINT)
        hint.grid(row=3, column=0, sticky="ew", padx=28, pady=(0, 10))
        self._hint = hint

    def _build_footer(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 22))
        bar.grid_columnconfigure(0, weight=1)
        self._footer = bar

        self.status_var = tk.StringVar(value=t("status.ready"))
        self.status_lbl = ctk.CTkLabel(bar, textvariable=self.status_var,
                                       anchor="w", font=_font(13),
                                       text_color=theme.SUCCESS)
        self.status_lbl.grid(row=0, column=0, sticky="ew")

        ctk.CTkButton(bar, text=t("btn.merge"), height=46, width=230,
                      corner_radius=12, font=_font(13, "bold"),
                      fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
                      text_color=theme.TEXT,
                      command=self._merge_spotify_files).grid(
            row=0, column=1, padx=(0, 10))
        ctk.CTkButton(bar, text="📂", height=46, width=52, corner_radius=12,
                      font=_font(16), fg_color=theme.SURFACE_2,
                      hover_color=theme.BORDER, text_color=theme.TEXT,
                      command=self._open_folder).grid(row=0, column=2,
                                                      padx=(0, 10))
        self.scrobble_btn = ctk.CTkButton(
            bar, text=t("btn.scrobble"), height=46, width=210,
            corner_radius=12, font=_font(14, "bold"),
            fg_color=theme.SURFACE_2, hover_color=theme.BORDER,
            text_color=theme.TEXT, command=self._scrobble)
        self.scrobble_btn.grid(row=0, column=3, padx=(0, 10))
        ctk.CTkButton(bar, text=t("btn.export"), height=46,
                      width=230, corner_radius=12, font=_font(14, "bold"),
                      command=self._export).grid(row=0, column=4)

    # ------------------------------------------------------------------ #
    # Sprache
    # ------------------------------------------------------------------ #
    def _on_language_change(self, value: str) -> None:
        lang = value.lower()
        if lang == i18n.get_language():
            return
        i18n.set_language(lang)
        self._save_language(lang)
        self._rebuild_ui()

    def _save_language(self, lang: str) -> None:
        config = lastfm_api.load_config(self._config_path())
        config["language"] = lang
        lastfm_api.save_config(config, self._config_path())

    def _rebuild_ui(self) -> None:
        """Baut die Oberflaeche nach einem Sprachwechsel neu auf; die Daten
        (grouped, artist_state, ...) bleiben auf self erhalten."""
        for widget in (self._header, self._toolbar, self._table_wrap,
                       self._hint, self._footer):
            widget.destroy()
        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_footer()
        self._refresh_rows()

    # ------------------------------------------------------------------ #
    # Daten laden
    # ------------------------------------------------------------------ #
    def _load_data(self, path: str | None = None) -> None:
        try:
            if path is None:
                path = find_source_json(self.folder)
            records = load_source_records(path)
        except (FileNotFoundError, ValueError) as err:
            msg = t(err.key, **err.params) if hasattr(err, "key") else str(err)
            messagebox.showerror(t("load.error_title"), msg)
            self.status_var.set(t("load.no_data"))
            self.status_lbl.configure(text_color=theme.ERROR)
            return
        self.grouped = aggregate_by_artist(records)
        self.custom_records = {}
        self.artist_state = {
            artist: {"selected": False, "target": len(recs),
                     "real_count": len(recs), "manual": False, "custom": False}
            for artist, recs in self.grouped.items()
        }
        self.status_var.set(
            t("load.summary", records=len(records), artists=len(self.grouped)))
        self.status_lbl.configure(text_color=theme.SUCCESS)
        self._refresh_rows()

    # ------------------------------------------------------------------ #
    # Tabelle
    # ------------------------------------------------------------------ #
    def _visible_artists(self) -> list[str]:
        query = self.search_entry.get().strip().lower()
        artists = [a for a in self.artist_state if query in a.lower()]
        if self.only_selected.get():
            artists = [a for a in artists if self.artist_state[a]["selected"]]
        if self.sort_column in ("real_count", "target"):
            artists.sort(key=lambda a: self.artist_state[a][self.sort_column],
                         reverse=self.sort_reverse)
        else:
            artists.sort(key=lambda a: a.lower(), reverse=self.sort_reverse)
        return artists

    def _refresh_rows(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for i, artist in enumerate(self._visible_artists()):
            row = self.artist_state[artist]
            checkbox = CHECKED if row["selected"] else UNCHECKED
            pin = PIN if row["manual"] else ""
            tags = ("chosen",) if row["selected"] else (
                "even" if i % 2 else "odd",)
            self.tree.insert("", "end", iid=artist, values=(
                checkbox, artist, row["real_count"], row["target"], pin),
                tags=tags)
        self._update_summary()

    def _update_summary(self) -> None:
        selected = [a for a, r in self.artist_state.items() if r["selected"]]
        pinned = [a for a in selected if self.artist_state[a]["manual"]]
        total_plays = sum(self.artist_state[a]["target"] for a in selected)
        parts = [t("summary.selected", n=len(selected),
                   total=len(self.artist_state))]
        if pinned:
            parts.append(t("summary.manual", n=len(pinned), pin=PIN))
        query = self.search_entry.get().strip()
        if query or self.only_selected.get():
            parts.append(t("summary.visible", n=len(self.tree.get_children())))
        self.summary_var.set("  ·  ".join(parts))

        ratio = min(1.0, total_plays / MAX_TOTAL_PLAYS)
        self.meter.set(ratio)
        self.meter.configure(progress_color=theme.meter_color(ratio))
        self.meter_label.configure(
            text=f"{total_plays} / {MAX_TOTAL_PLAYS}",
            text_color=theme.meter_color(ratio) if total_plays else theme.TEXT_MUTED)

    def _rebalance(self, pinned: str | None = None) -> None:
        """Verteilt das Play-Budget (MAX_TOTAL_PLAYS) auf alle ausgewählten
        Artists: manuell gesetzte Werte bleiben erhalten und passen sich
        automatisch an die Grenze an, der Rest wird gleichmäßig aufgeteilt."""
        selected = {a: r["target"] for a, r in self.artist_state.items()
                    if r["selected"]}
        if not selected:
            return
        manual = {a for a in selected if self.artist_state[a]["manual"]}
        balanced = rebalance_targets(selected, manual, MAX_TOTAL_PLAYS,
                                     pinned=pinned)
        for artist, target in balanced.items():
            self.artist_state[artist]["target"] = target

    def _apply_sort_headings(self) -> None:
        arrow = ARROW_DESC if self.sort_reverse else ARROW_ASC
        for col, label in self._column_labels().items():
            self.tree.heading(
                col, text=label + (arrow if col == self.sort_column else ""))

    def _sort_by(self, column: str) -> None:
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self._apply_sort_headings()
        self._refresh_rows()

    # ------------------------------------------------------------------ #
    # Interaktion
    # ------------------------------------------------------------------ #
    def _on_tree_click(self, event: tk.Event) -> None:
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        artist = self.tree.identify_row(event.y)
        if not artist:
            return
        if column in ("#1", "#2"):
            row = self.artist_state[artist]
            row["selected"] = not row["selected"]
            if not row["selected"]:
                row["manual"] = False
                row["target"] = row["real_count"]
            self._rebalance()
            self._refresh_rows()
        elif column == "#5" and self.artist_state[artist]["manual"]:
            self.artist_state[artist]["manual"] = False
            self._rebalance()
            self._refresh_rows()

    def _on_tree_double_click(self, event: tk.Event) -> None:
        column = self.tree.identify_column(event.x)
        artist = self.tree.identify_row(event.y)
        if not artist or column != "#4":
            return
        self._edit_target(artist)

    def _on_tree_wheel(self, event: tk.Event) -> str | None:
        column = self.tree.identify_column(event.x)
        artist = self.tree.identify_row(event.y)
        if not artist or column != "#4":
            return None
        step = 10 if (event.state & 0x0001) else 1
        delta = step if event.delta > 0 else -step
        row = self.artist_state[artist]
        row["target"] = max(0, row["target"] + delta)
        row["manual"] = True
        if row["selected"]:
            self._rebalance(pinned=artist)
        self._refresh_rows()
        return "break"

    def _edit_target(self, artist: str) -> None:
        bbox = self.tree.bbox(artist, "target")
        if not bbox:
            return
        x, y, width, height = bbox
        var = tk.StringVar(value=str(self.artist_state[artist]["target"]))
        entry = tk.Entry(self.tree, textvariable=var, justify="right",
                         bg=theme.INPUT_BG, fg=theme.TEXT,
                         insertbackground=theme.TEXT, relief="flat",
                         highlightthickness=1, highlightbackground=theme.ACCENT,
                         highlightcolor=theme.ACCENT, font=("Segoe UI", 11))
        entry.place(x=x, y=y, width=width, height=height)
        entry.focus_set()
        entry.select_range(0, "end")

        # entry.destroy() kann noch ein <FocusOut> ausloesen; ohne die
        # Sperre wuerde commit nach cancel den Wert doch noch uebernehmen.
        closed = False

        def commit(_event=None) -> None:
            nonlocal closed
            if closed:
                return
            closed = True
            text = var.get().strip()
            row = self.artist_state[artist]
            try:
                value = int(text)
                if value < 0:
                    raise ValueError
            except ValueError:
                value = row["target"]
            else:
                row["target"] = value
                row["manual"] = True
                if row["selected"]:
                    self._rebalance(pinned=artist)
            entry.destroy()
            self._refresh_rows()

        def cancel(_event=None) -> None:
            nonlocal closed
            if closed:
                return
            closed = True
            entry.destroy()

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        entry.bind("<Escape>", cancel)

    def _add_custom_artist(self) -> None:
        """Fuegt einen Artist hinzu, der nicht in der JSON steht: holt dessen
        Top-Tracks von Last.fm und macht sie scrobble-/exportierbar."""
        config = self._ensure_lastfm_session()
        if not config:
            return
        dialog = AddArtistDialog(self, default_count=MAX_TOTAL_PLAYS)
        self.wait_window(dialog)
        if not dialog.result:
            return
        artist = dialog.result["artist"]
        count = dialog.result["count"]

        existing = next(
            (a for a in self.artist_state if a.lower() == artist.lower()), None)
        if existing:
            row = self.artist_state[existing]
            row["selected"] = True
            row["target"] = count
            row["manual"] = True
            self._rebalance(pinned=existing)
            self._refresh_rows()
            self.status_var.set(t("add.updated", artist=existing))
            self.status_lbl.configure(text_color=theme.SUCCESS)
            return

        self.status_var.set(t("add.fetching", artist=artist))
        self.status_lbl.configure(text_color=theme.TEXT_MUTED)
        self.update_idletasks()
        try:
            track_names = lastfm_api.get_artist_top_tracks(
                artist, config["api_key"])
        except lastfm_api.LastfmError as err:
            messagebox.showerror(t("lastfm.error_title"), str(err))
            self.status_var.set(t("add.load_failed"))
            self.status_lbl.configure(text_color=theme.ERROR)
            return
        if not track_names:
            messagebox.showerror(t("add.not_found_title"),
                                 t("add.not_found_msg", artist=artist))
            self.status_var.set(t("add.not_found_status"))
            self.status_lbl.configure(text_color=theme.ERROR)
            return

        self.custom_records[artist] = synthetic_records(artist, track_names)
        self.artist_state[artist] = {
            "selected": True, "target": count, "real_count": len(track_names),
            "manual": True, "custom": True}
        self._rebalance(pinned=artist)
        self._refresh_rows()
        self.status_var.set(t("add.added", artist=artist, n=len(track_names)))
        self.status_lbl.configure(text_color=theme.SUCCESS)

    def _reset_distribution(self) -> None:
        """Löst alle Pins und verteilt das Budget wieder gleichmäßig."""
        for row in self.artist_state.values():
            row["manual"] = False
        self._rebalance()
        self._refresh_rows()

    def _open_folder(self) -> None:
        os.startfile(self.folder)

    def _set_all_selected(self, selected: bool) -> None:
        for artist in self._visible_artists():
            row = self.artist_state[artist]
            row["selected"] = selected
            if not selected:
                row["manual"] = False
                row["target"] = row["real_count"]
        self._rebalance()
        self._refresh_rows()

    # ------------------------------------------------------------------ #
    # Converter: mehrere Spotify-JSONs zusammenfuehren
    # ------------------------------------------------------------------ #
    def _merge_spotify_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title=t("merge.pick_title"), initialdir=self.folder,
            filetypes=[("JSON", "*.json"), ("*", "*.*")])
        if not paths:
            return
        output_path = filedialog.asksaveasfilename(
            title=t("merge.save_title"), initialdir=self.folder,
            defaultextension=".json", initialfile="streaming_history_audio_.json",
            filetypes=[("JSON", "*.json")])
        if not output_path:
            return
        try:
            merged = merge_spotify_histories(list(paths))
            write_export_json(merged, output_path)
        except (OSError, ValueError) as err:
            messagebox.showerror(t("merge.error_title"), str(err))
            return
        self.status_var.set(
            t("merge.done_status", n=len(merged), files=len(paths)))
        self.status_lbl.configure(text_color=theme.SUCCESS)
        if messagebox.askyesno(
                t("merge.done_title"),
                t("merge.done_msg", n=len(merged), files=len(paths),
                  path=output_path)):
            self._load_data(output_path)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def _combined_grouped(self) -> dict[str, list[dict]]:
        """JSON-Artists plus manuell hinzugefuegte Artists (deren Top-Tracks
        von Last.fm geholt wurden)."""
        combined = dict(self.grouped)
        combined.update(self.custom_records)
        return combined

    def _current_selections(self) -> dict[str, int] | None:
        selections = {
            artist: row["target"]
            for artist, row in self.artist_state.items()
            if row["selected"] and row["target"] > 0
        }
        if not selections:
            messagebox.showerror(t("export.no_selection_title"),
                                 t("export.no_selection_msg"))
            return None
        return selections

    def _export(self) -> None:
        selections = self._current_selections()
        if not selections:
            return
        # Anker in UTC, weil die ts-Werte mit "Z" (UTC) markiert werden;
        # der Dateiname bleibt in lokaler Zeit.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        records = generate_export_records(self._combined_grouped(), selections, now)
        output_path = os.path.join(
            self.folder, default_export_filename(datetime.now()))
        write_export_json(records, output_path)
        self.status_var.set(
            t("export.done_status", n=len(records),
              file=os.path.basename(output_path)))
        self.status_lbl.configure(text_color=theme.SUCCESS)
        if messagebox.askyesno(
                t("export.done_title"),
                t("export.done_msg", n=len(records), path=output_path)):
            self._open_folder()

    # ------------------------------------------------------------------ #
    # Scrobbeln
    # ------------------------------------------------------------------ #
    def _config_path(self) -> str:
        return os.path.join(self.folder, lastfm_api.CONFIG_FILENAME)

    def _ensure_lastfm_session(self) -> dict | None:
        app_creds = credentials.app_credentials()
        stored = credentials.load_session(self.folder)
        resolved = credentials.resolve_credentials(app_creds, stored)
        if resolved:
            return resolved
        dialog = ScrobbleSetupDialog(self, app_creds, self.folder)
        self.wait_window(dialog)
        if dialog.result and dialog.result.get("session_key"):
            return dialog.result
        return None

    def _scrobble(self) -> None:
        selections = self._current_selections()
        if not selections:
            return
        config = self._ensure_lastfm_session()
        if not config:
            return
        total = sum(selections.values())
        user = config.get("username") or t("scrobble.default_user")
        if not messagebox.askyesno(
                t("scrobble.confirm_title"),
                t("scrobble.confirm_msg", total=total, n=len(selections),
                  user=user)):
            return
        now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        records = generate_export_records(self._combined_grouped(), selections, now)
        scrobbles = [lastfm_api.record_to_scrobble(r) for r in records]
        batches = lastfm_api.chunked(scrobbles)
        self.scrobble_btn.configure(state="disabled")
        self.status_var.set(t("scrobble.progress", i=0, total=len(batches)))
        self.status_lbl.configure(text_color=theme.TEXT_MUTED)
        self._scrobble_queue: queue.Queue = queue.Queue()
        threading.Thread(target=self._scrobble_worker,
                         args=(batches, config), daemon=True).start()
        self.after(100, self._poll_scrobble_queue)

    def _scrobble_worker(self, batches: list[list[dict]],
                         config: dict) -> None:
        """Laeuft im Hintergrund-Thread; meldet Fortschritt nur ueber die
        Queue (Tkinter-Aufrufe sind hier nicht erlaubt)."""
        accepted = ignored = 0
        try:
            for i, batch in enumerate(batches, start=1):
                acc, ign = lastfm_api.scrobble_batch(
                    batch, config["api_key"], config["api_secret"],
                    config["session_key"])
                accepted += acc
                ignored += ign
                self._scrobble_queue.put(("progress", i, len(batches)))
        except Exception as err:  # Ohne "done"-Meldung haengt die GUI ewig.
            self._scrobble_queue.put(("done", accepted, ignored, str(err)))
            return
        self._scrobble_queue.put(("done", accepted, ignored, None))

    def _poll_scrobble_queue(self) -> None:
        try:
            while True:
                message = self._scrobble_queue.get_nowait()
                if message[0] == "progress":
                    _, i, total = message
                    self.status_var.set(t("scrobble.progress", i=i, total=total))
                else:
                    _, accepted, ignored, error = message
                    self._scrobble_done(accepted, ignored, error)
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll_scrobble_queue)

    def _scrobble_done(self, accepted: int, ignored: int,
                       error: str | None) -> None:
        self.scrobble_btn.configure(state="normal")
        if error:
            self.status_var.set(t("scrobble.aborted_status", error=error))
            self.status_lbl.configure(text_color=theme.ERROR)
            messagebox.showerror(t("scrobble.failed_title"),
                                 t("scrobble.failed_msg", error=error,
                                   n=accepted))
            return
        summary = t("scrobble.done_summary", n=accepted)
        if ignored:
            summary += t("scrobble.done_ignored", n=ignored)
        self.status_var.set(summary + ".")
        self.status_lbl.configure(text_color=theme.SUCCESS)
        messagebox.showinfo(t("scrobble.done_title"), summary + ".")


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
