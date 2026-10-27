"""
Twitch Live-Alert – Moon Edition
--------------------------------
Installation:  pip install requests pillow pystray
Starten:       python twitch_alert_gui.py   (oder als .pyw ohne Konsole)
"""

import copy
import io
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime, timedelta, timezone

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

# ---------- Farben (schwarz / lila / Mond) ----------
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
SCHRIFT = "Segoe UI"

BADGES = {"live": ("LIVE", LIVE), "spiel": ("SPIELWECHSEL", GELB),
          "titel": ("NEUER TITEL", "#4dd0ff"), "offline": ("OFFLINE", "#6b6490")}
FARBEN = ["", "#ff4d6d", "#4dd0ff", "#5be3a0", "#ffb84d", "#ff7ad9"]  # "" = Standard-Lila

# ---------- Version / Update ----------
# Bei jedem Update die Versionsnummer erhöhen, sonst erkennt das Programm es nicht.
VERSION = "2.0.0"
UPDATE_URL = "https://raw.githubusercontent.com/AwayToMoon/Twitch-Alerts/refs/heads/main/twitch_alert_gui.py"

# Dateien liegen neben dem Skript bzw. der .exe
BASIS = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_DATEI = os.path.join(BASIS, "twitch_alert_config.json")
VERLAUF_DATEI = os.path.join(BASIS, "twitch_alert_verlauf.json")

STANDARD = {
    "client_id": "", "client_secret": "",
    "streamer": ["papaplatte"],
    "intervall": 60,
    "ton": True, "sprache": False, "sound_datei": "",
    "ruhe_an": False, "ruhe_von": "23:00", "ruhe_bis": "08:00",
    "browser": False, "profilbild": True, "vorschau": True,
    "meld_spiel": False, "meld_titel": False, "meld_offline": False,
    "autostart": True, "tray": True, "minimiert": False, "update_check": True,
    "push_ntfy": False, "ntfy_topic": "",
    "push_discord": False, "discord_url": "",
    "push_telegram": False, "telegram_token": "", "telegram_chat": "",
    "pro_streamer": {},  # login -> {"stumm": bool, "sound": pfad, "farbe": hex, "spiele": "a, b"}
}

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


# ---------- kleine Helfer ----------
def fmt_zahl(n):
    return f"{int(n):,}".replace(",", ".")


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
def spiele_klang(datei=""):
    try:
        import winsound
        if datei and os.path.isfile(datei):
            winsound.PlaySound(datei, winsound.SND_FILENAME)
        else:
            for frequenz, dauer in ((880, 150), (1100, 150), (1320, 300)):
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


def ton_und_sprache(cfg, login, name):
    pro = cfg["pro_streamer"].get(login, {})
    if not cfg["ton"] or pro.get("stumm") or in_ruhezeit(cfg):
        return
    spiele_klang(pro.get("sound") or cfg["sound_datei"])
    if cfg["sprache"]:
        sprich(f"{name} ist live")


def sende_push(cfg, art, name, login, zeile, titel, log):
    url = f"https://twitch.tv/{login}"
    kopf = {"live": f"🔴 {name} ist live", "spiel": f"🎮 {name} wechselt das Spiel",
            "titel": f"✏️ {name}: neuer Titel", "offline": f"⚫ {name} ist offline"}[art]
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
            log(f"Push über {dienst} fehlgeschlagen – Zugangsdaten prüfen.")


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


def verlauf_zeilen():
    daten = lade_verlauf()
    eintraege = []
    jetzt = datetime.now(timezone.utc)
    stat = {}
    for e in daten:
        s, t = parse_zeit(e.get("start", "")), parse_zeit(e.get("ende", ""))
        if not s or not t:
            continue
        sek = max((t - s).total_seconds(), 0)
        eintraege.append((t, s, e, sek))
        if (jetzt - t).days < 7:
            a = stat.setdefault(e.get("streamer", "?"), [0, 0.0, 0])
            a[0] += 1
            a[1] += sek
            a[2] = max(a[2], e.get("max", 0))
    if not eintraege:
        return [("Noch keine beendeten Streams aufgezeichnet.\n"
                 "Sobald ein überwachter Streamer offline geht, erscheint er hier.\n", "")]
    zeilen = [("LETZTE 7 TAGE\n", "kopf")]
    if stat:
        for name, (n, sek, peak) in sorted(stat.items(), key=lambda x: -x[1][1]):
            zeilen.append((f"{name:<16}{n:>3} Streams {dauer_text(sek):>11}   Peak {fmt_zahl(peak)}\n", ""))
    else:
        zeilen.append(("Keine Streams in den letzten 7 Tagen.\n", ""))
    zeilen.append(("\nLETZTE STREAMS\n", "kopf"))
    for t, s, e, sek in sorted(eintraege, key=lambda x: x[0], reverse=True)[:40]:
        spiele = ", ".join(e.get("spiele", []))[:34]
        zeilen.append((f"{s.astimezone():%d.%m. %H:%M}  {e.get('streamer', '?'):<14}{dauer_text(sek):>11}  {spiele}\n", ""))
    return zeilen


