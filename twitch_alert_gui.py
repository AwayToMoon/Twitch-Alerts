"""
Twitch Live-Alert – Moon Edition
--------------------------------
Installation:  pip install requests pillow pystray
Starten:       python twitch_alert_gui.py   (oder als .pyw ohne Konsole)
"""

import ast
import copy
import csv
import io
import json
import os
import queue
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from tkinter import filedialog, messagebox, ttk
from urllib.parse import parse_qs, urlencode, urlparse

import requests

try:
    from PIL import Image, ImageDraw, ImageTk
    HAT_PIL = True
except ImportError:
    HAT_PIL = False
try:
    import pystray
    HAT_TRAY = HAT_PIL
except ImportError:
    HAT_TRAY = False

# ---------- Farben (Standard-Design „Mond“) ----------
BG = "#0b0814"
PANEL = "#150f2b"
FELD = "#0f0a20"
RAND = "#2a2050"
AKZENT = "#9d6bff"
AKZENT_HELL = "#c9b0ff"
TEXT = "#ece6ff"
GEDAEMPFT = "#8a7fb0"
LEISE = "#5b4f87"
LIVE = "#ff4d6d"
MOND = "#f3e9c6"
GRUEN = "#5be3a0"
GELB = "#ffb84d"
KNOPF = "#241a47"
KNOPF_HOVER = "#32245f"
PUNKT_AUS = "#3a2f66"
SCHRIFT = "Segoe UI"

THEMES = {
    "Mond": dict(BG="#0b0814", PANEL="#150f2b", FELD="#0f0a20", RAND="#2a2050", AKZENT="#9d6bff",
                 AKZENT_HELL="#c9b0ff", TEXT="#ece6ff", GEDAEMPFT="#8a7fb0", LEISE="#5b4f87", LIVE="#ff4d6d",
                 MOND="#f3e9c6", GRUEN="#5be3a0", GELB="#ffb84d", KNOPF="#241a47", KNOPF_HOVER="#32245f",
                 PUNKT_AUS="#3a2f66"),
    "Sonnenuntergang": dict(BG="#120a0d", PANEL="#211216", FELD="#170c10", RAND="#40222b", AKZENT="#ff7a59",
                            AKZENT_HELL="#ffb199", TEXT="#fff0ea", GEDAEMPFT="#b58d86", LEISE="#7a5a57",
                            LIVE="#ff4d6d", MOND="#ffd98a", GRUEN="#7be0a8", GELB="#ffc857", KNOPF="#34191f",
                            KNOPF_HOVER="#4a2630", PUNKT_AUS="#5a3238"),
    "Hell": dict(BG="#f4f1fb", PANEL="#ffffff", FELD="#efeaf9", RAND="#d9d0ee", AKZENT="#7b4dff",
                 AKZENT_HELL="#5a34c9", TEXT="#1d1633", GEDAEMPFT="#6a6089", LEISE="#9a90b8", LIVE="#e5173f",
                 MOND="#e8a317", GRUEN="#12a05f", GELB="#d98200", KNOPF="#e6e0f5", KNOPF_HOVER="#d6cdee",
                 PUNKT_AUS="#cfc6e6"),
}
THEME_NAME = "Mond"
LANG = "de"
FARBEN = ["", "#ff4d6d", "#4dd0ff", "#5be3a0", "#ffb84d", "#ff7ad9"]  # "" = Standardfarbe des Designs


def wende_theme(name):
    """Setzt die Farben des gewählten Designs (muss vor dem Aufbau der Oberfläche passieren)."""
    global THEME_NAME
    THEME_NAME = name if name in THEMES else "Mond"
    globals().update(THEMES[THEME_NAME])


def setze_sprache(lang):
    global LANG
    LANG = lang if lang in ("de", "en") else "de"


def badge_daten(art):
    return {"live": ("LIVE", LIVE), "spiel": (T("SPIELWECHSEL"), GELB), "titel": (T("NEUER TITEL"), "#2aa9d6"),
            "bald": (T("BALD LIVE"), "#2aa9d6"), "offline": ("OFFLINE", "#6b6490")}.get(art, ("LIVE", LIVE))


# ---------- Version / Update ----------
# Bei jedem Update die Versionsnummer erhöhen, sonst erkennt das Programm es nicht.
VERSION = "2.2.0"
UPDATE_URL = "https://raw.githubusercontent.com/AwayToMoon/Twitch-Alerts/refs/heads/main/twitch_alert_gui.py"
RELEASES_URL = "https://github.com/AwayToMoon/Twitch-Alerts/releases/latest"  # Download der fertigen .exe
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
HELIX = "https://api.twitch.tv/helix/"

# Wird im Update-Dialog angezeigt. Muss genau so (am Zeilenanfang) stehen bleiben, sonst findet es der Update-Check nicht.
WAS_IST_NEU = {
    "de": """• Favoriten (★): eigener Ton, Pop-up bleibt bis zum Klick
• „Später“-Knopf im Pop-up (Erinnerung nach X Minuten)
• Pop-up: Ecke, Monitor und Anzeigedauer wählbar
• Spielmodus: bei Vollbild kein störendes Pop-up
• „Zugang testen“ für Client-ID und Client-Secret
• Gefolgte Kanäle von Twitch importieren
• Stream-Zeitplan: Hinweis kurz vor dem Start
• Verlauf mit Diagrammen und CSV-Export
• Mini-Fenster mit allen Live-Streamern
• Neue Designs und englische Oberfläche
• Einstellungen sichern und übertragen""",
    "en": """• Favorites (★): own sound, pop-up stays until clicked
• "Later" button in the pop-up (reminder after X minutes)
• Pop-up: choose corner, monitor and display time
• Game mode: no disturbing pop-up in full screen
• "Test access" for Client ID and Client Secret
• Import followed channels from Twitch
• Stream schedule: heads-up shortly before a start
• History with charts and CSV export
• Mini window showing everyone who is live
• New themes and English interface
• Back up and transfer settings""",
}

# Dateien liegen neben dem Skript bzw. der .exe
BASIS = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_DATEI = os.path.join(BASIS, "twitch_alert_config.json")
VERLAUF_DATEI = os.path.join(BASIS, "twitch_alert_verlauf.json")

STANDARD = {
    "client_id": "", "client_secret": "", "redirect_uri": "http://localhost",
    "streamer": ["papaplatte"],
    "intervall": 60,
    "ton": True, "sprache": False, "sound_datei": "", "sound_favorit": "",
    "ruhe_an": False, "ruhe_von": "23:00", "ruhe_bis": "08:00",
    "browser": False, "profilbild": True, "vorschau": True,
    "popup_ecke": "br", "popup_monitor": 1, "popup_dauer": 20, "erinnerung_min": 10, "spielmodus": True,
    "meld_spiel": False, "meld_titel": False, "meld_offline": False,
    "zeitplan": False, "zeitplan_min": 15,
    "autostart": True, "tray": True, "minimiert": False, "update_check": True, "log_pruefung": False,
    "mini_an": False, "mini_pos": "",
    "theme": "Mond", "lang": "de",
    "push_ntfy": False, "ntfy_topic": "",
    "push_discord": False, "discord_url": "",
    "push_telegram": False, "telegram_token": "", "telegram_chat": "",
    # login -> {"stumm": bool, "favorit": bool, "sound": pfad, "farbe": hex, "spiele": "a, b"}
    "pro_streamer": {},
}
GEHEIM = ("client_secret", "discord_url", "telegram_token", "telegram_chat", "ntfy_topic")

ZUSTAND = {"pause_bis": 0.0}  # gemeinsamer Laufzeitzustand (Pause der Alerts)


