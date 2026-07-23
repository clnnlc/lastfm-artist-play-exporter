"""Design-System fuer den Last.fm Artist Play Exporter.

Warmes Anthrazit mit Last.fm-Rot als Akzent; das Budget-Meter wandert
farblich von Gruen ueber Bernstein nach Rot, je voller das Play-Budget.
`apply()` wird einmal vor dem Erstellen der Fenster aufgerufen.
"""
from __future__ import annotations

import customtkinter as ctk

BG          = "#131013"
SURFACE     = "#1b171a"
SURFACE_2   = "#252025"
INPUT_BG    = "#151114"
BORDER      = "#352e34"

ACCENT      = "#e8382c"
ACCENT_HOVER = "#c72d22"
ACCENT_SOFT = "#ff9d94"

ROW_SELECTED_BG = "#47151a"
ROW_SELECTED_FG = "#ffe3df"

TEXT        = "#f2eef0"
TEXT_MUTED  = "#aa9fa5"
TEXT_FAINT  = "#6f6469"

SUCCESS     = "#4ade80"
WARNING     = "#fbbf24"
ERROR       = "#f87171"

METER_TRACK = "#2a2429"

_THEME = {
    "CTk":        {"fg_color": [BG, BG]},
    "CTkToplevel": {"fg_color": [BG, BG]},
    "CTkFrame": {
        "corner_radius": 14,
        "border_width": 0,
        "fg_color": [SURFACE, SURFACE],
        "top_fg_color": [SURFACE_2, SURFACE_2],
        "border_color": [BORDER, BORDER],
    },
    "CTkButton": {
        "corner_radius": 10,
        "border_width": 0,
        "fg_color": [ACCENT, ACCENT],
        "hover_color": [ACCENT_HOVER, ACCENT_HOVER],
        "border_color": [ACCENT, ACCENT],
        "text_color": ["#ffffff", "#ffffff"],
        "text_color_disabled": [TEXT_FAINT, TEXT_FAINT],
    },
    "CTkLabel": {
        "corner_radius": 0,
        "fg_color": "transparent",
        "text_color": [TEXT, TEXT],
    },
    "CTkEntry": {
        "corner_radius": 9,
        "border_width": 1,
        "fg_color": [INPUT_BG, INPUT_BG],
        "border_color": [BORDER, BORDER],
        "text_color": [TEXT, TEXT],
        "placeholder_text_color": [TEXT_FAINT, TEXT_FAINT],
    },
    "CTkSwitch": {
        "corner_radius": 1000,
        "border_width": 3,
        "button_length": 0,
        "fg_color": [BORDER, BORDER],
        "progress_color": [ACCENT, ACCENT],
        "button_color": [TEXT_MUTED, TEXT_MUTED],
        "button_hover_color": [TEXT, TEXT],
        "text_color": [TEXT_MUTED, TEXT_MUTED],
        "text_color_disabled": [TEXT_FAINT, TEXT_FAINT],
    },
    "CTkProgressBar": {
        "corner_radius": 1000,
        "border_width": 0,
        "fg_color": [METER_TRACK, METER_TRACK],
        "progress_color": [SUCCESS, SUCCESS],
        "border_color": [BORDER, BORDER],
    },
    "CTkScrollbar": {
        "corner_radius": 1000,
        "border_spacing": 4,
        "fg_color": "transparent",
        "button_color": [BORDER, BORDER],
        "button_hover_color": ["#4a4048", "#4a4048"],
    },
}


def meter_color(ratio: float) -> str:
    """Farbe des Budget-Meters: gruen -> bernstein -> rot."""
    if ratio < 0.6:
        return SUCCESS
    if ratio < 0.95:
        return WARNING
    return ACCENT


def apply() -> None:
    """Dark-Mode aktivieren und das Theme einspielen."""
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    theme = ctk.ThemeManager.theme
    for widget, props in _THEME.items():
        theme.setdefault(widget, {}).update(props)
    theme.setdefault("CTkFont", {}).setdefault("Windows", {})
    theme["CTkFont"]["Windows"].update({"family": "Segoe UI", "size": 13})