# ---------- Überwachung ----------
class Monitor(threading.Thread):
    """Prüft im Hintergrund die Streamer und löst Meldungen aus."""

    def __init__(self, cfg, log):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.log = log
        self.stop_event = threading.Event()
        self.token = None
        self.zustand = {}   # login -> Laufzeitdaten des aktuellen Streams
        self.profile = {}   # Cache der Profilbilder

    def hole_token(self):
        r = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={"client_id": self.cfg["client_id"], "client_secret": self.cfg["client_secret"],
                    "grant_type": "client_credentials"},
            timeout=15,
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def api(self, pfad, params):
        for versuch in range(2):
            if not self.token:
                self.hole_token()
            r = requests.get("https://api.twitch.tv/helix/" + pfad, params=params, timeout=15,
                             headers={"Client-ID": self.cfg["client_id"], "Authorization": f"Bearer {self.token}"})
            if r.status_code == 401 and versuch == 0:
                self.token = None
                continue
            r.raise_for_status()
            return r.json()["data"]
        return []

    def abfrage(self):
        params = [("user_login", n) for n in self.cfg["streamer"]]
        return {s["user_login"].lower(): s for s in self.api("streams", params)}

    def profilbild(self, login):
        if login not in self.profile:
            daten = None
            try:
                u = self.api("users", [("login", login)])
                if u:
                    daten = lade_bytes(u[0]["profile_image_url"])
            except (requests.RequestException, KeyError):
                pass
            self.profile[login] = daten
        return self.profile[login]

    def melde(self, art, login, name, spiel, titel, zuschauer=0, start="", alt="", vorschau_url="", test=False):
        cfg = self.cfg
        d = seit(start)
        info = ""
        if art == "live":
            zeile = spiel
            info = f"{fmt_zahl(zuschauer)} Zuschauer" + (f"  ·  seit {d}" if d else "")
            self.log(f"🔴 {name} ist LIVE – {spiel}")
        elif art == "spiel":
            zeile = f"{alt}  →  {spiel}"
            self.log(f"🎮 {name}: Spielwechsel zu {spiel}")
        elif art == "titel":
            zeile = spiel
            self.log(f"✏️ {name}: neuer Titel")
        else:
            zeile, titel = "Stream beendet", ""
            info = f"war {d} live" if d else ""
            self.log(f"⚫ {name} ist offline gegangen")
        profil = self.profilbild(login) if cfg["profilbild"] and HAT_PIL else None
        vorschau = None
        if cfg["vorschau"] and HAT_PIL and vorschau_url and art != "offline":
            vorschau = lade_bytes(vorschau_url.replace("{width}", "320").replace("{height}", "180"))
        self.log(("popup", {"art": art, "name": name, "login": login, "zeile": zeile, "info": info, "titel": titel,
                            "farbe": cfg["pro_streamer"].get(login, {}).get("farbe", ""),
                            "profil": profil, "vorschau": vorschau}))
        threading.Thread(target=sende_push, args=(cfg, art, name, login, zeile + (f"  ·  {info}" if info else ""), titel, self.log),
                         daemon=True).start()
        if art == "live":
            threading.Thread(target=ton_und_sprache, args=(cfg, login, name), daemon=True).start()
            if cfg["browser"] and not test:
                webbrowser.open(f"https://twitch.tv/{login}")

    def tick(self):
        cfg = self.cfg
        aktuell = self.abfrage()
        pausiert = time.time() < ZUSTAND["pause_bis"]
        info = {}
        for n in cfg["streamer"]:
            s = aktuell.get(n.lower())
            info[n.lower()] = {"live": bool(s), "spiel": (s.get("game_name") or "–") if s else "",
                               "zuschauer": s.get("viewer_count", 0) if s else 0}
        self.log(("live_status", info))

        for login, s in aktuell.items():
            name = s.get("user_name", login)
            spiel = s.get("game_name") or "Unbekannt"
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

    def run(self):
        self.log("Überwachung gestartet.")
        while not self.stop_event.is_set():
            try:
                self.tick()
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "?"
                self.log(f"API-Fehler ({code}) – Client-ID/Secret prüfen.")
                self.token = None
            except requests.RequestException:
                self.log("Netzwerkfehler – nächster Versuch folgt.")
            except Exception as e:
                self.log(f"Fehler: {e!r}")
            self.stop_event.wait(max(15, int(self.cfg["intervall"])))
        self.log("Überwachung gestoppt.")


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