def lade_config():
    cfg = copy.deepcopy(STANDARD)
    try:
        with open(CONFIG_DATEI, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def speichere_config(cfg):
    try:
        with open(CONFIG_DATEI, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ---------- Übersetzung (Deutsch / Englisch) ----------
def uebersetze(s):
    """Übersetzt feste Texte ins Englische. Unbekanntes bleibt unverändert."""
    if LANG != "en" or not isinstance(s, str) or not s:
        return s
    if s in EN:
        return EN[s]
    if "\n" in s:
        return "\n".join(uebersetze(z) for z in s.split("\n"))
    return s


def T(s, **kw):
    """Text in der gewählten Sprache; mit Platzhaltern: T("{name} ist live", name=...)."""
    t = uebersetze(s)
    return t.format(**kw) if kw else t


_UEBERSETZUNG_AKTIV = False


def installiere_uebersetzung():
    """Übersetzt feste Beschriftungen automatisch, sobald sie in Widgets, Dialogen oder Zeichenflächen auftauchen."""
    global _UEBERSETZUNG_AKTIV
    if LANG != "en" or _UEBERSETZUNG_AKTIV:
        return
    _UEBERSETZUNG_AKTIV = True

    orig_init = tk.Widget.__init__

    def neu_init(self, master, widgetName, cnf={}, kw={}, extra=()):
        if isinstance(kw.get("text"), str):
            kw = {**kw, "text": uebersetze(kw["text"])}
        if isinstance(cnf.get("text"), str):
            cnf = {**cnf, "text": uebersetze(cnf["text"])}
        orig_init(self, master, widgetName, cnf, kw, extra)
    tk.Widget.__init__ = neu_init

    orig_cfg = tk.Misc.configure

    def neu_cfg(self, cnf=None, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = uebersetze(kw["text"])
        return orig_cfg(self, cnf, **kw)
    tk.Misc.configure = neu_cfg
    tk.Misc.config = neu_cfg

    orig_text = tk.Canvas.create_text

    def neu_text(self, *args, **kw):
        if isinstance(kw.get("text"), str):
            kw["text"] = uebersetze(kw["text"])
        return orig_text(self, *args, **kw)
    tk.Canvas.create_text = neu_text

    for name in ("showinfo", "showwarning", "showerror", "askyesno"):
        orig = getattr(messagebox, name)
        setattr(messagebox, name, (lambda o: lambda title=None, message=None, **kw:
                                   o(uebersetze(title), uebersetze(message), **kw))(orig))

# ---------- Englische Texte (Schlüssel = deutscher Originaltext) ----------
EN = {
    # Tabs und Karten
    "Übersicht": "Overview", "Handy": "Phone", "Verlauf": "History", "Programm": "Program",
    "Live-Übersicht": "Live overview", "Protokoll": "Log",
    "Einstellungen pro Streamer": "Per-streamer settings",
    "Ton & Sprache": "Sound & speech", "Ruhezeiten": "Quiet hours",
    "Zusätzliche Meldungen (nur Pop-up, ohne Ton)": "Extra notifications (pop-up only, no sound)",
    "Position und Dauer": "Position and duration", "Inhalt und Verhalten": "Content and behavior",
    "ntfy (am einfachsten)": "ntfy (easiest)", "Verlauf deiner Streamer": "History of your streamers",
    "Design und Sprache": "Theme and language", "Sichern und übertragen": "Back up and transfer",
    # Übersicht
    "Noch nicht gestartet": "Not started yet", "Prüfe …": "Checking …", "Zuletzt geprüft: {t}": "Last checked: {t}",
    "Überwachung gestoppt": "Monitoring stopped", "Überwachung gestartet.": "Monitoring started.",
    "Überwachung gestoppt.": "Monitoring stopped.",
    "Noch keine Streamer – im Tab „Streamer“ hinzufügen.": "No streamers yet – add some in the “Streamer” tab.",
    "{spiel}  ·  {n} Zuschauer": "{spiel}  ·  {n} viewers", "{n} Zuschauer": "{n} viewers",
    "offline  ·  nächster Stream {t}": "offline  ·  next stream {t}", "wird geprüft …": "checking …",
    "▶  Starten": "▶  Start", "■  Stoppen": "■  Stop", "▶ Fortsetzen": "▶ Resume",
    "○  Gestoppt": "○  Stopped", "●  Aktiv · {n} Streamer · {k} live": "●  Active · {n} streamers · {k} live",
    "⏸  Alerts pausiert · bis du fortsetzt": "⏸  Alerts paused · until you resume",
    "⏸  Alerts pausiert · bis {uhr}": "⏸  Alerts paused · until {uhr}",
    "1 Stunde": "1 hour", "2 Stunden": "2 hours", "30 Minuten": "30 minutes", "4 Stunden": "4 hours",
    "Bis ich fortsetze": "Until I resume", "Alerts pausiert ({text}).": "Alerts paused ({text}).",
    "Alerts wieder aktiv.": "Alerts active again.", "niemand": "nobody",
    # Streamer
    "＋ Hinzufügen": "＋ Add", "Ausgewählten entfernen": "Remove selected",
    "⬇ Gefolgte Kanäle importieren": "⬇ Import followed channels",
    "Wähle oben einen Streamer aus.": "Select a streamer above.", "Einstellungen für: {name}": "Settings for: {name}",
    "★ Favorit (eigener Ton, Pop-up bleibt bis zum Klick)": "★ Favorite (own sound, pop-up stays until clicked)",
    "Ton & Sprache für diesen Streamer": "Sound & speech for this streamer", "Eigener Ton": "Custom sound",
    "Standard-Ton": "Default sound", "Datei…": "File…", "Pop-up-Farbe": "Pop-up color",
    "Nur melden bei diesen Spielen": "Only notify for these games",
    "Mehrere Spiele mit Komma trennen, z. B. „GTA, Just Chatting“. Leer = immer melden.":
        "Separate several games with commas, e.g. “GTA, Just Chatting”. Empty = always notify.",
    "Gefolgte Kanäle": "Followed channels", "Alle auswählen": "Select all", "＋ Auswahl hinzufügen": "＋ Add selection",
    "{n} neue Kanäle gefunden. Wähle aus, welche überwacht werden sollen:":
        "{n} new channels found. Choose which ones to monitor:",
    "Keine neuen gefolgten Kanäle gefunden.": "No new followed channels found.",
    "Gefolgte Kanäle werden geladen – bitte im Browser bei Twitch bestätigen …":
        "Loading followed channels – please confirm in the browser on Twitch …",
    "Browser geöffnet – bitte bei Twitch bestätigen …": "Browser opened – please confirm on Twitch …",
    "Anmeldung abgebrochen oder abgelehnt.": "Sign-in canceled or denied.",
    "Die Verbindung zu Twitch ist fehlgeschlagen.": "The connection to Twitch failed.",
    "Die Redirect-URL muss auf localhost zeigen.": "The redirect URL must point to localhost.",
    "Bitte zuerst Client-ID und Client-Secret im Tab „System“ eintragen.":
        "Please enter Client ID and Client Secret in the “System” tab first.",
    "Port {port} ist belegt. Trage in der Twitch-Console z. B. http://localhost:3000 als Redirect-URL ein und gib dieselbe Adresse im Tab „System“ an.":
        "Port {port} is in use. In the Twitch console, enter e.g. http://localhost:3000 as redirect URL and use the same address in the “System” tab.",
    "Keine Antwort von Twitch. Stimmt die Redirect-URL in der Twitch-Console exakt mit der im Tab „System“ überein?":
        "No response from Twitch. Does the redirect URL in the Twitch console exactly match the one in the “System” tab?",
    "Fertig! Du kannst dieses Fenster schließen.": "Done! You can close this window.",
    # Alerts
    "Ton abspielen": "Play sound", "Sprachansage („Papaplatte ist live“)": "Voice announcement (“Papaplatte is live”)",
    "Eigener Ton (.wav)": "Custom sound (.wav)", "Ton für Favoriten ★": "Sound for favorites ★",
    "Sounddatei wählen": "Choose sound file",
    "Ruhezeit aktiv (kein Ton, keine Sprache)": "Quiet hours active (no sound, no speech)",
    "Format HH:MM, z. B. 23:00": "Format HH:MM, e.g. 23:00", "von": "from", "bis": "to",
    "Spiel gewechselt": "Game changed", "Titel geändert": "Title changed", "Stream beendet": "Stream ended",
    "Stream startet bald (laut Zeitplan des Streamers)": "Stream starts soon (per the streamer's schedule)",
    "Vorwarnzeit (Minuten)": "Heads-up time (minutes)",
    "Der Zeitplan funktioniert nur bei Streamern, die auf Twitch einen Zeitplan veröffentlicht haben.":
        "The schedule only works for streamers who have published a schedule on Twitch.",
    # Pop-up
    "Ecke": "Corner", "Es wurde nur ein Monitor erkannt.": "Only one monitor was detected.",
    "Anzeigedauer (Sekunden, 0 = bleibt bis zum Klick)": "Display time (seconds, 0 = stays until clicked)",
    "„Später“-Erinnerung nach (Minuten)": "“Later” reminder after (minutes)",
    "🔔 Pop-up ausprobieren": "🔔 Try out the pop-up",
    "Profilbild des Streamers zeigen": "Show the streamer's profile picture",
    "Vorschaubild des Streams zeigen": "Show the stream preview image",
    "Stream automatisch im Browser öffnen": "Open stream in the browser automatically",
    "Spielmodus (bei Vollbild kein Pop-up, nur Ton und Push)": "Game mode (no pop-up in full screen, sound and push only)",
    "Im Spielmodus werden Pop-ups zurückgestellt und gezeigt, sobald du das Vollbild verlässt.":
        "In game mode, pop-ups are held back and shown as soon as you leave full screen.",
    "Für Bilder bitte installieren: python -m pip install pillow": "For images please install: python -m pip install pillow",
    "▶  Ansehen": "▶  Watch", "BALD LIVE": "LIVE SOON", "SPIELWECHSEL": "GAME CHANGE", "NEUER TITEL": "NEW TITLE",
    "🎮 Vollbild erkannt – Pop-up für {name} folgt danach.": "🎮 Full screen detected – pop-up for {name} will follow afterwards.",
    "⏰ Erinnerung an {name} in {n} min.": "⏰ Reminder for {name} in {n} min.",
    "⏰ Erinnerung  ·  {n} Zuschauer": "⏰ Reminder  ·  {n} viewers",
    "{name} ist nicht mehr live – keine Erinnerung.": "{name} is no longer live – no reminder.",
    "Startet vermutlich um {uhr} (in {min} min)": "Probably starts at {uhr} (in {min} min)",
    "Stream beendet": "Stream ended", "war {d} live": "was live for {d}", "  ·  seit {d}": "  ·  for {d}",
    "Unbekannt": "Unknown", "heute {uhr}": "today {uhr}", "morgen {uhr}": "tomorrow {uhr}",
    "Niemand live": "Nobody live",
    # Handy
    "App „ntfy“ aufs Handy installieren und genau dieses Topic abonnieren. Wähle einen langen, schwer zu erratenden Namen.":
        "Install the ntfy app on your phone and subscribe to exactly this topic. Choose a long name that is hard to guess.",
    "Discord: Servereinstellungen → Integrationen → Webhooks → URL kopieren.":
        "Discord: Server settings → Integrations → Webhooks → copy URL.",
    "Bot bei @BotFather erstellen, ihm einmal schreiben und die Chat-ID eintragen.":
        "Create a bot with @BotFather, send it one message and enter the chat ID.",
    "Aktiv": "Active", "📲  Test-Push senden": "📲  Send test push",
    "Das ist ein Test-Push": "This is a test push", "Das ist eine Test-Benachrichtigung": "This is a test notification",
    "Test-Push gesendet (nur wenn mindestens ein Dienst aktiv und ausgefüllt ist).":
        "Test push sent (only if at least one service is active and filled in).",
    "Push über {dienst} fehlgeschlagen – Zugangsdaten prüfen.": "Push via {dienst} failed – check your credentials.",
    "🔴 {name} ist live": "🔴 {name} is live", "🎮 {name} wechselt das Spiel": "🎮 {name} switches games",
    "✏️ {name}: neuer Titel": "✏️ {name}: new title", "⚫ {name} ist offline": "⚫ {name} is offline",
    "⏰ {name} startet bald": "⏰ {name} starts soon",
    "{name} ist live": "{name} is live",
    # Verlauf
    "Liste": "List", "Wochen": "Weeks", "Uhrzeiten": "Times of day", "Alle": "All",
    "⟳ Aktualisieren": "⟳ Refresh", "CSV exportieren": "Export CSV", "Verlauf löschen": "Delete history",
    "Den gesamten Verlauf wirklich löschen?": "Really delete the entire history?",
    "Live-Stunden pro Woche": "Live hours per week", "Noch keine Daten.": "No data yet.",
    "Wann gehen sie live? (Anzahl Starts pro Uhrzeit)": "When do they go live? (number of starts per hour of the day)",
    "LETZTE 7 TAGE": "LAST 7 DAYS", "LETZTE STREAMS": "LATEST STREAMS",
    "Keine Streams in den letzten 7 Tagen.": "No streams in the last 7 days.",
    "Noch keine beendeten Streams aufgezeichnet.\nSobald ein überwachter Streamer offline geht, erscheint er hier.":
        "No finished streams recorded yet.\nAs soon as a monitored streamer goes offline, it will show up here.",
    "Verlauf exportieren": "Export history", "Verlauf exportiert: {pfad}": "History exported: {pfad}",
    "Dauer (min)": "Duration (min)", "Ende": "End", "Spiele": "Games", "Zuschauer-Peak": "Peak viewers",
    # System
    "🔑 Zugang testen": "🔑 Test access", "Teste …": "Testing …",
    "Bitte Client-ID und Client-Secret eintragen.": "Please enter Client ID and Client Secret.",
    "Keine Verbindung zu Twitch.": "No connection to Twitch.",
    "✔ Zugang OK – Client-ID und Secret stimmen.": "✔ Access OK – Client ID and secret are correct.",
    "✖ Das Client-Secret ist falsch.": "✖ The Client Secret is wrong.",
    "✖ Die Client-ID ist falsch.": "✖ The Client ID is wrong.",
    "✖ Twitch lehnt den Zugang ab (Fehler {code}).": "✖ Twitch rejects the access (error {code}).",
    "Prüfintervall (Sekunden)": "Check interval (seconds)",
    "Überwachung beim Öffnen automatisch starten": "Start monitoring automatically on launch",
    "Beim Schließen im Infobereich weiterlaufen": "Keep running in the tray when closed",
    "Minimiert starten (nur Symbol neben der Uhr)": "Start minimized (tray icon only)",
    "Beim Start nach Updates suchen": "Check for updates on start",
    "Jede Prüfung im Protokoll anzeigen": "Show every check in the log",
    "⟳  Jetzt nach Updates suchen": "⟳  Check for updates now",
    "Design": "Theme", "Mond": "Moon", "Sonnenuntergang": "Sunset", "Hell": "Light", "Sprache": "Language",
    "Design und Sprache gelten nach einem Neustart.": "Theme and language apply after a restart.",
    "Design und Sprache gelten nach einem Neustart. Jetzt neu starten?": "Theme and language apply after a restart. Restart now?",
    "Neustart nötig": "Restart required", "Neustart fehlgeschlagen": "Restart failed",
    "Einstellungen exportieren …": "Export settings …", "Einstellungen importieren …": "Import settings …",
    "Einstellungen exportieren": "Export settings", "Einstellungen importieren": "Import settings",
    "Einstellungen exportiert: {pfad}": "Settings exported: {pfad}",
    "Einstellungen importiert ({n} Werte).": "Settings imported ({n} values).",
    "Zugangsdaten": "Credentials",
    "Zugangsdaten (Client-Secret, Push-Adressen) mit exportieren?\n\nNur „Ja“, wenn du die Datei sicher aufbewahrst.":
        "Also export credentials (Client Secret, push addresses)?\n\nOnly choose “Yes” if you keep the file safe.",
    "Die Datei ist keine gültige Einstellungsdatei.": "The file is not a valid settings file.",
    "Fehler": "Error", "Fehler: {e}": "Error: {e}", "Fehlt noch": "Missing info",
    "Bitte im Tab „System“ Client-ID und Client-Secret eintragen.":
        "Please enter Client ID and Client Secret in the “System” tab.",
    "Bitte im Tab „Streamer“ mindestens einen Streamer hinzufügen.":
        "Please add at least one streamer in the “Streamer” tab.",
    # Updates
    "Update verfügbar": "Update available", "Update fehlgeschlagen": "Update failed",
    "Version {neu} ist verfügbar (du hast v{alt}).": "Version {neu} is available (you have v{alt}).",
    "Neu in dieser Version:": "New in this version:", "Jetzt aktualisieren und neu starten?": "Update now and restart?",
    "Die Download-Seite jetzt öffnen?": "Open the download page now?",
    "Du nutzt bereits die neueste Version (v{v}).": "You already have the latest version (v{v}).",
    "Update-Suche fehlgeschlagen – keine Verbindung zu GitHub.": "Update check failed – no connection to GitHub.",
    "Update v{neu} verfügbar – Fenster öffnen, Tab „System“ → „Jetzt nach Updates suchen“.":
        "Update v{neu} available – open the window, “System” tab → “Check for updates now”.",
    "Das Update wurde nicht installiert:": "The update was not installed:",
    "Heruntergeladene Datei wirkt unvollständig.": "The downloaded file looks incomplete.",
    # Überwachung und Meldungen
    "🔴 {name} ist LIVE – {spiel}": "🔴 {name} is LIVE – {spiel}",
    "🎮 {name}: Spielwechsel zu {spiel}": "🎮 {name}: switched to {spiel}",
    "⏰ {name} startet laut Zeitplan um {uhr}": "⏰ {name} starts at {uhr} per schedule",
    "⚫ {name} ist offline gegangen": "⚫ {name} went offline",
    "Geprüft – live: {namen}": "Checked – live: {namen}",
    "API-Fehler ({code}) – Client-ID/Secret prüfen.": "API error ({code}) – check Client ID/Secret.",
    "Netzwerkfehler – nächster Versuch folgt.": "Network error – will try again.",
    # Tray
    "Fenster öffnen": "Open window", "Beenden": "Quit",
}


# ---------- kleine Helfer ----------
def fmt_zahl(n):
    n = int(n)
    return f"{n:,}".replace(",", ".") if LANG == "de" else f"{n:,}"


def fmt_dez(v):
    s = f"{v:.1f}"
    return s.replace(".", ",") if LANG == "de" else s


def parse_zeit(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def dauer_text(sekunden):
    minuten = max(int(sekunden // 60), 0)
    if minuten < 60:
        return f"{minuten} min"
    return f"{minuten // 60} h {minuten % 60:02d} min"


def seit(start_iso):
    t = parse_zeit(start_iso)
    return dauer_text((datetime.now(timezone.utc) - t).total_seconds()) if t else ""


def heller(h, f=0.18):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(int(c + (255 - c) * f) for c in (r, g, b))


TAGE = {"de": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"], "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}


def zeit_text(dt):
    """„heute 20:00“, „morgen 20:00“ oder „Sa 20:00“ (lokale Zeit)."""
    lok = dt.astimezone()
    tage = (lok.date() - datetime.now().astimezone().date()).days
    uhr = f"{lok:%H:%M}"
    if tage == 0:
        return T("heute {uhr}", uhr=uhr)
    if tage == 1:
        return T("morgen {uhr}", uhr=uhr)
    return f"{TAGE[LANG][lok.weekday()]} {uhr}"


def in_ruhezeit(cfg):
    if not cfg["ruhe_an"]:
        return False
    try:
        v = datetime.strptime(cfg["ruhe_von"].strip(), "%H:%M")
        b = datetime.strptime(cfg["ruhe_bis"].strip(), "%H:%M")
    except ValueError:
        return False
    jetzt = datetime.now().hour * 60 + datetime.now().minute
    von, bis = v.hour * 60 + v.minute, b.hour * 60 + b.minute
    if von == bis:
        return False
    return von <= jetzt < bis if von < bis else (jetzt >= von or jetzt < bis)


def spiel_passt(cfg, login, spiel):
    filt = cfg["pro_streamer"].get(login, {}).get("spiele", "")
    teile = [t.strip().lower() for t in filt.split(",") if t.strip()]
    return not teile or any(t in spiel.lower() for t in teile)


# ---------- Ton, Sprache, Push ----------
def spiele_klang(datei="", fanfare=False):
    """Eigene .wav oder eine kurze Tonfolge (Fanfare für Favoriten)."""
    try:
        import winsound
        if datei and os.path.isfile(datei):
            winsound.PlaySound(datei, winsound.SND_FILENAME)
        else:
            folge = ((784, 110), (988, 110), (1175, 110), (1568, 320)) if fanfare else ((880, 150), (1100, 150), (1320, 300))
            for frequenz, dauer in folge:
                winsound.Beep(frequenz, dauer)
    except Exception:
        pass


def sprich(text):
    text = re.sub(r"[^\w\s-]", "", text)
    if not text.strip():
        return
    cmd = ("Add-Type -AssemblyName System.Speech; "
           f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}')")
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", cmd], timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:
        pass


def ton_und_sprache(cfg, login, name, sprechen=True):
    pro = cfg["pro_streamer"].get(login, {})
    if not cfg["ton"] or pro.get("stumm") or in_ruhezeit(cfg):
        return
    fav = bool(pro.get("favorit"))
    datei = pro.get("sound") or (cfg["sound_favorit"] if fav else cfg["sound_datei"])
    spiele_klang(datei, fanfare=fav)
    if sprechen and cfg["sprache"]:
        sprich(T("{name} ist live", name=name))


def sende_push(cfg, art, name, login, zeile, titel, log):
    url = f"https://twitch.tv/{login}"
    kopf = {"live": T("🔴 {name} ist live", name=name), "spiel": T("🎮 {name} wechselt das Spiel", name=name),
            "titel": T("✏️ {name}: neuer Titel", name=name), "offline": T("⚫ {name} ist offline", name=name),
            "bald": T("⏰ {name} startet bald", name=name)}[art]
    text = zeile + (f"\n{titel}" if titel else "")
    auftraege = []
    if cfg["push_ntfy"] and cfg["ntfy_topic"].strip():
        auftraege.append(("ntfy", lambda: requests.post(
            "https://ntfy.sh/", timeout=10,
            json={"topic": cfg["ntfy_topic"].strip(), "title": kopf, "message": text, "click": url})))
    if cfg["push_discord"] and cfg["discord_url"].strip():
        auftraege.append(("Discord", lambda: requests.post(
            cfg["discord_url"].strip(), timeout=10, json={"content": f"**{kopf}**\n{text}\n{url}"})))
    if cfg["push_telegram"] and cfg["telegram_token"].strip() and cfg["telegram_chat"].strip():
        auftraege.append(("Telegram", lambda: requests.post(
            f"https://api.telegram.org/bot{cfg['telegram_token'].strip()}/sendMessage", timeout=10,
            json={"chat_id": cfg["telegram_chat"].strip(), "text": f"{kopf}\n{text}\n{url}"})))
    for dienst, senden in auftraege:
        try:
            senden().raise_for_status()
        except requests.RequestException:
            log(T("Push über {dienst} fehlgeschlagen – Zugangsdaten prüfen.", dienst=dienst))


# ---------- Bilder ----------
def lade_bytes(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.content
    except requests.RequestException:
        return None


def tk_bild(daten, groesse, rund=False):
    if not (HAT_PIL and daten):
        return None
    try:
        bild = Image.open(io.BytesIO(daten)).convert("RGBA").resize(groesse, Image.LANCZOS)
        if rund:
            gross = Image.new("L", (groesse[0] * 4, groesse[1] * 4), 0)
            ImageDraw.Draw(gross).ellipse((0, 0, gross.size[0] - 1, gross.size[1] - 1), fill=255)
            bild.putalpha(gross.resize(groesse, Image.LANCZOS))
        return ImageTk.PhotoImage(bild)
    except Exception:
        return None


# ---------- Windows: Monitore und Vollbild ----------
def _monitorinfo_struktur():
    import ctypes
    from ctypes import wintypes

    class MonitorInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    return MonitorInfo


def monitor_bereiche(root):
    """Liste der Arbeitsbereiche (links, oben, rechts, unten, ist_hauptmonitor); Hauptmonitor zuerst."""
    bereiche = []
    try:
        import ctypes
        from ctypes import wintypes
        info_klasse = _monitorinfo_struktur()

        def rueckruf(hmon, hdc, rect, lparam):
            mi = info_klasse()
            mi.cbSize = ctypes.sizeof(info_klasse)
            ctypes.windll.user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(mi))
            w = mi.rcWork
            bereiche.append((w.left, w.top, w.right, w.bottom, bool(mi.dwFlags & 1)))
            return 1
        proc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)
        ctypes.windll.user32.EnumDisplayMonitors(0, 0, proc(rueckruf), 0)
    except Exception:
        bereiche = []
    if not bereiche:
        bereiche = [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48, True)]
    bereiche.sort(key=lambda b: (not b[4], b[0], b[1]))
    return bereiche


def vollbild_aktiv():
    """True, wenn das aktive Fenster einen ganzen Monitor ausfüllt (Spiel, Video im Vollbild …)."""
    try:
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        u.GetForegroundWindow.restype = ctypes.c_void_p  # Handles sind unter 64-Bit-Windows 64 Bit breit
        u.MonitorFromWindow.restype = ctypes.c_void_p
        hwnd = u.GetForegroundWindow()
        if not hwnd:
            return False
        h = ctypes.c_void_p(hwnd)
        klasse = ctypes.create_unicode_buffer(64)
        u.GetClassNameW(h, klasse, 64)
        if klasse.value in ("Progman", "WorkerW", "Shell_TrayWnd"):  # Desktop und Taskleiste zählen nicht
            return False
        rect = wintypes.RECT()
        u.GetWindowRect(h, ctypes.byref(rect))
        info_klasse = _monitorinfo_struktur()
        mi = info_klasse()
        mi.cbSize = ctypes.sizeof(info_klasse)
        monitor = u.MonitorFromWindow(h, 2)
        u.GetMonitorInfoW(ctypes.c_void_p(monitor), ctypes.byref(mi))
        m = mi.rcMonitor
        return rect.left <= m.left and rect.top <= m.top and rect.right >= m.right and rect.bottom >= m.bottom
    except Exception:
        return False


# ---------- Twitch-Zugang testen ----------
def pruefe_zugang(client_id, secret):
    """Gibt (ok, Text) zurück – sagt klar, ob Client-ID oder Secret falsch ist."""
    if not client_id.strip() or not secret.strip():
        return False, T("Bitte Client-ID und Client-Secret eintragen.")
    try:
        r = requests.post(TOKEN_URL, timeout=15, params={"client_id": client_id.strip(),
                                                         "client_secret": secret.strip(),
                                                         "grant_type": "client_credentials"})
    except requests.RequestException:
        return False, T("Keine Verbindung zu Twitch.")
    if r.status_code == 200:
        return True, T("✔ Zugang OK – Client-ID und Secret stimmen.")
    try:
        msg = str(r.json().get("message", "")).lower()
    except ValueError:
        msg = ""
    if "secret" in msg:
        return False, T("✖ Das Client-Secret ist falsch.")
    if "client" in msg:
        return False, T("✖ Die Client-ID ist falsch.")
    return False, T("✖ Twitch lehnt den Zugang ab (Fehler {code}).", code=r.status_code)


# ---------- Gefolgte Kanäle importieren (Twitch-Anmeldung im Browser) ----------
class _Rueckruf(BaseHTTPRequestHandler):
    def do_GET(self):
        q = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if "code" in q or "error" in q:
            self.server.ergebnis = q
            seite = ("<html><body style='background:#0b0814;color:#ece6ff;font-family:Segoe UI,sans-serif;"
                     "text-align:center;padding-top:20vh'><h1>🌙 Twitch Live-Alert</h1>"
                     f"<p>{T('Fertig! Du kannst dieses Fenster schließen.')}</p></body></html>").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(seite)))
            self.end_headers()
            self.wfile.write(seite)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


def hole_follows(cfg, fortschritt):
    """Meldet dich per Browser bei Twitch an (Recht: nur Follows lesen) und gibt die gefolgten Kanäle zurück."""
    cid, secret = cfg["client_id"].strip(), cfg["client_secret"].strip()
    if not cid or not secret:
        raise RuntimeError(T("Bitte zuerst Client-ID und Client-Secret im Tab „System“ eintragen."))
    redirect = (cfg["redirect_uri"] or "").strip() or "http://localhost"
    u = urlparse(redirect)
    if u.hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError(T("Die Redirect-URL muss auf localhost zeigen."))
    port = u.port or 80
    state = secrets.token_urlsafe(16)
    try:
        server = HTTPServer(("127.0.0.1", port), _Rueckruf)
    except OSError:
        raise RuntimeError(T("Port {port} ist belegt. Trage in der Twitch-Console z. B. http://localhost:3000 als "
                             "Redirect-URL ein und gib dieselbe Adresse im Tab „System“ an.", port=port))
    server.ergebnis = None
    server.timeout = 1
    webbrowser.open("https://id.twitch.tv/oauth2/authorize?" + urlencode({
        "client_id": cid, "redirect_uri": redirect, "response_type": "code",
        "scope": "user:read:follows", "state": state}))
    fortschritt(T("Browser geöffnet – bitte bei Twitch bestätigen …"))
    ende = time.time() + 180
    try:
        while server.ergebnis is None and time.time() < ende:
            server.handle_request()
    finally:
        server.server_close()
    erg = server.ergebnis
    if not erg:
        raise RuntimeError(T("Keine Antwort von Twitch. Stimmt die Redirect-URL in der Twitch-Console exakt mit der "
                             "im Tab „System“ überein?"))
    if erg.get("state") != state or "code" not in erg:
        raise RuntimeError(T("Anmeldung abgebrochen oder abgelehnt."))
    r = requests.post(TOKEN_URL, timeout=15, data={"client_id": cid, "client_secret": secret, "code": erg["code"],
                                                   "grant_type": "authorization_code", "redirect_uri": redirect})
    r.raise_for_status()
    kopf = {"Client-ID": cid, "Authorization": f"Bearer {r.json()['access_token']}"}
    r = requests.get(HELIX + "users", headers=kopf, timeout=15)
    r.raise_for_status()
    me = r.json()["data"][0]
    namen, cursor = [], None
    for _ in range(10):  # höchstens 1000 Kanäle
        params = {"user_id": me["id"], "first": 100}
        if cursor:
            params["after"] = cursor
        r = requests.get(HELIX + "channels/followed", params=params, headers=kopf, timeout=15)
        r.raise_for_status()
        j = r.json()
        namen += [c["broadcaster_login"].lower() for c in j["data"]]
        cursor = j.get("pagination", {}).get("cursor")
        if not cursor:
            break
    return sorted(set(namen))


# ---------- Verlauf ----------
def lade_verlauf():
    try:
        with open(VERLAUF_DATEI, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def speichere_verlauf(eintrag):
    liste = lade_verlauf()
    liste.append(eintrag)
    try:
        with open(VERLAUF_DATEI, "w", encoding="utf-8") as f:
            json.dump(liste[-500:], f, ensure_ascii=False)
    except OSError:
        pass


def verlauf_namen():
    return sorted({e.get("streamer", "?") for e in lade_verlauf()}, key=str.lower)


def verlauf_eintraege(name=None):
    """Liste von (Ende, Start, Eintrag, Sekunden) – optional nur für einen Streamer."""
    res = []
    for e in lade_verlauf():
        s, t = parse_zeit(e.get("start", "")), parse_zeit(e.get("ende", ""))
        if not s or not t:
            continue
        if name and e.get("streamer", "").lower() != name.lower():
            continue
        res.append((t, s, e, max((t - s).total_seconds(), 0)))
    return res


def verlauf_zeilen(name=None):
    eintraege = verlauf_eintraege(name)
    if not eintraege:
        return [(T("Noch keine beendeten Streams aufgezeichnet.\n"
                   "Sobald ein überwachter Streamer offline geht, erscheint er hier.") + "\n", "")]
    jetzt = datetime.now(timezone.utc)
    stat = {}
    for t, s, e, sek in eintraege:
        if (jetzt - t).days < 7:
            a = stat.setdefault(e.get("streamer", "?"), [0, 0.0, 0])
            a[0] += 1
            a[1] += sek
            a[2] = max(a[2], e.get("max", 0))
    zeilen = [(T("LETZTE 7 TAGE") + "\n", "kopf")]
    if stat:
        for n, (anz, sek, peak) in sorted(stat.items(), key=lambda x: -x[1][1]):
            zeilen.append((f"{n:<16}{anz:>3} {T('Streams')} {dauer_text(sek):>11}   Peak {fmt_zahl(peak)}\n", ""))
    else:
        zeilen.append((T("Keine Streams in den letzten 7 Tagen.") + "\n", ""))
    zeilen.append(("\n" + T("LETZTE STREAMS") + "\n", "kopf"))
    for t, s, e, sek in sorted(eintraege, key=lambda x: x[0], reverse=True)[:40]:
        spiele = ", ".join(e.get("spiele", []))[:34]
        zeilen.append((f"{s.astimezone():%d.%m. %H:%M}  {e.get('streamer', '?'):<14}{dauer_text(sek):>11}  {spiele}\n", ""))
    return zeilen


def wochen_daten(eintraege, wochen=8):
    """(Beschriftungen, Live-Stunden pro Woche) der letzten Wochen, Wochenstart = Montag."""
    heute = datetime.now().astimezone().date()
    montag0 = heute - timedelta(days=heute.weekday())
    summen = {}
    for t, s, e, sek in eintraege:
        d = s.astimezone().date()
        m = d - timedelta(days=d.weekday())
        summen[m] = summen.get(m, 0) + sek / 3600
    montage = [montag0 - timedelta(weeks=i) for i in range(wochen - 1, -1, -1)]
    return [f"{m:%d.%m.}" for m in montage], [round(summen.get(m, 0), 1) for m in montage]


def start_daten(eintraege):
    """(Beschriftungen, Anzahl Stream-Starts pro Uhrzeit 0–23)."""
    zaehler = [0] * 24
    for t, s, e, sek in eintraege:
        zaehler[s.astimezone().hour] += 1
    return [str(h) if h % 3 == 0 else "" for h in range(24)], zaehler


def verlauf_csv(pfad, name=None):
    """Schreibt den Verlauf als CSV (Semikolon, UTF-8 mit BOM – öffnet sich direkt in Excel)."""
    with open(pfad, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([T("Streamer"), T("Start"), T("Ende"), T("Dauer (min)"), T("Spiele"), T("Zuschauer-Peak")])
        for t, s, e, sek in sorted(verlauf_eintraege(name), key=lambda x: x[1]):
            w.writerow([e.get("streamer", ""), f"{s.astimezone():%Y-%m-%d %H:%M}", f"{t.astimezone():%Y-%m-%d %H:%M}",
                        round(sek / 60), ", ".join(e.get("spiele", [])), e.get("max", 0)])


# ---------- Überwachung ----------
class Monitor(threading.Thread):
    """Prüft im Hintergrund die Streamer und löst Meldungen aus."""

    def __init__(self, cfg, log):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.log = log
        self.stop_event = threading.Event()
        self.token = None
        self.zustand = {}          # login -> Laufzeitdaten des aktuellen Streams
        self.profile = {}          # Cache der Profilbilder
        self.benutzer_cache = {}   # Cache der Twitch-Benutzerdaten (ID, Anzeigename, Bild)
        self.plan = {}             # login -> (Zeitpunkt des Abrufs, Segmente des Zeitplans)
        self.plan_gemeldet = set()

    # --- Twitch-API ---
    def hole_token(self):
        r = requests.post(TOKEN_URL, timeout=15,
                          params={"client_id": self.cfg["client_id"], "client_secret": self.cfg["client_secret"],
                                  "grant_type": "client_credentials"})
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def api(self, pfad, params):
        for versuch in range(2):
            if not self.token:
                self.hole_token()
            r = requests.get(HELIX + pfad, params=params, timeout=15,
                             headers={"Client-ID": self.cfg["client_id"], "Authorization": f"Bearer {self.token}"})
            if r.status_code == 401 and versuch == 0:
                self.token = None
                continue
            r.raise_for_status()
            return r.json()["data"]
        return []

    def abfrage(self):
        """Alle aktuell laufenden Streams (Twitch erlaubt höchstens 100 Namen pro Anfrage)."""
        namen = list(self.cfg["streamer"])
        ergebnis = {}
        for i in range(0, len(namen), 100):
            params = [("user_login", n) for n in namen[i:i + 100]] + [("first", "100")]
            for s in self.api("streams", params):
                ergebnis[s["user_login"].lower()] = s
        return ergebnis

    def benutzer(self, login):
        if login not in self.benutzer_cache:
            daten = None
            try:
                u = self.api("users", [("login", login)])
                if u:
                    daten = u[0]
            except (requests.RequestException, KeyError):
                pass
            self.benutzer_cache[login] = daten
        return self.benutzer_cache[login]

    def profilbild(self, login):
        if login not in self.profile:
            u = self.benutzer(login)
            self.profile[login] = lade_bytes(u["profile_image_url"]) if u and u.get("profile_image_url") else None
        return self.profile[login]

    # --- Meldung auslösen ---
    def melde(self, art, login, name, spiel, titel, zuschauer=0, start="", alt="", vorschau_url="",
              bald_zeit=None, test=False):
        cfg = self.cfg
        pro = cfg["pro_streamer"].get(login, {})
        d = seit(start)
        info = ""
        if art == "live":
            zeile = spiel
            info = T("{n} Zuschauer", n=fmt_zahl(zuschauer)) + (T("  ·  seit {d}", d=d) if d else "")
            self.log(T("🔴 {name} ist LIVE – {spiel}", name=name, spiel=spiel))
        elif art == "spiel":
            zeile = f"{alt}  →  {spiel}"
            self.log(T("🎮 {name}: Spielwechsel zu {spiel}", name=name, spiel=spiel))
        elif art == "titel":
            zeile = spiel
            self.log(T("✏️ {name}: neuer Titel", name=name))
        elif art == "bald":
            minuten = max(int((bald_zeit - datetime.now(timezone.utc)).total_seconds() // 60), 0)
            uhr = f"{bald_zeit.astimezone():%H:%M}"
            zeile = T("Startet vermutlich um {uhr} (in {min} min)", uhr=uhr, min=minuten)
            info = spiel
            self.log(T("⏰ {name} startet laut Zeitplan um {uhr}", name=name, uhr=uhr))
        else:
            zeile, titel = T("Stream beendet"), ""
            info = T("war {d} live", d=d) if d else ""
            self.log(T("⚫ {name} ist offline gegangen", name=name))
        profil = self.profilbild(login) if cfg["profilbild"] and HAT_PIL else None
        vorschau = None
        if cfg["vorschau"] and HAT_PIL and vorschau_url and art not in ("offline", "bald"):
            vorschau = lade_bytes(vorschau_url.replace("{width}", "320").replace("{height}", "180"))
        self.log(("popup", {"art": art, "name": name, "login": login, "zeile": zeile, "info": info, "titel": titel,
                            "farbe": pro.get("farbe", ""), "favorit": bool(pro.get("favorit")), "test": test,
                            "profil": profil, "vorschau": vorschau}))
        push_text = zeile + (f"  ·  {info}" if info else "")
        threading.Thread(target=sende_push, args=(cfg, art, name, login, push_text, titel, self.log),
                         daemon=True).start()
        if art == "live":
            threading.Thread(target=ton_und_sprache, args=(cfg, login, name), daemon=True).start()
            if cfg["browser"] and not test:
                webbrowser.open(f"https://twitch.tv/{login}")

    # --- Zeitplan ---
    def zeitplan_laden(self, aktuell):
        """Lädt höchstens 3 veraltete Zeitpläne pro Durchlauf (schont die Twitch-Schnittstelle)."""
        jetzt = time.time()
        faellig = [n.lower() for n in self.cfg["streamer"]
                   if n.lower() not in aktuell and jetzt - self.plan.get(n.lower(), (0, []))[0] > 3600]
        for login in faellig[:3]:
            segmente = []
            u = self.benutzer(login)
            if u:
                try:
                    d = self.api("schedule", [("broadcaster_id", u["id"]), ("first", "10")])
                    if isinstance(d, dict):
                        segmente = [s for s in (d.get("segments") or []) if not s.get("canceled_until")]
                except requests.RequestException:
                    pass  # 404 = der Streamer hat keinen Zeitplan
            self.plan[login] = (jetzt, segmente)

    def naechster_start(self, login):
        jetzt = datetime.now(timezone.utc)
        zeiten = sorted(t for t in (parse_zeit(s.get("start_time", "")) for s in self.plan.get(login, (0, []))[1])
                        if t and t > jetzt)
        return zeiten[0] if zeiten else None

    def zeitplan_melden(self, aktuell):
        jetzt = datetime.now(timezone.utc)
        for login, (_, segmente) in list(self.plan.items()):
            if login in aktuell:
                continue
            for s in segmente:
                start = parse_zeit(s.get("start_time", ""))
                if not start:
                    continue
                minuten = (start - jetzt).total_seconds() / 60
                if 0 <= minuten <= int(self.cfg["zeitplan_min"]) and s.get("id") not in self.plan_gemeldet:
                    self.plan_gemeldet.add(s.get("id"))
                    u = self.benutzer(login) or {}
                    self.melde("bald", login, u.get("display_name", login), (s.get("category") or {}).get("name", ""),
                               s.get("title", ""), bald_zeit=start)

    # --- ein Durchlauf ---
    def tick(self):
        cfg = self.cfg
        aktuell = self.abfrage()
        pausiert = time.time() < ZUSTAND["pause_bis"]
        if cfg["zeitplan"]:
            self.zeitplan_laden(aktuell)
        info = {}
        for n in cfg["streamer"]:
            s = aktuell.get(n.lower())
            nxt = None if s or not cfg["zeitplan"] else self.naechster_start(n.lower())
            info[n.lower()] = {"live": bool(s), "spiel": (s.get("game_name") or "–") if s else "",
                               "zuschauer": s.get("viewer_count", 0) if s else 0,
                               "naechster": zeit_text(nxt) if nxt else ""}
        self.log(("live_status", info))
        if cfg["log_pruefung"]:
            live_namen = [n for n, i in info.items() if i["live"]]
            self.log(T("Geprüft – live: {namen}", namen=", ".join(live_namen) if live_namen else T("niemand")))

        for login, s in aktuell.items():
            name = s.get("user_name", login)
            spiel = s.get("game_name") or T("Unbekannt")
            titel = s.get("title", "")
            zuschauer = s.get("viewer_count", 0)
            z = self.zustand.get(login)
            if z is None:
                z = self.zustand[login] = {"spiel": spiel, "titel": titel, "start": s.get("started_at", ""),
                                           "gemeldet": False, "spiele": [], "max": 0, "fehlt": 0, "name": name}
            z["fehlt"] = 0
            z["max"] = max(z["max"], zuschauer)
            if spiel not in z["spiele"]:
                z["spiele"].append(spiel)
            args = dict(login=login, name=name, spiel=spiel, titel=titel, zuschauer=zuschauer,
                        start=z["start"], vorschau_url=s.get("thumbnail_url", ""))
            if not z["gemeldet"]:
                if not pausiert and spiel_passt(cfg, login, spiel):
                    z["gemeldet"] = True
                    self.melde("live", **args)
            elif not pausiert:
                if spiel != z["spiel"] and cfg["meld_spiel"]:
                    self.melde("spiel", alt=z["spiel"], **args)
                elif titel != z["titel"] and cfg["meld_titel"]:
                    self.melde("titel", **args)
            z["spiel"], z["titel"] = spiel, titel

        konfig = {n.lower() for n in cfg["streamer"]}
        for login in list(self.zustand):
            if login in aktuell:
                continue
            z = self.zustand[login]
            z["fehlt"] += 1
            if z["fehlt"] < 2:  # kurze API-Aussetzer ignorieren
                continue
            del self.zustand[login]
            if login not in konfig:
                continue
            speichere_verlauf({"streamer": z["name"], "start": z["start"], "max": z["max"], "spiele": z["spiele"],
                               "ende": datetime.now(timezone.utc).isoformat()})
            if z["gemeldet"] and cfg["meld_offline"] and not pausiert:
                self.melde("offline", login=login, name=z["name"], spiel=z["spiel"], titel="", start=z["start"])

        if cfg["zeitplan"] and not pausiert:
            self.zeitplan_melden(aktuell)

    def run(self):
        self.log(T("Überwachung gestartet."))
        while not self.stop_event.is_set():
            try:
                self.tick()
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "?"
                self.log(T("API-Fehler ({code}) – Client-ID/Secret prüfen.", code=code))
                self.token = None
            except requests.RequestException:
                self.log(T("Netzwerkfehler – nächster Versuch folgt."))
            except Exception as e:
                self.log(T("Fehler: {e}", e=repr(e)))
            self.stop_event.wait(max(15, int(self.cfg["intervall"])))
        self.log(T("Überwachung gestoppt."))


# ---------- Update-Hilfen ----------
def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def hole_update_text():
    r = requests.get(UPDATE_URL, params={"t": int(time.time())}, timeout=15)
    r.raise_for_status()
    return r.content.decode("utf-8")


def finde_version(text):
    m = re.search(r'^VERSION = "([\d.]+)"', text, re.MULTILINE)
    return m.group(1) if m else None


def finde_was_neu(text):
    """Liest den „Was ist neu“-Text der neuen Version (in der gewählten Sprache) aus der heruntergeladenen Datei."""
    m = re.search(r"^WAS_IST_NEU = (\{.*?^\})", text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    try:
        d = ast.literal_eval(m.group(1))
    except (ValueError, SyntaxError):
        return ""
    return (d.get(LANG) or d.get("de") or "").strip()


# ---------- Zeichen- und Bedienelemente ----------
def zeichne_mond(c, cx, cy, r, hintergrund):
    """Halbmond: heller Kreis, mit Hintergrundfarbe angeschnitten."""
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=MOND, outline="")
    dx, dy = r * 0.62, -r * 0.18
    c.create_oval(cx - r + dx, cy - r + dy, cx + r + dx, cy + r + dy, fill=hintergrund, outline="")


def zeichne_sterne(c, punkte):
    for x, y, s in punkte:
        c.create_oval(x - s, y - s, x + s, y + s, fill=AKZENT_HELL, outline="")


def icon_bild(groesse=64):
    """Mond-Symbol (dunkler Kreis, lila Rand, Halbmond), weich gezeichnet."""
    n = groesse * 8
    u = n / 64
    bild = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    d.ellipse((2 * u, 2 * u, 62 * u, 62 * u), fill=(21, 15, 43, 255), outline=(157, 107, 255, 255), width=int(3 * u))
    maske = Image.new("L", (n, n), 0)  # Halbmond per Maske, damit der Rand unberührt bleibt
    md = ImageDraw.Draw(maske)
    md.ellipse((15 * u, 14 * u, 47 * u, 46 * u), fill=255)
    md.ellipse((25 * u, 8 * u, 57 * u, 40 * u), fill=0)
    bild.paste((243, 233, 198, 255), (0, 0), maske)
    return bild.resize((groesse, groesse), Image.LANCZOS)


def tray_bild():
    return icon_bild(64)


def dunkle_titelleiste(fenster, dunkel=True):
    """Dunkle (oder helle) Windows-Titelleiste (Windows 10/11), sonst wirkungslos."""
    try:
        import ctypes
        fenster.update()
        hwnd = ctypes.windll.user32.GetParent(fenster.winfo_id())
        wert = ctypes.c_int(1 if dunkel else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(wert), ctypes.sizeof(wert))
    except Exception:
        pass


def stile_einrichten():
    """Dunkle (bzw. zum Design passende) Bildlaufleiste."""
    st = ttk.Style()
    try:
        st.theme_use("clam")
    except tk.TclError:
        return
    st.configure("Mond.Vertical.TScrollbar", background=KNOPF, troughcolor=BG, bordercolor=BG, lightcolor=KNOPF,
                 darkcolor=KNOPF, arrowcolor=GEDAEMPFT, gripcount=0, relief="flat")
    st.map("Mond.Vertical.TScrollbar", background=[("active", AKZENT)])


class Knopf(tk.Label):
    def __init__(self, master, text, aktion, primaer=False, klein=False, farbe=None):
        super().__init__(master, font=(SCHRIFT, 9 if klein else 10, "bold"),
                         padx=12 if klein else 18, pady=4 if klein else 9, cursor="hand2")
        self.aktion = aktion
        self.farbe = farbe or AKZENT
        self.setze(text, primaer)
        self.bind("<Enter>", lambda e: self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.normal))
        self.bind("<Button-1>", lambda e: self.aktion())

    def setze(self, text, primaer):
        self.normal = self.farbe if primaer else KNOPF
        self.hover = heller(self.farbe) if primaer else KNOPF_HOVER
        self.config(text=text, bg=self.normal, fg="white" if primaer else TEXT)


class Schalter(tk.Frame):
    """Moderner An/Aus-Schalter mit Beschriftung."""

    def __init__(self, master, text, variable):
        super().__init__(master, bg=PANEL)
        self.var = variable
        self.lbl = tk.Label(self, text=text, bg=PANEL, fg=TEXT, font=(SCHRIFT, 10), anchor="w")
        self.lbl.pack(side="left", fill="x", expand=True)
        self.pille = tk.Canvas(self, width=42, height=22, bg=PANEL, highlightthickness=0, cursor="hand2")
        self.pille.pack(side="right")
        for w in (self, self.lbl, self.pille):
            w.bind("<Button-1>", self.umschalten)
        variable.trace_add("write", lambda *a: self.zeichnen())
        self.zeichnen()

    def umschalten(self, e=None):
        self.var.set(not self.var.get())

    def zeichnen(self):
        c = self.pille
        c.delete("all")
        an = self.var.get()
        farbe = AKZENT if an else RAND
        c.create_oval(1, 1, 21, 21, fill=farbe, outline=farbe)
        c.create_oval(21, 1, 41, 21, fill=farbe, outline=farbe)
        c.create_rectangle(11, 1, 31, 21, fill=farbe, outline=farbe)
        x = 31 if an else 11
        c.create_oval(x - 8, 3, x + 8, 19, fill="white" if an else GEDAEMPFT, outline="")


class Segment(tk.Frame):
    """Auswahlleiste: genau eine Option ist aktiv (Wert der Variable)."""

    def __init__(self, master, optionen, variable, bg=None):
        super().__init__(master, bg=bg or PANEL)
        self.var = variable
        self.lbls = {}
        for wert, text in optionen:
            lbl = tk.Label(self, text=text, bg=KNOPF, fg=TEXT, font=(SCHRIFT, 10, "bold"),
                           padx=12, pady=4, cursor="hand2")
            lbl.pack(side="left", padx=(0, 2))
            lbl.bind("<Button-1>", lambda e, w=wert: self.var.set(w))
            self.lbls[wert] = lbl
        variable.trace_add("write", lambda *a: self.zeichnen())
        self.zeichnen()

    def zeichnen(self):
        aktuell = self.var.get()
        for w, lbl in self.lbls.items():
            an = w == aktuell
            lbl.config(bg=AKZENT if an else KNOPF, fg="white" if an else TEXT)


class TabLeiste(tk.Frame):
    def __init__(self, master, namen, wechsel):
        super().__init__(master, bg=BG)
        self.knoepfe = {}
        for n in namen:
            lbl = tk.Label(self, text=n, bg=BG, fg=GEDAEMPFT, font=(SCHRIFT, 10, "bold"), padx=9, pady=7, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, n=n: wechsel(n))
            self.knoepfe[n] = lbl

    def aktiv(self, name):
        for n, lbl in self.knoepfe.items():
            lbl.config(bg=PANEL if n == name else BG, fg=AKZENT_HELL if n == name else GEDAEMPFT)


class Scrollseite(tk.Frame):
    """Seite, die bei Platzmangel scrollt (Mausrad oder Leiste rechts)."""

    def __init__(self, master):
        super().__init__(master, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.leiste = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview,
                                    style="Mond.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=self.leiste.set)
        self.leiste.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.innen = tk.Frame(self.canvas, bg=BG)
        self.fenster = self.canvas.create_window((0, 0), window=self.innen, anchor="nw")
        self.innen.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.fenster, width=e.width))

    def rad(self, delta):
        if self.innen.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-delta / 120) or (-1 if delta > 0 else 1), "units")


def karte(parent, titel, expand=False):
    rahmen = tk.Frame(parent, bg=PANEL, highlightbackground=RAND, highlightthickness=1)
    rahmen.pack(fill="both" if expand else "x", expand=expand, padx=16, pady=5)
    tk.Label(rahmen, text=uebersetze(titel).upper(), bg=PANEL, fg=AKZENT_HELL,
             font=(SCHRIFT, 8, "bold")).pack(anchor="w", padx=14, pady=(9, 3))
    innen = tk.Frame(rahmen, bg=PANEL)
    innen.pack(fill="both" if expand else "x", expand=expand, padx=14, pady=(0, 10))
    return innen


def feld(parent, variable, show="", width=20):
    return tk.Entry(parent, textvariable=variable, show=show, width=width, bg=FELD, fg=TEXT,
                    insertbackground=AKZENT_HELL, relief="flat", font=(SCHRIFT, 10),
                    highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT)


def hinweis(parent, text):
    tk.Label(parent, text=text, bg=PANEL, fg=LEISE, font=(SCHRIFT, 8), wraplength=500,
             justify="left", anchor="w").pack(fill="x", pady=(4, 0))


def zeichne_balken(c, werte, labels, titel, fmt=lambda v: f"{v:g}", ganzzahl=False):
    """Einfaches Balkendiagramm auf einer Zeichenfläche."""
    c.delete("all")
    b, h = max(c.winfo_width(), 320), max(c.winfo_height(), 220)
    links, rechts, oben, unten = 38, 14, 40, 28
    c.create_text(links - 24, 16, text=titel, anchor="w", fill=AKZENT_HELL, font=(SCHRIFT, 9, "bold"))
    if not werte or max(werte) <= 0:
        c.create_text(b / 2, h / 2, text=T("Noch keine Daten."), fill=GEDAEMPFT, font=(SCHRIFT, 10))
        return
    spitze = max(werte) * 1.12
    if ganzzahl:  # glatte Achsenwerte (0, 1, 2, …), wenn es um Anzahlen geht
        spitze = max(4, -(-int(max(werte)) // 4) * 4)
    flaeche = h - oben - unten
    for i in range(5):
        y = h - unten - flaeche * i / 4
        c.create_line(links, y, b - rechts, y, fill=RAND)
        c.create_text(links - 6, y, text=fmt(spitze * i / 4) if i else "0", anchor="e", fill=LEISE, font=(SCHRIFT, 8))
    n = len(werte)
    breite = (b - links - rechts) / n
    for i, v in enumerate(werte):
        x0, x1 = links + i * breite + breite * 0.18, links + (i + 1) * breite - breite * 0.18
        y1 = h - unten
        y0 = y1 - flaeche * v / spitze
        if v > 0:
            c.create_rectangle(x0, y0, x1, y1, fill=AKZENT, outline="")
            if breite > 26:
                c.create_text((x0 + x1) / 2, y0 - 8, text=fmt(v), fill=TEXT, font=(SCHRIFT, 8))
        c.create_text((x0 + x1) / 2, y1 + 12, text=labels[i], fill=GEDAEMPFT, font=(SCHRIFT, 8))


class MiniFenster(tk.Toplevel):
    """Kleines Fenster, das immer im Vordergrund zeigt, wer gerade live ist."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.94)
        self.configure(bg=AKZENT)
        self.innen = tk.Frame(self, bg=PANEL)
        self.innen.pack(fill="both", expand=True, padx=1, pady=1)
        try:
            x, y = (int(v) for v in app.cfg["mini_pos"].split(","))
        except ValueError:
            x, y = app.winfo_screenwidth() - 300, 60
        self.geometry(f"+{x}+{y}")
        self._versatz = (0, 0)
        self.aktualisieren(app.live_info)

    def aktualisieren(self, info):
        for w in self.innen.winfo_children():
            w.destroy()
        tk.Frame(self.innen, width=250, height=1, bg=PANEL).pack()
        live = sorted(((n, i) for n, i in info.items() if i.get("live")), key=lambda x: -x[1].get("zuschauer", 0))
        kopf = tk.Frame(self.innen, bg=PANEL, cursor="fleur")
        kopf.pack(fill="x")
        titel = tk.Label(kopf, text=T("🌙 Live: {n}", n=len(live)), bg=PANEL, fg=AKZENT_HELL,
                         font=(SCHRIFT, 9, "bold"), padx=10, pady=6)
        titel.pack(side="left")
        zu = tk.Label(kopf, text="✕", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9), cursor="hand2", padx=8)
        zu.pack(side="right")
        zu.bind("<Button-1>", lambda e: self.app.mini_umschalten())
        for w in (kopf, titel):
            w.bind("<ButtonPress-1>", self._start)
            w.bind("<B1-Motion>", self._zieh)
            w.bind("<ButtonRelease-1>", self._ende)
        if not live:
            tk.Label(self.innen, text=T("Niemand live"), bg=PANEL, fg=LEISE, font=(SCHRIFT, 9),
                     padx=10, pady=4).pack(anchor="w")
        for n, i in live:
            zeile = tk.Frame(self.innen, bg=PANEL, cursor="hand2")
            zeile.pack(fill="x", padx=6, pady=1)
            tk.Label(zeile, text="●", fg=LIVE, bg=PANEL, font=(SCHRIFT, 9)).pack(side="left")
            tk.Label(zeile, text=n, fg=TEXT, bg=PANEL, font=(SCHRIFT, 9, "bold")).pack(side="left", padx=5)
            tk.Label(zeile, text=fmt_zahl(i.get("zuschauer", 0)), fg=AKZENT_HELL, bg=PANEL,
                     font=(SCHRIFT, 9)).pack(side="right")
            for w in [zeile] + list(zeile.winfo_children()):
                w.bind("<Button-1>", lambda e, n=n: webbrowser.open(f"https://twitch.tv/{n}"))
        tk.Frame(self.innen, height=4, bg=PANEL).pack()

    def _start(self, e):
        self._versatz = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _zieh(self, e):
        self.geometry(f"+{e.x_root - self._versatz[0]}+{e.y_root - self._versatz[1]}")

    def _ende(self, e):
        self.app.cfg["mini_pos"] = f"{self.winfo_x()},{self.winfo_y()}"
        speichere_config(self.app.cfg)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = lade_config()
        wende_theme(self.cfg["theme"])
        setze_sprache(self.cfg["lang"])
        installiere_uebersetzung()
        stile_einrichten()
        self.title("Twitch Live-Alert")
        self.geometry("600x800")
        self.minsize(560, 640)
        self.configure(bg=BG)
        try:  # eigene App-ID: die Taskleiste zeigt dann das Mond-Symbol statt des Python-Symbols
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AwayToMoon.TwitchLiveAlert")
        except Exception:
            pass
        if HAT_PIL:
            try:
                self._icons = [ImageTk.PhotoImage(icon_bild(g)) for g in (64, 32)]
                self.iconphoto(True, *self._icons)
            except Exception:
                pass
        self.vars = {}
        self.monitor = None
        self.msgs = queue.Queue()
        self.popups = []
        self.verpasst = []          # Pop-ups, die während eines Vollbilds zurückgestellt wurden
        self.tray = None
        self.mini = None
        self.live_info = {}
        self.status = (T("○  Gestoppt"), GEDAEMPFT)
        self.aktueller = None
        self.aktiver_tab = "Übersicht"
        self._laedt = False
        self._timer = None
        self._pause_an = False
        self._frage_offen = False
        self.bauen()
        dunkle_titelleiste(self, THEME_NAME != "Hell")
        self.protocol("WM_DELETE_WINDOW", self.schliessen_klick)
        self.bind_all("<MouseWheel>", self.mausrad)
        self.after(200, self.log_pumpe)
        self.after(1000, self.sekundentakt)
        self.tray_starten()
        c = self.cfg
        if c["mini_an"]:
            self.mini = MiniFenster(self)
        if c["autostart"] and c["client_id"] and c["client_secret"] and c["streamer"]:
            self.umschalten()
        if c["minimiert"] and self.tray:
            self.withdraw()
        if c["update_check"]:
            self.after(3000, self.update_pruefen)

    # ---------- Variablen und Konfiguration ----------
    def var(self, key):
        wert = self.cfg[key]
        if isinstance(wert, bool):
            v = tk.BooleanVar(value=wert)
        elif isinstance(wert, int):
            v = tk.IntVar(value=wert)
        else:
            v = tk.StringVar(value=wert)
        v.trace_add("write", self.config_geaendert)
        self.vars[key] = v
        return v

    def config_geaendert(self, *a):
        if self._timer:
            self.after_cancel(self._timer)
        self._timer = self.after(500, self.sammle_config)

    def sammle_config(self):
        neu = {}
        for k, v in self.vars.items():
            try:
                neu[k] = v.get()
            except (tk.TclError, ValueError):
                pass
        neu["streamer"] = list(self.liste.get(0, "end"))
        self.cfg.update(neu)  # in-place: laufende Überwachung übernimmt Änderungen sofort
        speichere_config(self.cfg)

    def config_anwenden(self, neu):
        """Übernimmt importierte Einstellungen in Oberfläche und Konfiguration."""
        for k, v in neu.items():
            if k in self.vars:
                try:
                    self.vars[k].set(v)
                except tk.TclError:
                    pass
        if "streamer" in neu:
            self.liste.delete(0, "end")
            for s in neu["streamer"]:
                self.liste.insert("end", s)
        if "pro_streamer" in neu:
            self.cfg["pro_streamer"].clear()
            self.cfg["pro_streamer"].update(neu["pro_streamer"])
            self.auswahl_geaendert()
        self.sammle_config()
        self.zeichne_live_liste()
        self.aktualisiere_status()
        self.neustart_fragen()

    # ---------- Aufbau ----------
    def bauen(self):
        self.kopf = tk.Canvas(self, height=84, bg=BG, highlightthickness=0)
        self.kopf.pack(fill="x")
        self.kopf.bind("<Configure>", self.zeichne_kopf)
        namen = ["Übersicht", "Streamer", "Alerts", "Pop-up", "Handy", "Verlauf", "System"]
        self.tabs = TabLeiste(self, namen, self.tab_wechseln)
        self.tabs.pack(fill="x", padx=12)
        tk.Frame(self, bg=RAND, height=1).pack(fill="x")
        inhalt = tk.Frame(self, bg=BG)
        inhalt.pack(fill="both", expand=True)
        spez = [("Übersicht", False, self.seite_uebersicht), ("Streamer", True, self.seite_streamer),
                ("Alerts", True, self.seite_alerts), ("Pop-up", True, self.seite_popup),
                ("Handy", True, self.seite_handy), ("Verlauf", False, self.seite_verlauf),
                ("System", True, self.seite_system)]
        self.seiten = {}
        for name, scroll, fn in spez:
            if scroll:
                s = Scrollseite(inhalt)
                fn(s.innen)
            else:
                s = tk.Frame(inhalt, bg=BG)
                fn(s)
            self.seiten[name] = s
        self.tab_wechseln("Übersicht")

    def tab_wechseln(self, name):
        for s in self.seiten.values():
            s.pack_forget()
        self.seiten[name].pack(fill="both", expand=True)
        self.aktiver_tab = name
        self.tabs.aktiv(name)
        if name == "Verlauf":
            self.verlauf_aktualisieren()

    def mausrad(self, e):
        s = self.seiten.get(self.aktiver_tab)
        if isinstance(s, Scrollseite):
            s.rad(e.delta)

    def zeichne_kopf(self, event=None):
        c = self.kopf
        breite = max(c.winfo_width(), 520)
        c.delete("all")
        zeichne_sterne(c, [(breite - 40, 20, 2), (breite - 90, 46, 1.5), (breite - 150, 16, 1.5),
                           (breite - 200, 62, 2), (breite - 250, 32, 1), (breite - 310, 12, 1.5)])
        zeichne_mond(c, 50, 42, 20, BG)
        c.create_text(88, 32, text="Twitch Live-Alert", anchor="w", fill=TEXT, font=(SCHRIFT, 17, "bold"))
        c.create_text(88, 58, text=self.status[0], anchor="w", fill=self.status[1], font=(SCHRIFT, 10))
        c.create_text(breite - 16, 74, text=f"v{VERSION}", anchor="e", fill=LEISE, font=(SCHRIFT, 8))

    def spin(self, parent, key, von, bis, schritt=1, breite=5):
        return tk.Spinbox(parent, from_=von, to=bis, increment=schritt, textvariable=self.var(key), width=breite,
                          bg=FELD, fg=TEXT, buttonbackground=KNOPF, insertbackground=AKZENT_HELL, relief="flat",
                          font=(SCHRIFT, 10), highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT)

    def zeile(self, parent, text):
        z = tk.Frame(parent, bg=PANEL)
        z.pack(fill="x", pady=3)
        tk.Label(z, text=text, bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left")
        return z

    # --- Tab: Übersicht ---
    def seite_uebersicht(self, f):
        k = karte(f, "Live-Übersicht")
        self.pruef_lbl = tk.Label(k, text="Noch nicht gestartet", bg=PANEL, fg=LEISE, font=(SCHRIFT, 8), anchor="e")
        self.pruef_lbl.pack(fill="x", pady=(0, 4))
        self.live_box = tk.Frame(k, bg=PANEL)
        self.live_box.pack(fill="x")
        z = tk.Frame(f, bg=BG)
        z.pack(fill="x", padx=16, pady=6)
        self.btn = Knopf(z, "▶  Starten", self.umschalten, primaer=True)
        self.btn.pack(side="left", fill="x", expand=True)
        self.pause_btn = Knopf(z, "⏸ Pause", self.pause_klick)
        self.pause_btn.pack(side="left", padx=(8, 0))
        Knopf(z, "🔔 Test", self.test).pack(side="left", padx=(8, 0))
        Knopf(z, "🗗 Mini", self.mini_umschalten).pack(side="left", padx=(8, 0))
        lf = karte(f, "Protokoll", expand=True)
        self.text = tk.Text(lf, height=5, state="disabled", wrap="word", bg=FELD, fg=GEDAEMPFT, relief="flat",
                            highlightthickness=0, font=("Consolas", 9), padx=8, pady=6)
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("zeit", foreground=LEISE)
        self.text.tag_configure("live", foreground=LIVE)
        self.text.tag_configure("warn", foreground=GELB)
        self.zeichne_live_liste()

    def zeichne_live_liste(self):
        for w in self.live_box.winfo_children():
            w.destroy()
        namen = self.cfg["streamer"]
        if not namen:
            tk.Label(self.live_box, text="Noch keine Streamer – im Tab „Streamer“ hinzufügen.",
                     bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10)).pack(anchor="w")
            return
        live_zuerst = sorted(namen, key=lambda n: 0 if self.live_info.get(n.lower(), {}).get("live") else 1)
        for n in live_zuerst:
            info = self.live_info.get(n.lower(), {})
            live = info.get("live")
            fav = self.cfg["pro_streamer"].get(n.lower(), {}).get("favorit")
            zeile = tk.Frame(self.live_box, bg=PANEL, cursor="hand2")
            zeile.pack(fill="x", pady=2)
            tk.Label(zeile, text="●", fg=LIVE if live else PUNKT_AUS, bg=PANEL, font=(SCHRIFT, 11)).pack(side="left")
            tk.Label(zeile, text=("★ " if fav else "") + n, fg=TEXT if live else GEDAEMPFT, bg=PANEL,
                     font=(SCHRIFT, 10, "bold")).pack(side="left", padx=8)
            if live:
                rechts = T("{spiel}  ·  {n} Zuschauer", spiel=info["spiel"], n=fmt_zahl(info["zuschauer"]))
            elif info:
                rechts = (T("offline  ·  nächster Stream {t}", t=info["naechster"]) if info.get("naechster")
                          else T("offline"))
            else:
                rechts = T("wird geprüft …") if self.laeuft() else "–"
            tk.Label(zeile, text=rechts, fg=AKZENT_HELL if live else LEISE, bg=PANEL,
                     font=(SCHRIFT, 9)).pack(side="right")
            for w in [zeile] + list(zeile.winfo_children()):
                w.bind("<Button-1>", lambda e, n=n: webbrowser.open(f"https://twitch.tv/{n}"))

    # --- Tab: Streamer ---
    def seite_streamer(self, f):
        sf = karte(f, "Streamer")
        z = tk.Frame(sf, bg=PANEL)
        z.pack(fill="x")
        self.v_neu = tk.StringVar()
        eintrag = feld(z, self.v_neu)
        eintrag.pack(side="left", fill="x", expand=True, ipady=5)
        eintrag.bind("<Return>", lambda e: self.hinzufuegen())
        Knopf(z, "＋ Hinzufügen", self.hinzufuegen, primaer=True, klein=True).pack(side="left", padx=(8, 0))
        self.liste = tk.Listbox(sf, height=5, bg=FELD, fg=TEXT, selectbackground=AKZENT, selectforeground="white",
                                relief="flat", highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT,
                                activestyle="none", font=(SCHRIFT, 10), exportselection=False)
        self.liste.pack(fill="x", pady=(8, 6))
        for s in self.cfg["streamer"]:
            self.liste.insert("end", s)
        self.liste.bind("<<ListboxSelect>>", self.auswahl_geaendert)
        reihe = tk.Frame(sf, bg=PANEL)
        reihe.pack(fill="x")
        Knopf(reihe, "⬇ Gefolgte Kanäle importieren", self.follows_import, klein=True).pack(side="left")
        Knopf(reihe, "Ausgewählten entfernen", self.entfernen, klein=True).pack(side="right")

        ef = karte(f, "Einstellungen pro Streamer")
        self.s_titel = tk.Label(ef, text="Wähle oben einen Streamer aus.", bg=PANEL, fg=GEDAEMPFT,
                                font=(SCHRIFT, 10, "bold"), anchor="w")
        self.s_titel.pack(fill="x", pady=(0, 4))
        self.v_s_fav = tk.BooleanVar(value=False)
        self.v_s_ton = tk.BooleanVar(value=True)
        self.v_s_sound = tk.StringVar()
        self.v_s_farbe = tk.StringVar()
        self.v_s_spiele = tk.StringVar()
        Schalter(ef, "★ Favorit (eigener Ton, Pop-up bleibt bis zum Klick)", self.v_s_fav).pack(fill="x", pady=2)
        Schalter(ef, "Ton & Sprache für diesen Streamer", self.v_s_ton).pack(fill="x", pady=2)
        self.datei_zeile(ef, "Eigener Ton", self.v_s_sound)
        reihe = tk.Frame(ef, bg=PANEL)
        reihe.pack(fill="x", pady=4)
        tk.Label(reihe, text="Pop-up-Farbe", bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left", padx=(0, 10))
        self.swatches = {}
        for farbe in FARBEN:
            lbl = tk.Label(reihe, width=3, bg=farbe or AKZENT, cursor="hand2",
                           highlightthickness=2, highlightbackground=PANEL)
            lbl.pack(side="left", padx=3)
            lbl.bind("<Button-1>", lambda e, fb=farbe: self.v_s_farbe.set(fb))
            self.swatches[farbe] = lbl
        tk.Label(ef, text="Nur melden bei diesen Spielen", bg=PANEL, fg=TEXT,
                 font=(SCHRIFT, 10), anchor="w").pack(fill="x", pady=(6, 2))
        feld(ef, self.v_s_spiele).pack(fill="x", ipady=4)
        hinweis(ef, "Mehrere Spiele mit Komma trennen, z. B. „GTA, Just Chatting“. Leer = immer melden.")
        for v in (self.v_s_fav, self.v_s_ton, self.v_s_sound, self.v_s_farbe, self.v_s_spiele):
            v.trace_add("write", self.speichere_pro)
        self.v_s_farbe.trace_add("write", lambda *a: self.zeichne_farben())

    def auswahl_geaendert(self, e=None):
        sel = self.liste.curselection()
        self.aktueller = self.liste.get(sel[0]) if sel else None
        pro = self.cfg["pro_streamer"].get(self.aktueller, {}) if self.aktueller else {}
        self._laedt = True
        self.v_s_fav.set(bool(pro.get("favorit", False)))
        self.v_s_ton.set(not pro.get("stumm", False))
        self.v_s_sound.set(pro.get("sound", ""))
        self.v_s_farbe.set(pro.get("farbe", ""))
        self.v_s_spiele.set(pro.get("spiele", ""))
        self._laedt = False
        self.s_titel.config(text=T("Einstellungen für: {name}", name=self.aktueller) if self.aktueller
                            else "Wähle oben einen Streamer aus.")
        self.zeichne_farben()

    def speichere_pro(self, *a):
        if self._laedt or not self.aktueller:
            return
        self.cfg["pro_streamer"][self.aktueller] = {
            "favorit": self.v_s_fav.get(), "stumm": not self.v_s_ton.get(), "sound": self.v_s_sound.get(),
            "farbe": self.v_s_farbe.get(), "spiele": self.v_s_spiele.get().strip()}
        speichere_config(self.cfg)
        self.zeichne_live_liste()

    def zeichne_farben(self):
        aktuell = self.v_s_farbe.get()
        for farbe, lbl in self.swatches.items():
            lbl.config(highlightbackground=TEXT if farbe == aktuell else PANEL)

    def datei_zeile(self, parent, text, var, testbar=False, fanfare=False):
        z = tk.Frame(parent, bg=PANEL)
        z.pack(fill="x", pady=3)
        tk.Label(z, text=text, bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left")
        name = tk.StringVar()

        def aktual(*a):
            name.set(os.path.basename(var.get()) or T("Standard-Ton"))
        var.trace_add("write", aktual)
        aktual()
        Knopf(z, "✕", lambda: var.set(""), klein=True).pack(side="right", padx=(6, 0))
        Knopf(z, "Datei…", lambda: self.waehle_wav(var), klein=True).pack(side="right")
        if testbar:
            Knopf(z, "▶", lambda: threading.Thread(target=spiele_klang, args=(var.get(), fanfare),
                                                  daemon=True).start(), klein=True).pack(side="right", padx=(0, 6))
        tk.Label(z, textvariable=name, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).pack(side="left", padx=10)

    def waehle_wav(self, var):
        pfad = filedialog.askopenfilename(title=T("Sounddatei wählen"), filetypes=[("WAV", "*.wav")])
        if pfad:
            var.set(pfad)

    # --- Tab: Alerts ---
    def seite_alerts(self, f):
        k = karte(f, "Ton & Sprache")
        Schalter(k, "Ton abspielen", self.var("ton")).pack(fill="x", pady=2)
        Schalter(k, "Sprachansage („Papaplatte ist live“)", self.var("sprache")).pack(fill="x", pady=2)
        self.datei_zeile(k, "Eigener Ton (.wav)", self.var("sound_datei"), testbar=True)
        self.datei_zeile(k, "Ton für Favoriten ★", self.var("sound_favorit"), testbar=True, fanfare=True)

        k = karte(f, "Ruhezeiten")
        Schalter(k, "Ruhezeit aktiv (kein Ton, keine Sprache)", self.var("ruhe_an")).pack(fill="x", pady=2)
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x", pady=4)
        for txt, key in (("von", "ruhe_von"), ("bis", "ruhe_bis")):
            tk.Label(z, text=txt, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10)).pack(side="left", padx=(0, 6))
            feld(z, self.var(key), width=7).pack(side="left", padx=(0, 16), ipady=3)
        tk.Label(z, text="Format HH:MM, z. B. 23:00", bg=PANEL, fg=LEISE, font=(SCHRIFT, 8)).pack(side="left")

        k = karte(f, "Zusätzliche Meldungen (nur Pop-up, ohne Ton)")
        Schalter(k, "Spiel gewechselt", self.var("meld_spiel")).pack(fill="x", pady=2)
        Schalter(k, "Titel geändert", self.var("meld_titel")).pack(fill="x", pady=2)
        Schalter(k, "Stream beendet", self.var("meld_offline")).pack(fill="x", pady=2)
        Schalter(k, "Stream startet bald (laut Zeitplan des Streamers)", self.var("zeitplan")).pack(fill="x", pady=2)
        z = self.zeile(k, "Vorwarnzeit (Minuten)")
        self.spin(z, "zeitplan_min", 5, 120, 5).pack(side="right", ipady=2)
        hinweis(k, "Der Zeitplan funktioniert nur bei Streamern, die auf Twitch einen Zeitplan veröffentlicht haben.")

    # --- Tab: Pop-up ---
    def seite_popup(self, f):
        k = karte(f, "Position und Dauer")
        z = self.zeile(k, "Ecke")
        Segment(z, [("tl", "↖"), ("tr", "↗"), ("bl", "↙"), ("br", "↘")], self.var("popup_ecke")).pack(side="right")
        n = len(monitor_bereiche(self))
        z = self.zeile(k, "Monitor")
        Segment(z, [(i + 1, str(i + 1)) for i in range(max(n, 1))], self.var("popup_monitor")).pack(side="right")
        if n < 2:
            hinweis(k, "Es wurde nur ein Monitor erkannt.")
        z = self.zeile(k, "Anzeigedauer (Sekunden, 0 = bleibt bis zum Klick)")
        self.spin(z, "popup_dauer", 0, 300, 5).pack(side="right", ipady=2)
        z = self.zeile(k, "„Später“-Erinnerung nach (Minuten)")
        self.spin(z, "erinnerung_min", 1, 120, 1).pack(side="right", ipady=2)
        Knopf(k, "🔔 Pop-up ausprobieren", self.test, klein=True).pack(anchor="w", pady=(8, 0))

        k = karte(f, "Inhalt und Verhalten")
        Schalter(k, "Profilbild des Streamers zeigen", self.var("profilbild")).pack(fill="x", pady=2)
        Schalter(k, "Vorschaubild des Streams zeigen", self.var("vorschau")).pack(fill="x", pady=2)
        Schalter(k, "Stream automatisch im Browser öffnen", self.var("browser")).pack(fill="x", pady=2)
        Schalter(k, "Spielmodus (bei Vollbild kein Pop-up, nur Ton und Push)", self.var("spielmodus")).pack(fill="x", pady=2)
        hinweis(k, "Im Spielmodus werden Pop-ups zurückgestellt und gezeigt, sobald du das Vollbild verlässt.")
        if not HAT_PIL:
            hinweis(k, "Für Bilder bitte installieren: python -m pip install pillow")

    # --- Tab: Handy ---
    def push_karte(self, f, titel, schalter, felder, text):
        k = karte(f, titel)
        Schalter(k, "Aktiv", self.var(schalter)).pack(fill="x", pady=2)
        for label, key, show in felder:
            z = tk.Frame(k, bg=PANEL)
            z.pack(fill="x", pady=2)
            tk.Label(z, text=label, width=12, anchor="w", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).pack(side="left")
            feld(z, self.var(key), show=show).pack(side="left", fill="x", expand=True, ipady=4)
        hinweis(k, text)

    def seite_handy(self, f):
        self.push_karte(f, "ntfy (am einfachsten)", "push_ntfy", [("Topic", "ntfy_topic", "")],
                        "App „ntfy“ aufs Handy installieren und genau dieses Topic abonnieren. "
                        "Wähle einen langen, schwer zu erratenden Namen.")
        self.push_karte(f, "Discord", "push_discord", [("Webhook-URL", "discord_url", "•")],
                        "Discord: Servereinstellungen → Integrationen → Webhooks → URL kopieren.")
        self.push_karte(f, "Telegram", "push_telegram",
                        [("Bot-Token", "telegram_token", "•"), ("Chat-ID", "telegram_chat", "")],
                        "Bot bei @BotFather erstellen, ihm einmal schreiben und die Chat-ID eintragen.")
        z = tk.Frame(f, bg=BG)
        z.pack(fill="x", padx=16, pady=6)
        Knopf(z, "📲  Test-Push senden", self.test_push, primaer=True).pack(fill="x")

    # --- Tab: Verlauf ---
    def seite_verlauf(self, f):
        k = karte(f, "Verlauf deiner Streamer", expand=True)
        kopf = tk.Frame(k, bg=PANEL)
        kopf.pack(fill="x", pady=(0, 6))
        self.v_ansicht = tk.StringVar(value="liste")
        Segment(kopf, [("liste", "Liste"), ("woche", "Wochen"), ("zeit", "Uhrzeiten")], self.v_ansicht).pack(side="left")
        self.v_filter = tk.StringVar(value=T("Alle"))
        self.filter_menue = tk.OptionMenu(kopf, self.v_filter, T("Alle"))
        self.filter_menue.config(bg=KNOPF, fg=TEXT, activebackground=AKZENT, activeforeground="white", relief="flat",
                                 highlightthickness=0, bd=0, font=(SCHRIFT, 9, "bold"), padx=10, pady=4)
        self.filter_menue["menu"].config(bg=PANEL, fg=TEXT, activebackground=AKZENT, activeforeground="white",
                                         bd=0, relief="flat")
        self.filter_menue.pack(side="left", padx=8)
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x", pady=(0, 6))
        Knopf(z, "⟳ Aktualisieren", self.verlauf_aktualisieren, klein=True).pack(side="left")
        Knopf(z, "CSV exportieren", self.verlauf_export, klein=True).pack(side="left", padx=6)
        Knopf(z, "Verlauf löschen", self.verlauf_loeschen, klein=True).pack(side="left")
        self.vtext = tk.Text(k, state="disabled", wrap="word", bg=FELD, fg=TEXT, relief="flat",
                             highlightthickness=0, font=("Consolas", 9), padx=8, pady=6)
        self.vtext.tag_configure("kopf", foreground=AKZENT_HELL, font=("Consolas", 9, "bold"))
        self.vcanvas = tk.Canvas(k, bg=FELD, highlightthickness=0)
        self.vcanvas.bind("<Configure>", lambda e: self.verlauf_aktualisieren() if self.v_ansicht.get() != "liste" else None)
        self.v_ansicht.trace_add("write", self.verlauf_aktualisieren)
        self.v_filter.trace_add("write", self.verlauf_aktualisieren)
        self.verlauf_aktualisieren()

    def verlauf_aktualisieren(self, *a):
        alle = T("Alle")
        namen = [alle] + verlauf_namen()
        menue = self.filter_menue["menu"]
        menue.delete(0, "end")
        for n in namen:
            menue.add_command(label=n, command=lambda n=n: self.v_filter.set(n))
        if self.v_filter.get() not in namen:
            self.v_filter.set(alle)
            return
        name = None if self.v_filter.get() == alle else self.v_filter.get()
        self.vtext.pack_forget()
        self.vcanvas.pack_forget()
        ansicht = self.v_ansicht.get()
        if ansicht == "liste":
            self.vtext.pack(fill="both", expand=True)
            self.vtext.config(state="normal")
            self.vtext.delete("1.0", "end")
            for zeile, tag in verlauf_zeilen(name):
                self.vtext.insert("end", zeile, tag)
            self.vtext.config(state="disabled")
            return
        self.vcanvas.pack(fill="both", expand=True)
        self.update_idletasks()
        e = verlauf_eintraege(name)
        if ansicht == "woche":
            labels, werte = wochen_daten(e)
            zeichne_balken(self.vcanvas, werte, labels, T("Live-Stunden pro Woche"), lambda v: fmt_dez(v) + " h")
        else:
            labels, werte = start_daten(e)
            zeichne_balken(self.vcanvas, werte, labels, T("Wann gehen sie live? (Anzahl Starts pro Uhrzeit)"),
                           lambda v: f"{v:.0f}", ganzzahl=True)

    def verlauf_export(self):
        pfad = filedialog.asksaveasfilename(title=T("Verlauf exportieren"), defaultextension=".csv",
                                            filetypes=[("CSV", "*.csv")], initialfile="twitch_verlauf.csv")
        if not pfad:
            return
        name = None if self.v_filter.get() == T("Alle") else self.v_filter.get()
        try:
            verlauf_csv(pfad, name)
            self.msgs.put(T("Verlauf exportiert: {pfad}", pfad=pfad))
        except OSError as e:
            messagebox.showerror(T("Fehler"), str(e))

    def verlauf_loeschen(self):
        if messagebox.askyesno("Verlauf löschen", "Den gesamten Verlauf wirklich löschen?"):
            try:
                os.remove(VERLAUF_DATEI)
            except OSError:
                pass
            self.verlauf_aktualisieren()

    # --- Tab: System ---
    def seite_system(self, f):
        api = karte(f, "Twitch-API  ·  dev.twitch.tv/console")
        api.columnconfigure(1, weight=1)
        zeilen = (("Client-ID", "client_id", ""), ("Client-Secret", "client_secret", "•"),
                  ("Redirect-URL", "redirect_uri", ""))
        for i, (txt, key, show) in enumerate(zeilen):
            tk.Label(api, text=txt, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).grid(row=i, column=0, sticky="w", pady=3)
            feld(api, self.var(key), show).grid(row=i, column=1, sticky="ew", padx=(12, 0), pady=3, ipady=4)
        z = tk.Frame(api, bg=PANEL)
        z.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        Knopf(z, "🔑 Zugang testen", self.api_test, klein=True).pack(side="left")
        self.api_lbl = tk.Label(z, text="", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9), anchor="w", wraplength=330)
        self.api_lbl.pack(side="left", padx=10)

        k = karte(f, "Programm")
        z = self.zeile(k, "Prüfintervall (Sekunden)")
        self.spin(z, "intervall", 15, 600, 15).pack(side="right", ipady=2)
        schalter = [("Überwachung beim Öffnen automatisch starten", "autostart")]
        if HAT_TRAY:
            schalter += [("Beim Schließen im Infobereich weiterlaufen", "tray"),
                         ("Minimiert starten (nur Symbol neben der Uhr)", "minimiert")]
        schalter += [("Beim Start nach Updates suchen", "update_check"),
                     ("Jede Prüfung im Protokoll anzeigen", "log_pruefung")]
        for txt, key in schalter:
            Schalter(k, txt, self.var(key)).pack(fill="x", pady=2)
        Knopf(k, "⟳  Jetzt nach Updates suchen", lambda: self.update_pruefen(True),
              klein=True).pack(anchor="w", pady=(8, 0))

        k = karte(f, "Design und Sprache")
        z = self.zeile(k, "Design")
        Segment(z, [("Mond", "Mond"), ("Sonnenuntergang", "Sonnenuntergang"), ("Hell", "Hell")],
                self.var("theme")).pack(side="right")
        z = self.zeile(k, "Sprache")
        Segment(z, [("de", "Deutsch"), ("en", "English")], self.var("lang")).pack(side="right")
        hinweis(k, "Design und Sprache gelten nach einem Neustart.")
        for key in ("theme", "lang"):
            self.vars[key].trace_add("write", lambda *a: self.after(400, self.neustart_fragen))

        k = karte(f, "Sichern und übertragen")
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x")
        Knopf(z, "Einstellungen exportieren …", self.exportiere_config, klein=True).pack(side="left")
        Knopf(z, "Einstellungen importieren …", self.importiere_config, klein=True).pack(side="left", padx=6)
        hinweis(k, f"Version {VERSION}  ·  {os.path.basename(CONFIG_DATEI)}")

    # ---------- Status und Pause ----------
    def laeuft(self):
        return bool(self.monitor and self.monitor.is_alive())

    def aktualisiere_status(self):
        rest = ZUSTAND["pause_bis"] - time.time()
        if rest > 0:
            if rest > 3 * 365 * 86400:
                status = (T("⏸  Alerts pausiert · bis du fortsetzt"), GELB)
            else:
                uhr = f"{datetime.fromtimestamp(ZUSTAND['pause_bis']):%H:%M}"
                status = (T("⏸  Alerts pausiert · bis {uhr}", uhr=uhr), GELB)
        elif self.laeuft():
            k = sum(1 for i in self.live_info.values() if i.get("live"))
            status = (T("●  Aktiv · {n} Streamer · {k} live", n=len(self.cfg["streamer"]), k=k), GRUEN)
        else:
            status = (T("○  Gestoppt"), GEDAEMPFT)
        if status != self.status:
            self.status = status
            self.zeichne_kopf()
        pausiert = rest > 0
        if pausiert != self._pause_an:
            self._pause_an = pausiert
            self.pause_btn.setze("▶ Fortsetzen" if pausiert else "⏸ Pause", False)

    def sekundentakt(self):
        self.aktualisiere_status()
        if self.verpasst and not vollbild_aktiv():  # Vollbild beendet: zurückgestellte Pop-ups nachholen
            for d in self.verpasst[:5]:
                self.zeige_popup(d)
            self.verpasst.clear()
        self.after(1000, self.sekundentakt)

    def pause_klick(self):
        if ZUSTAND["pause_bis"] > time.time():
            ZUSTAND["pause_bis"] = 0.0
            self.msgs.put(T("Alerts wieder aktiv."))
            self.aktualisiere_status()
            return
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=AKZENT, activeforeground="white")
        for text, sek in (("30 Minuten", 1800), ("1 Stunde", 3600), ("2 Stunden", 7200),
                          ("4 Stunden", 14400), ("Bis ich fortsetze", 10 ** 9)):
            m.add_command(label=T(text), command=lambda s=sek, t=text: self.pause_setzen(s, t))
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def pause_setzen(self, sekunden, text):
        ZUSTAND["pause_bis"] = time.time() + sekunden
        self.msgs.put(T("Alerts pausiert ({text}).", text=T(text)))
        self.aktualisiere_status()

    # ---------- Aktionen ----------
    def hinzufuegen(self):
        name = self.v_neu.get().strip().lower().lstrip("@")
        if name and name not in self.liste.get(0, "end"):
            self.liste.insert("end", name)
        self.v_neu.set("")
        self.sammle_config()
        self.zeichne_live_liste()
        self.aktualisiere_status()

    def entfernen(self):
        for i in reversed(self.liste.curselection()):
            self.liste.delete(i)
        self.aktueller = None
        self.auswahl_geaendert()
        self.sammle_config()
        self.zeichne_live_liste()
        self.aktualisiere_status()

    def umschalten(self):
        if self.laeuft():
            self.monitor.stop_event.set()
            self.monitor = None
            self.live_info = {}
            self.pruef_lbl.config(text="Überwachung gestoppt")
            self.btn.setze("▶  Starten", True)
            self.zeichne_live_liste()
            self.aktualisiere_status()
            if self.mini:
                self.mini.aktualisieren(self.live_info)
            return
        self.sammle_config()
        if not self.cfg["client_id"] or not self.cfg["client_secret"]:
            messagebox.showwarning("Fehlt noch", "Bitte im Tab „System“ Client-ID und Client-Secret eintragen.")
            return
        if not self.cfg["streamer"]:
            messagebox.showwarning("Fehlt noch", "Bitte im Tab „Streamer“ mindestens einen Streamer hinzufügen.")
            return
        self.monitor = Monitor(self.cfg, self.msgs.put)
        self.monitor.start()
        self.btn.setze("■  Stoppen", False)
        self.pruef_lbl.config(text="Prüfe …")
        self.aktualisiere_status()

    def test(self):
        self.sammle_config()
        m = Monitor(self.cfg, self.msgs.put)
        threading.Thread(target=m.melde, args=("live", "twitch", "Testuser", "Just Chatting",
                                               T("Das ist eine Test-Benachrichtigung")),
                         kwargs={"zuschauer": 1234, "start": datetime.now(timezone.utc).isoformat(), "test": True},
                         daemon=True).start()

    def test_push(self):
        self.sammle_config()
        threading.Thread(target=sende_push, args=(self.cfg, "live", "Testuser", "twitch",
                                                  "Just Chatting  ·  1.234", T("Das ist ein Test-Push"),
                                                  self.msgs.put), daemon=True).start()
        self.msgs.put(T("Test-Push gesendet (nur wenn mindestens ein Dienst aktiv und ausgefüllt ist)."))

    def api_test(self):
        self.sammle_config()
        self.api_lbl.config(text=T("Teste …"), fg=GEDAEMPFT)
        cid, sec = self.cfg["client_id"], self.cfg["client_secret"]
        threading.Thread(target=lambda: self.msgs.put(("api_test",) + pruefe_zugang(cid, sec)), daemon=True).start()

    def mini_umschalten(self):
        if self.mini:
            self.mini.destroy()
            self.mini = None
            self.cfg["mini_an"] = False
        else:
            self.mini = MiniFenster(self)
            self.cfg["mini_an"] = True
        speichere_config(self.cfg)

    # --- gefolgte Kanäle ---
    def follows_import(self):
        self.sammle_config()
        self.msgs.put(T("Gefolgte Kanäle werden geladen – bitte im Browser bei Twitch bestätigen …"))

        def arbeit():
            try:
                namen = hole_follows(self.cfg, self.msgs.put)
            except RuntimeError as e:
                self.msgs.put(("info", str(e)))
            except requests.RequestException:
                self.msgs.put(("info", T("Die Verbindung zu Twitch ist fehlgeschlagen.")))
            except Exception as e:
                self.msgs.put(("info", T("Fehler: {e}", e=repr(e))))
            else:
                self.msgs.put(("follows", namen))
        threading.Thread(target=arbeit, daemon=True).start()

    def follow_dialog(self, namen):
        vorhanden = set(self.liste.get(0, "end"))
        neu = [n for n in namen if n not in vorhanden]
        if not neu:
            messagebox.showinfo("Twitch Live-Alert", T("Keine neuen gefolgten Kanäle gefunden."))
            return
        dlg = tk.Toplevel(self)
        dlg.title(T("Gefolgte Kanäle"))
        dlg.configure(bg=BG)
        dlg.geometry("400x540")
        dlg.transient(self)
        dunkle_titelleiste(dlg, THEME_NAME != "Hell")
        tk.Label(dlg, text=T("{n} neue Kanäle gefunden. Wähle aus, welche überwacht werden sollen:", n=len(neu)),
                 bg=BG, fg=TEXT, font=(SCHRIFT, 10), wraplength=360, justify="left").pack(anchor="w", padx=16, pady=(14, 6))
        suche = tk.StringVar()
        feld(dlg, suche).pack(fill="x", padx=16, ipady=4)
        lb = tk.Listbox(dlg, selectmode="extended", bg=FELD, fg=TEXT, selectbackground=AKZENT, selectforeground="white",
                        relief="flat", highlightthickness=1, highlightbackground=RAND, activestyle="none",
                        font=(SCHRIFT, 10), exportselection=False)
        lb.pack(fill="both", expand=True, padx=16, pady=8)
        sichtbar = []

        def fuellen(*a):
            sichtbar[:] = [n for n in neu if suche.get().strip().lower() in n]
            lb.delete(0, "end")
            for n in sichtbar:
                lb.insert("end", n)
        suche.trace_add("write", fuellen)
        fuellen()

        def hinzu():
            for i in lb.curselection():
                if sichtbar[i] not in self.liste.get(0, "end"):
                    self.liste.insert("end", sichtbar[i])
            self.sammle_config()
            self.zeichne_live_liste()
            self.aktualisiere_status()
            dlg.destroy()
        z = tk.Frame(dlg, bg=BG)
        z.pack(fill="x", padx=16, pady=(0, 14))
        Knopf(z, "Alle auswählen", lambda: lb.selection_set(0, "end"), klein=True).pack(side="left")
        Knopf(z, "＋ Auswahl hinzufügen", hinzu, primaer=True, klein=True).pack(side="right")

    # --- Einstellungen sichern ---
    def exportiere_config(self):
        self.sammle_config()
        pfad = filedialog.asksaveasfilename(title=T("Einstellungen exportieren"), defaultextension=".json",
                                            filetypes=[("JSON", "*.json")], initialfile="twitch_alert_einstellungen.json")
        if not pfad:
            return
        mit = messagebox.askyesno(T("Zugangsdaten"), T("Zugangsdaten (Client-Secret, Push-Adressen) mit exportieren?\n\n"
                                                      "Nur „Ja“, wenn du die Datei sicher aufbewahrst."))
        daten = copy.deepcopy(self.cfg)
        if not mit:
            for k in GEHEIM:
                daten[k] = ""
        try:
            with open(pfad, "w", encoding="utf-8") as f:
                json.dump(daten, f, indent=2, ensure_ascii=False)
            self.msgs.put(T("Einstellungen exportiert: {pfad}", pfad=pfad))
        except OSError as e:
            messagebox.showerror(T("Fehler"), str(e))

    def importiere_config(self):
        pfad = filedialog.askopenfilename(title=T("Einstellungen importieren"), filetypes=[("JSON", "*.json")])
        if not pfad:
            return
        try:
            with open(pfad, "r", encoding="utf-8") as f:
                daten = json.load(f)
            if not isinstance(daten, dict):
                raise ValueError
        except (OSError, ValueError):
            messagebox.showerror(T("Fehler"), T("Die Datei ist keine gültige Einstellungsdatei."))
            return
        neu = {k: v for k, v in daten.items()
               if k in STANDARD and k not in ("mini_an", "mini_pos") and type(v) is type(STANDARD[k])}
        for k in GEHEIM:  # leere Zugangsdaten in der Datei überschreiben vorhandene nicht
            if neu.get(k) == "":
                del neu[k]
        if not neu:
            messagebox.showerror(T("Fehler"), T("Die Datei ist keine gültige Einstellungsdatei."))
            return
        self.config_anwenden(neu)
        self.msgs.put(T("Einstellungen importiert ({n} Werte).", n=len(neu)))

    def neustart_fragen(self):
        if self._frage_offen or "theme" not in self.vars:
            return
        if self.vars["theme"].get() == THEME_NAME and self.vars["lang"].get() == LANG:
            return
        self._frage_offen = True
        self.sammle_config()
        if messagebox.askyesno("Neustart nötig", "Design und Sprache gelten nach einem Neustart. Jetzt neu starten?"):
            self.neustart()
        self._frage_offen = False

    def neustart(self):
        self.sammle_config()
        if self.monitor:
            self.monitor.stop_event.set()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        try:
            args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.abspath(__file__)]
            subprocess.Popen(args)
        except Exception as e:
            messagebox.showerror("Neustart fehlgeschlagen", f"{e}")
            return
        self.destroy()

    # ---------- Nachrichten aus dem Hintergrund ----------
    def log_pumpe(self):
        try:
            while True:
                zeile = self.msgs.get_nowait()
                if isinstance(zeile, tuple):
                    art = zeile[0]
                    if art == "popup":
                        self.zeige_popup(zeile[1])
                    elif art == "live_status":
                        self.live_info = zeile[1]
                        self.pruef_lbl.config(text=T("Zuletzt geprüft: {t}", t=f"{datetime.now():%H:%M:%S}"))
                        self.zeichne_live_liste()
                        self.aktualisiere_status()
                        if self.mini:
                            self.mini.aktualisieren(self.live_info)
                    elif art == "cmd":
                        self.befehl(zeile[1])
                    elif art == "update":
                        self.frage_update(zeile[1], zeile[2])
                    elif art == "info":
                        messagebox.showinfo("Twitch Live-Alert", zeile[1])
                    elif art == "api_test":
                        self.api_lbl.config(text=zeile[2], fg=GRUEN if zeile[1] else LIVE)
                    elif art == "follows":
                        self.follow_dialog(zeile[1])
                    continue
                tag = ("live",) if "LIVE" in zeile else (("warn",) if ("fehlgeschlagen" in zeile or "Fehler" in zeile
                                                                         or "failed" in zeile or "Error" in zeile) else ())
                self.text.config(state="normal")
                self.text.insert("end", f"{datetime.now():%H:%M:%S}  ", "zeit")
                self.text.insert("end", f"{uebersetze(zeile)}\n", tag)
                if int(self.text.index("end-1c").split(".")[0]) > 500:
                    self.text.delete("1.0", "100.0")
                self.text.see("end")
                self.text.config(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self.log_pumpe)

    # ---------- Pop-up ----------
    def popup_platz(self, breite, hoehe):
        bereiche = monitor_bereiche(self)
        idx = min(max(int(self.cfg["popup_monitor"]), 1), len(bereiche)) - 1
        links, oben, rechts, unten, _ = bereiche[idx]
        ecke = self.cfg["popup_ecke"]
        i = len(self.popups)
        x = rechts - breite - 20 if ecke.endswith("r") else links + 20
        if ecke.startswith("b"):
            y = unten - hoehe - 12 - i * (hoehe + 10)
        else:
            y = oben + 12 + i * (hoehe + 10)
        return x, max(y, oben), (60 if ecke.endswith("r") else -60)

    def zeige_popup(self, d):
        if self.cfg["spielmodus"] and not d.get("test") and vollbild_aktiv():
            self.verpasst.append(d)
            self.msgs.put(T("🎮 Vollbild erkannt – Pop-up für {name} folgt danach.", name=d["name"]))
            return
        fav = d.get("favorit")
        akzent = d.get("farbe") or (GELB if fav else AKZENT)
        badge, badge_farbe = badge_daten(d["art"])
        profil = tk_bild(d.get("profil"), (54, 54), rund=True)
        vorschau = tk_bild(d.get("vorschau"), (176, 99))
        breite, hoehe = (580 if vorschau else 430), 150
        x, y, versatz = self.popup_platz(breite, hoehe)
        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.attributes("-alpha", 0.0)
        pop.configure(bg=akzent)  # 1 px leuchtender Rand
        pop.bilder = [profil, vorschau]  # Referenzen, sonst verschwinden die Bilder
        pop.geometry(f"{breite}x{hoehe}+{x + versatz}+{y}")
        self.popups.append(pop)

        def schliessen(e=None):
            if pop in self.popups:
                self.popups.remove(pop)
            try:
                pop.destroy()
            except tk.TclError:
                pass

        def oeffnen():
            webbrowser.open(f"https://twitch.tv/{d['login']}")
            schliessen()

        def spaeter():
            schliessen()
            minuten = max(1, int(self.cfg["erinnerung_min"]))
            self.msgs.put(T("⏰ Erinnerung an {name} in {n} min.", name=d["name"], n=minuten))
            self.after(minuten * 60000, lambda: self.erinnerung(d))

        innen = tk.Frame(pop, bg=PANEL)
        innen.pack(fill="both", expand=True, padx=1, pady=1)
        balken = tk.Canvas(innen, height=3, bg=PANEL, highlightthickness=0)
        balken.pack(side="bottom", fill="x")
        tk.Frame(innen, bg=akzent, width=4).pack(side="left", fill="y")
        icon = tk.Canvas(innen, width=76, bg=PANEL, highlightthickness=0)
        icon.pack(side="left", fill="y")
        if profil:
            icon.create_oval(8, 43, 68, 103, outline=akzent, width=2)
            icon.create_image(38, 73, image=profil)
        else:
            zeichne_sterne(icon, [(14, 30, 1.5), (62, 38, 1), (58, 112, 1.5), (16, 108, 1)])
            zeichne_mond(icon, 38, 72, 19, PANEL)
        if vorschau:
            tk.Label(innen, image=vorschau, bg=PANEL, bd=0).pack(side="right", padx=(0, 12), pady=(14, 10))

        rechts = tk.Frame(innen, bg=PANEL)
        rechts.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=(10, 4))
        kopf = tk.Frame(rechts, bg=PANEL)
        kopf.pack(fill="x")
        tk.Label(kopf, text=f" {badge} ", bg=badge_farbe, fg="white", font=(SCHRIFT, 8, "bold")).pack(side="left")
        tk.Label(kopf, text=("★ " if fav else "") + d["name"], bg=PANEL, fg=TEXT,
                 font=(SCHRIFT, 13, "bold")).pack(side="left", padx=(8, 0))
        zu = tk.Label(kopf, text="✕", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10), cursor="hand2")
        zu.pack(side="right")
        zu.bind("<Button-1>", schliessen)
        zu.bind("<Enter>", lambda e: zu.config(fg=TEXT))
        zu.bind("<Leave>", lambda e: zu.config(fg=GEDAEMPFT))
        wrap = breite - 76 - 4 - (200 if vorschau else 0) - 30
        # Knöpfe zuerst unten verankern, damit sie nie aus dem Fenster rutschen
        knoepfe = tk.Frame(rechts, bg=PANEL)
        knoepfe.pack(side="bottom", anchor="w", pady=(6, 2))
        Knopf(knoepfe, "▶  Ansehen", oeffnen, primaer=True, klein=True, farbe=akzent).pack(side="left")
        if d["art"] == "live":
            Knopf(knoepfe, f"⏰ {max(1, int(self.cfg['erinnerung_min']))} min", spaeter,
                  klein=True).pack(side="left", padx=(6, 0))
        tk.Label(rechts, text=d["zeile"], bg=PANEL, fg=AKZENT_HELL, font=(SCHRIFT, 10, "bold"), anchor="w",
                 justify="left", wraplength=wrap).pack(fill="x", pady=(4, 0))
        if d.get("info"):
            tk.Label(rechts, text=d["info"], bg=PANEL, fg=TEXT, font=(SCHRIFT, 9), anchor="w",
                     justify="left", wraplength=wrap).pack(fill="x")
        titel = d.get("titel", "")
        if titel:
            kurz = 44 if vorschau else 56
            tk.Label(rechts, text=titel if len(titel) <= kurz else titel[:kurz - 2] + "…", bg=PANEL, fg=GEDAEMPFT,
                     font=(SCHRIFT, 9), anchor="w", justify="left", wraplength=wrap).pack(fill="x", pady=(2, 0))

        def einblenden(schritt=0):
            if schritt > 10:
                return
            t = schritt / 10
            try:
                pop.geometry(f"{breite}x{hoehe}+{int(x + versatz * (1 - t))}+{y}")
                pop.attributes("-alpha", 0.97 * t)
            except tk.TclError:
                return
            pop.after(15, einblenden, schritt + 1)

        gesamt = 0 if fav else max(0, int(self.cfg["popup_dauer"])) * 1000  # 0 = bleibt bis zum Klick

        def fortschritt(rest=gesamt):
            if rest <= 0:
                schliessen()
                return
            balken.delete("all")
            balken.create_rectangle(0, 0, (breite - 2) * rest / gesamt, 3, fill=akzent, outline="")
            pop.after(100, fortschritt, rest - 100)

        einblenden()
        if gesamt > 0:
            fortschritt()

    def erinnerung(self, d):
        info = self.live_info.get(d["login"], {})
        if not self.laeuft() or not info.get("live"):
            self.msgs.put(T("{name} ist nicht mehr live – keine Erinnerung.", name=d["name"]))
            return
        neu = {**d, "erinnerung": True, "zeile": info.get("spiel") or d["zeile"],
               "info": T("⏰ Erinnerung  ·  {n} Zuschauer", n=fmt_zahl(info.get("zuschauer", 0)))}
        self.zeige_popup(neu)
        threading.Thread(target=ton_und_sprache, args=(self.cfg, d["login"], d["name"], False), daemon=True).start()

    # ---------- Updates ----------
    def update_pruefen(self, manuell=False):
        def arbeit():
            try:
                text = hole_update_text()
                neu = finde_version(text)
                if neu and version_tuple(neu) > version_tuple(VERSION):
                    self.msgs.put(("update", neu, text))
                elif manuell:
                    self.msgs.put(("info", T("Du nutzt bereits die neueste Version (v{v}).", v=VERSION)))
            except (requests.RequestException, UnicodeDecodeError):
                if manuell:
                    self.msgs.put(("info", T("Update-Suche fehlgeschlagen – keine Verbindung zu GitHub.")))
        threading.Thread(target=arbeit, daemon=True).start()

    def frage_update(self, neu, text):
        if self.state() == "withdrawn":  # Fenster im Infobereich: nicht mit Dialog stören
            self.msgs.put(T("Update v{neu} verfügbar – Fenster öffnen, Tab „System“ → „Jetzt nach Updates suchen“.",
                            neu=neu))
            return
        neues = finde_was_neu(text)
        kopf = T("Version {neu} ist verfügbar (du hast v{alt}).", neu=neu, alt=VERSION)
        zusatz = ("\n\n" + T("Neu in dieser Version:") + "\n" + neues) if neues else ""
        if getattr(sys, "frozen", False):  # die .exe kann sich nicht selbst ersetzen
            if messagebox.askyesno(T("Update verfügbar"), kopf + zusatz + "\n\n" +
                                   T("Die Download-Seite jetzt öffnen?")):
                webbrowser.open(RELEASES_URL)
            return
        if not messagebox.askyesno(T("Update verfügbar"), kopf + zusatz + "\n\n" +
                                   T("Jetzt aktualisieren und neu starten?")):
            return
        pfad = os.path.abspath(__file__)
        try:
            compile(text, "update", "exec")  # Syntax prüfen, bevor etwas überschrieben wird
            if "class App" not in text or "VERSION" not in text:
                raise ValueError(T("Heruntergeladene Datei wirkt unvollständig."))
            shutil.copy2(pfad, pfad + ".bak")  # Sicherung der alten Version
            tmp = pfad + ".neu"
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            os.replace(tmp, pfad)
        except Exception as e:
            messagebox.showerror(T("Update fehlgeschlagen"), T("Das Update wurde nicht installiert:") + f"\n{e}")
            return
        self.neustart()

    # ---------- Infobereich (Tray) ----------
    def tray_starten(self):
        if not HAT_TRAY or self.tray:
            return
        menue = pystray.Menu(
            pystray.MenuItem(T("Fenster öffnen"), lambda icon, item: self.msgs.put(("cmd", "zeigen")), default=True),
            pystray.MenuItem(T("Beenden"), lambda icon, item: self.msgs.put(("cmd", "beenden"))),
        )
        try:
            self.tray = pystray.Icon("twitch_alert", tray_bild(), "Twitch Live-Alert", menue)
            self.tray.run_detached()
        except Exception:
            self.tray = None

    def befehl(self, was):
        if was == "zeigen":
            self.deiconify()
            self.lift()
            self.focus_force()
        elif was == "beenden":
            self.beenden()

    def schliessen_klick(self):
        self.sammle_config()
        if self.tray and self.cfg["tray"]:
            self.withdraw()  # läuft im Infobereich weiter
        else:
            self.beenden()

    def beenden(self):
        self.sammle_config()
        if self.monitor:
            self.monitor.stop_event.set()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