# ---------- Zeichen- und Bedienelemente ----------
def zeichne_mond(c, cx, cy, r, hintergrund):
    """Halbmond: heller Kreis, mit Hintergrundfarbe angeschnitten."""
    c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=MOND, outline="")
    dx, dy = r * 0.62, -r * 0.18
    c.create_oval(cx - r + dx, cy - r + dy, cx + r + dx, cy + r + dy, fill=hintergrund, outline="")


def zeichne_sterne(c, punkte):
    for x, y, s in punkte:
        c.create_oval(x - s, y - s, x + s, y + s, fill=AKZENT_HELL, outline="")


def tray_bild():
    bild = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    d.ellipse((2, 2, 62, 62), fill=(21, 15, 43, 255), outline=(157, 107, 255, 255), width=3)
    d.ellipse((15, 14, 47, 46), fill=(243, 233, 198, 255))
    d.ellipse((25, 8, 57, 40), fill=(21, 15, 43, 255))
    return bild


def dunkle_titelleiste(fenster):
    """Dunkle Windows-Titelleiste (Windows 10/11), sonst wirkungslos."""
    try:
        import ctypes
        fenster.update()
        hwnd = ctypes.windll.user32.GetParent(fenster.winfo_id())
        wert = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(wert), ctypes.sizeof(wert))
    except Exception:
        pass


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
        self.normal = self.farbe if primaer else "#241a47"
        self.hover = heller(self.farbe) if primaer else "#32245f"
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
        c.create_oval(x - 8, 3, x + 8, 19, fill=TEXT if an else GEDAEMPFT, outline="")


class TabLeiste(tk.Frame):
    def __init__(self, master, namen, wechsel):
        super().__init__(master, bg=BG)
        self.knoepfe = {}
        for n in namen:
            lbl = tk.Label(self, text=n, bg=BG, fg=GEDAEMPFT, font=(SCHRIFT, 10, "bold"), padx=11, pady=7, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, n=n: wechsel(n))
            self.knoepfe[n] = lbl

    def aktiv(self, name):
        for n, lbl in self.knoepfe.items():
            lbl.config(bg=PANEL if n == name else BG, fg=AKZENT_HELL if n == name else GEDAEMPFT)


def karte(parent, titel, expand=False):
    rahmen = tk.Frame(parent, bg=PANEL, highlightbackground=RAND, highlightthickness=1)
    rahmen.pack(fill="both" if expand else "x", expand=expand, padx=16, pady=5)
    tk.Label(rahmen, text=titel.upper(), bg=PANEL, fg=AKZENT_HELL,
             font=(SCHRIFT, 8, "bold")).pack(anchor="w", padx=14, pady=(9, 3))
    innen = tk.Frame(rahmen, bg=PANEL)
    innen.pack(fill="both" if expand else "x", expand=expand, padx=14, pady=(0, 10))
    return innen


def feld(parent, variable, show="", width=20):
    return tk.Entry(parent, textvariable=variable, show=show, width=width, bg=FELD, fg=TEXT,
                    insertbackground=AKZENT_HELL, relief="flat", font=(SCHRIFT, 10),
                    highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT)


def hinweis(parent, text):
    tk.Label(parent, text=text, bg=PANEL, fg=LEISE, font=(SCHRIFT, 8), wraplength=490,
             justify="left", anchor="w").pack(fill="x", pady=(4, 0))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Twitch Live-Alert")
        self.geometry("560x790")
        self.minsize(540, 730)
        self.configure(bg=BG)
        self.cfg = lade_config()
        self.vars = {}
        self.monitor = None
        self.msgs = queue.Queue()
        self.popups = []
        self.tray = None
        self.live_info = {}
        self.status = ("○  Gestoppt", GEDAEMPFT)
        self.aktueller = None
        self._laedt = False
        self._timer = None
        self._pause_an = False
        self.bauen()
        dunkle_titelleiste(self)
        self.protocol("WM_DELETE_WINDOW", self.schliessen_klick)
        self.after(200, self.log_pumpe)
        self.after(1000, self.sekundentakt)
        self.tray_starten()
        c = self.cfg
        if c["autostart"] and c["client_id"] and c["client_secret"] and c["streamer"]:
            self.umschalten()
        if c["minimiert"] and self.tray:
            self.withdraw()
        if c["update_check"] and not getattr(sys, "frozen", False):
            self.after(3000, self.update_pruefen)

    # ---------- Variablen ----------
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

    # ---------- Aufbau ----------
    def bauen(self):
        self.kopf = tk.Canvas(self, height=84, bg=BG, highlightthickness=0)
        self.kopf.pack(fill="x")
        self.kopf.bind("<Configure>", self.zeichne_kopf)
        namen = ["Übersicht", "Streamer", "Alerts", "Handy", "Verlauf", "System"]
        self.tabs = TabLeiste(self, namen, self.tab_wechseln)
        self.tabs.pack(fill="x", padx=12)
        tk.Frame(self, bg=RAND, height=1).pack(fill="x")
        inhalt = tk.Frame(self, bg=BG)
        inhalt.pack(fill="both", expand=True)
        self.seiten = {}
        for name, fn in zip(namen, (self.seite_uebersicht, self.seite_streamer, self.seite_alerts,
                                    self.seite_handy, self.seite_verlauf, self.seite_system)):
            f = tk.Frame(inhalt, bg=BG)
            self.seiten[name] = f
            fn(f)
        self.tab_wechseln("Übersicht")

    def tab_wechseln(self, name):
        for f in self.seiten.values():
            f.pack_forget()
        self.seiten[name].pack(fill="both", expand=True)
        self.tabs.aktiv(name)
        if name == "Verlauf":
            self.verlauf_aktualisieren()

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

    # --- Tab: Übersicht ---
    def seite_uebersicht(self, f):
        k = karte(f, "Live-Übersicht")
        self.live_box = tk.Frame(k, bg=PANEL)
        self.live_box.pack(fill="x")
        zeile = tk.Frame(f, bg=BG)
        zeile.pack(fill="x", padx=16, pady=6)
        self.btn = Knopf(zeile, "▶  Starten", self.umschalten, primaer=True)
        self.btn.pack(side="left", fill="x", expand=True)
        self.pause_btn = Knopf(zeile, "⏸ Pause", self.pause_klick)
        self.pause_btn.pack(side="left", padx=(8, 0))
        Knopf(zeile, "🔔 Test", self.test).pack(side="left", padx=(8, 0))
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
            zeile = tk.Frame(self.live_box, bg=PANEL, cursor="hand2")
            zeile.pack(fill="x", pady=2)
            tk.Label(zeile, text="●", fg=LIVE if live else "#3a2f66", bg=PANEL, font=(SCHRIFT, 11)).pack(side="left")
            tk.Label(zeile, text=n, fg=TEXT if live else GEDAEMPFT, bg=PANEL,
                     font=(SCHRIFT, 10, "bold")).pack(side="left", padx=8)
            rechts = (f"{info['spiel']}  ·  {fmt_zahl(info['zuschauer'])} Zuschauer" if live
                      else ("offline" if self.laeuft() else "–"))
            tk.Label(zeile, text=rechts, fg=AKZENT_HELL if live else LEISE, bg=PANEL,
                     font=(SCHRIFT, 9)).pack(side="right")
            for w in [zeile] + list(zeile.winfo_children()):
                w.bind("<Button-1>", lambda e, n=n: webbrowser.open(f"https://twitch.tv/{n}"))

    # --- Tab: Streamer ---
    def seite_streamer(self, f):
        sf = karte(f, "Streamer")
        zeile = tk.Frame(sf, bg=PANEL)
        zeile.pack(fill="x")
        self.v_neu = tk.StringVar()
        eintrag = feld(zeile, self.v_neu)
        eintrag.pack(side="left", fill="x", expand=True, ipady=5)
        eintrag.bind("<Return>", lambda e: self.hinzufuegen())
        Knopf(zeile, "＋ Hinzufügen", self.hinzufuegen, primaer=True, klein=True).pack(side="left", padx=(8, 0))
        self.liste = tk.Listbox(sf, height=5, bg=FELD, fg=TEXT, selectbackground=AKZENT, selectforeground="white",
                                relief="flat", highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT,
                                activestyle="none", font=(SCHRIFT, 10), exportselection=False)
        self.liste.pack(fill="x", pady=(8, 6))
        for s in self.cfg["streamer"]:
            self.liste.insert("end", s)
        self.liste.bind("<<ListboxSelect>>", self.auswahl_geaendert)
        Knopf(sf, "Ausgewählten entfernen", self.entfernen, klein=True).pack(anchor="e")

        ef = karte(f, "Einstellungen pro Streamer")
        self.s_titel = tk.Label(ef, text="Wähle oben einen Streamer aus.", bg=PANEL, fg=GEDAEMPFT,
                                font=(SCHRIFT, 10, "bold"), anchor="w")
        self.s_titel.pack(fill="x", pady=(0, 4))
        self.v_s_ton = tk.BooleanVar(value=True)
        self.v_s_sound = tk.StringVar()
        self.v_s_farbe = tk.StringVar()
        self.v_s_spiele = tk.StringVar()
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
        for v in (self.v_s_ton, self.v_s_sound, self.v_s_farbe, self.v_s_spiele):
            v.trace_add("write", self.speichere_pro)
        self.v_s_farbe.trace_add("write", lambda *a: self.zeichne_farben())

    def auswahl_geaendert(self, e=None):
        sel = self.liste.curselection()
        self.aktueller = self.liste.get(sel[0]) if sel else None
        pro = self.cfg["pro_streamer"].get(self.aktueller, {}) if self.aktueller else {}
        self._laedt = True
        self.v_s_ton.set(not pro.get("stumm", False))
        self.v_s_sound.set(pro.get("sound", ""))
        self.v_s_farbe.set(pro.get("farbe", ""))
        self.v_s_spiele.set(pro.get("spiele", ""))
        self._laedt = False
        self.s_titel.config(text=f"Einstellungen für: {self.aktueller}" if self.aktueller
                            else "Wähle oben einen Streamer aus.")
        self.zeichne_farben()

    def speichere_pro(self, *a):
        if self._laedt or not self.aktueller:
            return
        self.cfg["pro_streamer"][self.aktueller] = {
            "stumm": not self.v_s_ton.get(), "sound": self.v_s_sound.get(),
            "farbe": self.v_s_farbe.get(), "spiele": self.v_s_spiele.get().strip()}
        speichere_config(self.cfg)

    def zeichne_farben(self):
        aktuell = self.v_s_farbe.get()
        for farbe, lbl in self.swatches.items():
            lbl.config(highlightbackground=TEXT if farbe == aktuell else PANEL)

    def datei_zeile(self, parent, text, var, testbar=False):
        z = tk.Frame(parent, bg=PANEL)
        z.pack(fill="x", pady=3)
        tk.Label(z, text=text, bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left")
        name = tk.StringVar()

        def aktual(*a):
            name.set(os.path.basename(var.get()) or "Standard-Ton")
        var.trace_add("write", aktual)
        aktual()
        Knopf(z, "✕", lambda: var.set(""), klein=True).pack(side="right", padx=(6, 0))
        Knopf(z, "Datei…", lambda: self.waehle_wav(var), klein=True).pack(side="right")
        if testbar:
            Knopf(z, "▶", lambda: threading.Thread(target=spiele_klang, args=(var.get(),), daemon=True).start(),
                  klein=True).pack(side="right", padx=(0, 6))
        tk.Label(z, textvariable=name, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).pack(side="left", padx=10)

    def waehle_wav(self, var):
        pfad = filedialog.askopenfilename(title="Sounddatei wählen", filetypes=[("WAV-Datei", "*.wav")])
        if pfad:
            var.set(pfad)

    # --- Tab: Alerts ---
    def seite_alerts(self, f):
        k = karte(f, "Ton & Sprache")
        Schalter(k, "Ton abspielen", self.var("ton")).pack(fill="x", pady=2)
        Schalter(k, "Sprachansage („Papaplatte ist live“)", self.var("sprache")).pack(fill="x", pady=2)
        self.datei_zeile(k, "Eigener Ton (.wav)", self.var("sound_datei"), testbar=True)

        k = karte(f, "Ruhezeiten")
        Schalter(k, "Ruhezeit aktiv (kein Ton, keine Sprache)", self.var("ruhe_an")).pack(fill="x", pady=2)
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x", pady=4)
        for txt, key in (("von", "ruhe_von"), ("bis", "ruhe_bis")):
            tk.Label(z, text=txt, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10)).pack(side="left", padx=(0, 6))
            feld(z, self.var(key), width=7).pack(side="left", padx=(0, 16), ipady=3)
        tk.Label(z, text="Format HH:MM, z. B. 23:00", bg=PANEL, fg=LEISE, font=(SCHRIFT, 8)).pack(side="left")

        k = karte(f, "Pop-up")
        Schalter(k, "Profilbild des Streamers zeigen", self.var("profilbild")).pack(fill="x", pady=2)
        Schalter(k, "Vorschaubild des Streams zeigen", self.var("vorschau")).pack(fill="x", pady=2)
        Schalter(k, "Stream automatisch im Browser öffnen", self.var("browser")).pack(fill="x", pady=2)
        if not HAT_PIL:
            hinweis(k, "Für Bilder bitte installieren: python -m pip install pillow")

        k = karte(f, "Zusätzliche Meldungen (nur Pop-up, ohne Ton)")
        Schalter(k, "Spiel gewechselt", self.var("meld_spiel")).pack(fill="x", pady=2)
        Schalter(k, "Titel geändert", self.var("meld_titel")).pack(fill="x", pady=2)
        Schalter(k, "Stream beendet", self.var("meld_offline")).pack(fill="x", pady=2)

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
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x", pady=(0, 8))
        Knopf(z, "⟳ Aktualisieren", self.verlauf_aktualisieren, klein=True).pack(side="left")
        Knopf(z, "Verlauf löschen", self.verlauf_loeschen, klein=True).pack(side="left", padx=8)
        self.vtext = tk.Text(k, state="disabled", wrap="word", bg=FELD, fg=TEXT, relief="flat",
                             highlightthickness=0, font=("Consolas", 9), padx=8, pady=6)
        self.vtext.pack(fill="both", expand=True)
        self.vtext.tag_configure("kopf", foreground=AKZENT_HELL, font=("Consolas", 9, "bold"))

    def verlauf_aktualisieren(self):
        self.vtext.config(state="normal")
        self.vtext.delete("1.0", "end")
        for zeile, tag in verlauf_zeilen():
            self.vtext.insert("end", zeile, tag)
        self.vtext.config(state="disabled")

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
        for i, (txt, key, show) in enumerate((("Client-ID", "client_id", ""), ("Client-Secret", "client_secret", "•"))):
            tk.Label(api, text=txt, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).grid(row=i, column=0, sticky="w", pady=3)
            feld(api, self.var(key), show).grid(row=i, column=1, sticky="ew", padx=(12, 0), pady=3, ipady=4)

        k = karte(f, "Programm")
        z = tk.Frame(k, bg=PANEL)
        z.pack(fill="x", pady=(0, 6))
        tk.Label(z, text="Prüfintervall (Sekunden)", bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left")
        tk.Spinbox(z, from_=15, to=600, increment=15, textvariable=self.var("intervall"), width=5, bg=FELD, fg=TEXT,
                   buttonbackground="#241a47", insertbackground=AKZENT_HELL, relief="flat", font=(SCHRIFT, 10),
                   highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT).pack(side="right", ipady=2)
        schalter = [("Überwachung beim Öffnen automatisch starten", "autostart")]
        if HAT_TRAY:
            schalter += [("Beim Schließen im Infobereich weiterlaufen", "tray"),
                         ("Minimiert starten (nur Symbol neben der Uhr)", "minimiert")]
        schalter.append(("Beim Start nach Updates suchen", "update_check"))
        for txt, key in schalter:
            Schalter(k, txt, self.var(key)).pack(fill="x", pady=2)
        Knopf(k, "⟳  Jetzt nach Updates suchen", lambda: self.update_pruefen(True),
              klein=True).pack(anchor="w", pady=(8, 0))
        hinweis(k, f"Version {VERSION}  ·  Einstellungen: {os.path.basename(CONFIG_DATEI)}")

    # ---------- Status & Pause ----------
    def laeuft(self):
        return bool(self.monitor and self.monitor.is_alive())

    def aktualisiere_status(self):
        rest = ZUSTAND["pause_bis"] - time.time()
        if rest > 0:
            if rest > 3 * 365 * 86400:
                status = ("⏸  Alerts pausiert · bis du fortsetzt", GELB)
            else:
                status = (f"⏸  Alerts pausiert · bis {datetime.fromtimestamp(ZUSTAND['pause_bis']):%H:%M}", GELB)
        elif self.laeuft():
            k = sum(1 for i in self.live_info.values() if i.get("live"))
            status = (f"●  Aktiv · {len(self.cfg['streamer'])} Streamer · {k} live", GRUEN)
        else:
            status = ("○  Gestoppt", GEDAEMPFT)
        if status != self.status:
            self.status = status
            self.zeichne_kopf()
        pausiert = rest > 0
        if pausiert != self._pause_an:
            self._pause_an = pausiert
            self.pause_btn.setze("▶ Fortsetzen" if pausiert else "⏸ Pause", False)

    def sekundentakt(self):
        self.aktualisiere_status()
        self.after(1000, self.sekundentakt)

    def pause_klick(self):
        if ZUSTAND["pause_bis"] > time.time():
            ZUSTAND["pause_bis"] = 0.0
            self.msgs.put("Alerts wieder aktiv.")
            self.aktualisiere_status()
            return
        m = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, activebackground=AKZENT, activeforeground="white")
        for text, sek in (("30 Minuten", 1800), ("1 Stunde", 3600), ("2 Stunden", 7200),
                          ("4 Stunden", 14400), ("Bis ich fortsetze", 10 ** 9)):
            m.add_command(label=text, command=lambda s=sek, t=text: self.pause_setzen(s, t))
        m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def pause_setzen(self, sekunden, text):
        ZUSTAND["pause_bis"] = time.time() + sekunden
        self.msgs.put(f"Alerts pausiert ({text}).")
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
            self.btn.setze("▶  Starten", True)
            self.zeichne_live_liste()
            self.aktualisiere_status()
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
        self.aktualisiere_status()

    def test(self):
        self.sammle_config()
        m = Monitor(self.cfg, self.msgs.put)
        threading.Thread(target=m.melde, args=("live", "twitch", "Testuser", "Just Chatting",
                                               "Das ist eine Test-Benachrichtigung"),
                         kwargs={"zuschauer": 1234, "start": datetime.now(timezone.utc).isoformat(), "test": True},
                         daemon=True).start()

    def test_push(self):
        self.sammle_config()
        threading.Thread(target=sende_push, args=(self.cfg, "live", "Testuser", "twitch",
                                                  "Just Chatting  ·  1.234 Zuschauer", "Das ist ein Test-Push",
                                                  self.msgs.put), daemon=True).start()
        self.msgs.put("Test-Push gesendet (nur wenn mindestens ein Dienst aktiv und ausgefüllt ist).")

    def log_pumpe(self):
        try:
            while True:
                zeile = self.msgs.get_nowait()
                if isinstance(zeile, tuple):
                    if zeile[0] == "popup":
                        self.zeige_popup(zeile[1])
                    elif zeile[0] == "live_status":
                        self.live_info = zeile[1]
                        self.zeichne_live_liste()
                        self.aktualisiere_status()
                    elif zeile[0] == "cmd":
                        self.befehl(zeile[1])
                    elif zeile[0] == "update":
                        self.frage_update(zeile[1], zeile[2])
                    elif zeile[0] == "info":
                        messagebox.showinfo("Twitch Live-Alert", zeile[1])
                    continue
                tag = ("live",) if "LIVE" in zeile else (("warn",) if ("fehlgeschlagen" in zeile or "Fehler" in zeile) else ())
                self.text.config(state="normal")
                self.text.insert("end", f"{datetime.now():%H:%M:%S}  ", "zeit")
                self.text.insert("end", f"{zeile}\n", tag)
                if int(self.text.index("end-1c").split(".")[0]) > 500:
                    self.text.delete("1.0", "100.0")
                self.text.see("end")
                self.text.config(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self.log_pumpe)

    # ---------- Pop-up unten rechts ----------
    def zeige_popup(self, d):
        akzent = d.get("farbe") or AKZENT
        badge, badge_farbe = BADGES.get(d["art"], BADGES["live"])
        profil = tk_bild(d.get("profil"), (54, 54), rund=True)
        vorschau = tk_bild(d.get("vorschau"), (176, 99))
        breite, hoehe = (580 if vorschau else 430), 150
        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.attributes("-alpha", 0.0)
        pop.configure(bg=akzent)  # 1 px leuchtender Rand
        pop.bilder = [profil, vorschau]  # Referenzen, sonst verschwinden die Bilder
        x = self.winfo_screenwidth() - breite - 20
        y = max(self.winfo_screenheight() - hoehe - 60 - len(self.popups) * (hoehe + 10), 0)
        pop.geometry(f"{breite}x{hoehe}+{x + 60}+{y}")
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
        tk.Label(kopf, text=d["name"], bg=PANEL, fg=TEXT, font=(SCHRIFT, 13, "bold")).pack(side="left", padx=(8, 0))
        zu = tk.Label(kopf, text="✕", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10), cursor="hand2")
        zu.pack(side="right")
        zu.bind("<Button-1>", schliessen)
        zu.bind("<Enter>", lambda e: zu.config(fg=TEXT))
        zu.bind("<Leave>", lambda e: zu.config(fg=GEDAEMPFT))
        wrap = breite - 76 - 4 - (200 if vorschau else 0) - 30
        # Knopf zuerst unten verankern, damit er nie aus dem Fenster rutscht
        Knopf(rechts, "▶  Ansehen", oeffnen, primaer=True, klein=True, farbe=akzent).pack(
            side="bottom", anchor="w", pady=(6, 2))
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
                pop.geometry(f"{breite}x{hoehe}+{int(x + 60 * (1 - t))}+{y}")
                pop.attributes("-alpha", 0.97 * t)
            except tk.TclError:
                return
            pop.after(15, einblenden, schritt + 1)

        gesamt = 20000  # Millisekunden bis zum automatischen Schließen

        def fortschritt(rest=gesamt):
            if rest <= 0:
                schliessen()
                return
            balken.delete("all")
            balken.create_rectangle(0, 0, (breite - 2) * rest / gesamt, 3, fill=akzent, outline="")
            pop.after(100, fortschritt, rest - 100)

        einblenden()
        fortschritt()

    # ---------- Updates ----------
    def update_pruefen(self, manuell=False):
        if getattr(sys, "frozen", False):
            if manuell:
                self.msgs.put(("info", "Die .exe kann sich nicht selbst aktualisieren.\n"
                                       "Nutze die .pyw-Variante für automatische Updates."))
            return

        def arbeit():
            try:
                text = hole_update_text()
                neu = finde_version(text)
                if neu and version_tuple(neu) > version_tuple(VERSION):
                    self.msgs.put(("update", neu, text))
                elif manuell:
                    self.msgs.put(("info", f"Du nutzt bereits die neueste Version (v{VERSION})."))
            except (requests.RequestException, UnicodeDecodeError):
                if manuell:
                    self.msgs.put(("info", "Update-Suche fehlgeschlagen – keine Verbindung zu GitHub."))
        threading.Thread(target=arbeit, daemon=True).start()

    def frage_update(self, neu, text):
        if self.state() == "withdrawn":  # Fenster im Infobereich: nicht mit Dialog stören
            self.msgs.put(f"Update v{neu} verfügbar – Fenster öffnen, Tab „System“ → „Jetzt nach Updates suchen“.")
            return
        if not messagebox.askyesno("Update verfügbar",
                                   f"Version {neu} ist verfügbar (du hast v{VERSION}).\n\n"
                                   "Jetzt aktualisieren und neu starten?"):
            return
        pfad = os.path.abspath(__file__)
        try:
            compile(text, "update", "exec")  # Syntax prüfen, bevor etwas überschrieben wird
            if "class App" not in text or "VERSION" not in text:
                raise ValueError("Heruntergeladene Datei wirkt unvollständig.")
            shutil.copy2(pfad, pfad + ".bak")  # Sicherung der alten Version
            tmp = pfad + ".neu"
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                fh.write(text)
            os.replace(tmp, pfad)
        except Exception as e:
            messagebox.showerror("Update fehlgeschlagen", f"Das Update wurde nicht installiert:\n{e}")
            return
        self.sammle_config()
        if self.monitor:
            self.monitor.stop_event.set()
        if self.tray:
            try:
                self.tray.stop()
            except Exception:
                pass
        try:
            subprocess.Popen([sys.executable, pfad])
        except Exception as e:
            messagebox.showerror("Neustart fehlgeschlagen", f"Bitte das Programm von Hand starten:\n{e}")
        self.destroy()

    # ---------- Infobereich (Tray) ----------
    def tray_starten(self):
        if not HAT_TRAY or self.tray:
            return
        menue = pystray.Menu(
            pystray.MenuItem("Fenster öffnen", lambda icon, item: self.msgs.put(("cmd", "zeigen")), default=True),
            pystray.MenuItem("Beenden", lambda icon, item: self.msgs.put(("cmd", "beenden"))),
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
