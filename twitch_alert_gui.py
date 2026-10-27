"""
Twitch Live-Alert – Moon Edition
--------------------------------
Installation:  pip install requests pystray pillow
Starten:       python twitch_alert_gui.py   (oder als .pyw ohne Konsole)
"""

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
from tkinter import messagebox
from datetime import datetime

import requests

try:
    import pystray
    from PIL import Image, ImageDraw
    HAT_TRAY = True
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
LIVE = "#ff4d6d"
MOND = "#f3e9c6"
GRUEN = "#5be3a0"
SCHRIFT = "Segoe UI"

# ---------- Version / Update ----------
# Bei jedem Update die Versionsnummer erhöhen, sonst erkennt das Programm es nicht.
VERSION = "1.1.0"
UPDATE_URL = "https://raw.githubusercontent.com/AwayToMoon/Twitch-Alerts/refs/heads/main/twitch_alert_gui.py"

# Config liegt neben dem Skript bzw. der .exe
BASIS = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))
CONFIG_DATEI = os.path.join(BASIS, "twitch_alert_config.json")

STANDARD = {
    "client_id": "",
    "client_secret": "",
    "streamer": ["papaplatte"],
    "intervall": 60,
    "ton": True,
    "browser": False,
    "autostart": True,   # Überwachung beim Öffnen automatisch starten
    "tray": True,        # beim Schließen im Infobereich weiterlaufen
    "minimiert": False,  # beim Start nur im Infobereich anzeigen
    "update_check": True,  # beim Start nach neuer Version suchen
}


def lade_config():
    try:
        with open(CONFIG_DATEI, "r", encoding="utf-8") as f:
            return {**STANDARD, **json.load(f)}
    except (OSError, ValueError):
        return dict(STANDARD)


def speichere_config(cfg):
    try:
        with open(CONFIG_DATEI, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


class Monitor(threading.Thread):
    """Prüft im Hintergrund, ob Streamer live sind."""

    def __init__(self, cfg, log):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.log = log
        self.stop_event = threading.Event()
        self.token = None

    def hole_token(self):
        r = requests.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": self.cfg["client_id"],
                "client_secret": self.cfg["client_secret"],
                "grant_type": "client_credentials",
            },
            timeout=15,
        )
        r.raise_for_status()
        self.token = r.json()["access_token"]

    def abfrage(self):
        params = [("user_login", n) for n in self.cfg["streamer"]]
        for versuch in range(2):
            if not self.token:
                self.hole_token()
            r = requests.get(
                "https://api.twitch.tv/helix/streams",
                params=params,
                headers={"Client-ID": self.cfg["client_id"], "Authorization": f"Bearer {self.token}"},
                timeout=15,
            )
            if r.status_code == 401 and versuch == 0:
                self.token = None
                continue
            r.raise_for_status()
            return {s["user_login"].lower(): s for s in r.json()["data"]}

    def run(self):
        bereits_live = set()
        self.log("Überwachung gestartet.")
        while not self.stop_event.is_set():
            try:
                aktuell = self.abfrage()
                for login, s in aktuell.items():
                    if login not in bereits_live:
                        alarm(s, self.cfg, self.log)
                bereits_live = set(aktuell)
                self.log(f"Geprüft – live: {', '.join(aktuell) if aktuell else 'niemand'}")
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else "?"
                self.log(f"API-Fehler ({code}) – Client-ID/Secret prüfen.")
                self.token = None
            except requests.RequestException:
                self.log("Netzwerkfehler – nächster Versuch folgt.")
            self.stop_event.wait(max(15, int(self.cfg["intervall"])))
        self.log("Überwachung gestoppt.")


def spiele_ton():
    """Kurze Tonfolge, unabhängig vom Windows-Soundschema."""
    try:
        import winsound
        for frequenz, dauer in ((880, 150), (1100, 150), (1320, 300)):
            winsound.Beep(frequenz, dauer)
    except Exception:
        pass


def alarm(stream, cfg, log):
    name = stream["user_name"]
    spiel = stream.get("game_name") or "Unbekannt"
    titel = stream.get("title", "")
    log(f"🔴 {name} ist LIVE – {spiel}")
    # Pop-up wird im Hauptthread angezeigt (siehe App.log_pumpe)
    log(("popup", name, spiel, titel, stream["user_login"]))
    if cfg["ton"]:
        threading.Thread(target=spiele_ton, daemon=True).start()
    if cfg["browser"]:
        webbrowser.open(f"https://twitch.tv/{stream['user_login']}")


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
    def __init__(self, master, text, aktion, primaer=False, klein=False):
        super().__init__(master, text=text, font=(SCHRIFT, 9 if klein else 10, "bold"),
                         padx=12 if klein else 18, pady=4 if klein else 9, cursor="hand2")
        self.aktion = aktion
        self.setze(text, primaer)
        self.bind("<Enter>", lambda e: self.config(bg=self.hover))
        self.bind("<Leave>", lambda e: self.config(bg=self.normal))
        self.bind("<Button-1>", lambda e: self.aktion())

    def setze(self, text, primaer):
        self.normal = AKZENT if primaer else "#241a47"
        self.hover = "#b18cff" if primaer else "#32245f"
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
        farbe = AKZENT if an else "#2a2050"
        c.create_oval(1, 1, 21, 21, fill=farbe, outline=farbe)
        c.create_oval(21, 1, 41, 21, fill=farbe, outline=farbe)
        c.create_rectangle(11, 1, 31, 21, fill=farbe, outline=farbe)
        x = 31 if an else 11
        c.create_oval(x - 8, 3, x + 8, 19, fill=TEXT if an else GEDAEMPFT, outline="")


def karte(parent, titel, expand=False):
    rahmen = tk.Frame(parent, bg=PANEL, highlightbackground=RAND, highlightthickness=1)
    rahmen.pack(fill="both" if expand else "x", expand=expand, padx=16, pady=6)
    tk.Label(rahmen, text=titel.upper(), bg=PANEL, fg=AKZENT_HELL,
             font=(SCHRIFT, 8, "bold")).pack(anchor="w", padx=14, pady=(10, 4))
    innen = tk.Frame(rahmen, bg=PANEL)
    innen.pack(fill="both" if expand else "x", expand=expand, padx=14, pady=(0, 12))
    return innen


def feld(parent, variable, show="", width=20):
    return tk.Entry(parent, textvariable=variable, show=show, width=width, bg=FELD, fg=TEXT,
                    insertbackground=AKZENT_HELL, relief="flat", font=(SCHRIFT, 10),
                    highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Twitch Live-Alert")
        self.geometry("480x820")
        self.minsize(460, 720)
        self.configure(bg=BG)
        self.cfg = lade_config()
        self.monitor = None
        self.msgs = queue.Queue()
        self.popups = []
        self.tray = None
        self.status = ("○  Pausiert", GEDAEMPFT)
        self.bauen()
        dunkle_titelleiste(self)
        self.protocol("WM_DELETE_WINDOW", self.schliessen_klick)
        self.after(200, self.log_pumpe)
        self.tray_starten()
        c = self.cfg
        if c["autostart"] and c["client_id"] and c["client_secret"] and c["streamer"]:
            self.umschalten()
        if c["minimiert"] and self.tray:
            self.withdraw()
        if c["update_check"] and not getattr(sys, "frozen", False):
            self.after(3000, self.update_pruefen)

    # ---------- Oberfläche ----------
    def bauen(self):
        self.kopf = tk.Canvas(self, height=96, bg=BG, highlightthickness=0)
        self.kopf.pack(fill="x")
        self.kopf.bind("<Configure>", self.zeichne_kopf)

        api = karte(self, "Twitch-API  ·  dev.twitch.tv/console")
        api.columnconfigure(1, weight=1)
        self.v_id = tk.StringVar(value=self.cfg["client_id"])
        self.v_secret = tk.StringVar(value=self.cfg["client_secret"])
        for i, (txt, var, show) in enumerate((("Client-ID", self.v_id, ""), ("Client-Secret", self.v_secret, "•"))):
            tk.Label(api, text=txt, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9)).grid(row=i, column=0, sticky="w", pady=3)
            feld(api, var, show).grid(row=i, column=1, sticky="ew", padx=(12, 0), pady=3, ipady=4)

        sf = karte(self, "Streamer")
        zeile = tk.Frame(sf, bg=PANEL)
        zeile.pack(fill="x")
        self.v_neu = tk.StringVar()
        eintrag = feld(zeile, self.v_neu)
        eintrag.pack(side="left", fill="x", expand=True, ipady=5)
        eintrag.bind("<Return>", lambda e: self.hinzufuegen())
        Knopf(zeile, "＋ Hinzufügen", self.hinzufuegen, primaer=True, klein=True).pack(side="left", padx=(8, 0))
        self.liste = tk.Listbox(sf, height=4, bg=FELD, fg=TEXT, selectbackground=AKZENT, selectforeground="white",
                                relief="flat", highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT,
                                activestyle="none", font=(SCHRIFT, 10))
        self.liste.pack(fill="x", pady=(8, 6))
        for s in self.cfg["streamer"]:
            self.liste.insert("end", s)
        Knopf(sf, "Ausgewählten entfernen", self.entfernen, klein=True).pack(anchor="e")

        opt = karte(self, "Optionen")
        zeile = tk.Frame(opt, bg=PANEL)
        zeile.pack(fill="x", pady=(0, 6))
        tk.Label(zeile, text="Prüfintervall (Sekunden)", bg=PANEL, fg=TEXT, font=(SCHRIFT, 10)).pack(side="left")
        self.v_int = tk.IntVar(value=self.cfg["intervall"])
        tk.Spinbox(zeile, from_=15, to=600, increment=15, textvariable=self.v_int, width=5, bg=FELD, fg=TEXT,
                   buttonbackground="#241a47", insertbackground=AKZENT_HELL, relief="flat", font=(SCHRIFT, 10),
                   highlightthickness=1, highlightbackground=RAND, highlightcolor=AKZENT).pack(side="right", ipady=2)
        self.v_ton = tk.BooleanVar(value=self.cfg["ton"])
        self.v_browser = tk.BooleanVar(value=self.cfg["browser"])
        self.v_auto = tk.BooleanVar(value=self.cfg["autostart"])
        self.v_tray = tk.BooleanVar(value=self.cfg["tray"])
        self.v_min = tk.BooleanVar(value=self.cfg["minimiert"])
        self.v_upd = tk.BooleanVar(value=self.cfg["update_check"])
        schalter = [("Ton abspielen", self.v_ton),
                    ("Stream im Browser öffnen", self.v_browser),
                    ("Überwachung beim Öffnen automatisch starten", self.v_auto),
                    ("Beim Start nach Updates suchen", self.v_upd)]
        if HAT_TRAY:
            schalter += [("Beim Schließen im Infobereich weiterlaufen", self.v_tray),
                         ("Minimiert starten (nur Symbol neben der Uhr)", self.v_min)]
        for txt, var in schalter:
            Schalter(opt, txt, var).pack(fill="x", pady=3)
        Knopf(opt, "⟳  Jetzt nach Updates suchen", lambda: self.update_pruefen(True),
              klein=True).pack(anchor="w", pady=(8, 0))

        knoepfe = tk.Frame(self, bg=BG)
        knoepfe.pack(fill="x", padx=16, pady=8)
        self.btn = Knopf(knoepfe, "▶  Überwachung starten", self.umschalten, primaer=True)
        self.btn.pack(side="left", fill="x", expand=True)
        Knopf(knoepfe, "🔔 Test", self.test).pack(side="left", padx=(8, 0))

        lf = karte(self, "Protokoll", expand=True)
        self.text = tk.Text(lf, height=5, state="disabled", wrap="word", bg=FELD, fg=GEDAEMPFT, relief="flat",
                            highlightthickness=0, font=("Consolas", 9), padx=8, pady=6)
        self.text.pack(fill="both", expand=True)
        self.text.tag_configure("zeit", foreground="#5b4f87")
        self.text.tag_configure("live", foreground=LIVE)

    def zeichne_kopf(self, event=None):
        c = self.kopf
        breite = max(c.winfo_width(), 460)
        c.delete("all")
        zeichne_sterne(c, [(breite - 40, 24, 2), (breite - 90, 52, 1.5), (breite - 150, 20, 1.5),
                           (breite - 200, 70, 2), (breite - 250, 38, 1), (breite - 310, 16, 1.5)])
        zeichne_mond(c, 52, 48, 22, BG)
        c.create_text(92, 38, text="Twitch Live-Alert", anchor="w", fill=TEXT, font=(SCHRIFT, 17, "bold"))
        c.create_text(92, 66, text=self.status[0], anchor="w", fill=self.status[1], font=(SCHRIFT, 10))
        c.create_text(breite - 16, 84, text=f"v{VERSION}", anchor="e", fill="#5b4f87", font=(SCHRIFT, 8))

    def setze_status(self, aktiv):
        n = self.liste.size()
        self.status = (f"●  Überwachung aktiv · {n} Streamer", GRUEN) if aktiv else ("○  Pausiert", GEDAEMPFT)
        self.zeichne_kopf()

    def laeuft(self):
        return bool(self.monitor and self.monitor.is_alive())

    # ---------- Aktionen ----------
    def hinzufuegen(self):
        name = self.v_neu.get().strip().lower().lstrip("@")
        if name and name not in self.liste.get(0, "end"):
            self.liste.insert("end", name)
        self.v_neu.set("")
        self.sammle_config()
        self.setze_status(self.laeuft())

    def entfernen(self):
        for i in reversed(self.liste.curselection()):
            self.liste.delete(i)
        self.sammle_config()
        self.setze_status(self.laeuft())

    def sammle_config(self):
        try:
            intervall = int(self.v_int.get())
        except (tk.TclError, ValueError):
            intervall = 60
        neu = {
            "client_id": self.v_id.get().strip(),
            "client_secret": self.v_secret.get().strip(),
            "streamer": list(self.liste.get(0, "end")),
            "intervall": intervall,
            "ton": self.v_ton.get(),
            "browser": self.v_browser.get(),
            "autostart": self.v_auto.get(),
            "tray": self.v_tray.get(),
            "minimiert": self.v_min.get(),
            "update_check": self.v_upd.get(),
        }
        # In-place aktualisieren, damit die laufende Überwachung Änderungen sofort übernimmt
        self.cfg.clear()
        self.cfg.update(neu)
        speichere_config(self.cfg)

    def umschalten(self):
        if self.laeuft():
            self.monitor.stop_event.set()
            self.btn.setze("▶  Überwachung starten", True)
            self.setze_status(False)
            return
        self.sammle_config()
        if not self.cfg["client_id"] or not self.cfg["client_secret"]:
            messagebox.showwarning("Fehlt noch", "Bitte Client-ID und Client-Secret eintragen.")
            return
        if not self.cfg["streamer"]:
            messagebox.showwarning("Fehlt noch", "Bitte mindestens einen Streamer hinzufügen.")
            return
        self.monitor = Monitor(self.cfg, self.msgs.put)
        self.monitor.start()
        self.btn.setze("■  Stoppen", False)
        self.setze_status(True)

    def test(self):
        self.sammle_config()
        alarm({"user_name": "Testuser", "user_login": "twitch", "game_name": "Just Chatting",
               "title": "Das ist eine Test-Benachrichtigung"},
              {**self.cfg, "browser": False}, self.msgs.put)

    def log_pumpe(self):
        try:
            while True:
                zeile = self.msgs.get_nowait()
                if isinstance(zeile, tuple):
                    if zeile[0] == "popup":
                        self.zeige_popup(*zeile[1:])
                    elif zeile[0] == "cmd":
                        self.befehl(zeile[1])
                    elif zeile[0] == "update":
                        self.frage_update(zeile[1], zeile[2])
                    elif zeile[0] == "info":
                        messagebox.showinfo("Twitch Live-Alert", zeile[1])
                    continue
                self.text.config(state="normal")
                self.text.insert("end", f"{datetime.now():%H:%M:%S}  ", "zeit")
                self.text.insert("end", f"{zeile}\n", ("live",) if "LIVE" in zeile else ())
                if int(self.text.index("end-1c").split(".")[0]) > 500:
                    self.text.delete("1.0", "100.0")
                self.text.see("end")
                self.text.config(state="disabled")
        except queue.Empty:
            pass
        self.after(200, self.log_pumpe)

    # ---------- Pop-up unten rechts ----------
    def zeige_popup(self, name, spiel, titel, login):
        breite, hoehe = 400, 128
        pop = tk.Toplevel(self)
        pop.overrideredirect(True)
        pop.attributes("-topmost", True)
        pop.attributes("-alpha", 0.0)
        pop.configure(bg=AKZENT)  # 1 px leuchtender Rand
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
            webbrowser.open(f"https://twitch.tv/{login}")
            schliessen()

        innen = tk.Frame(pop, bg=PANEL)
        innen.pack(fill="both", expand=True, padx=1, pady=1)

        balken = tk.Canvas(innen, height=3, bg=PANEL, highlightthickness=0)
        balken.pack(side="bottom", fill="x")
        tk.Frame(innen, bg=AKZENT, width=4).pack(side="left", fill="y")

        mond = tk.Canvas(innen, width=76, bg=PANEL, highlightthickness=0)
        mond.pack(side="left", fill="y")
        zeichne_sterne(mond, [(14, 22, 1.5), (62, 30, 1), (58, 100, 1.5), (16, 96, 1)])
        zeichne_mond(mond, 38, 60, 19, PANEL)

        rechts = tk.Frame(innen, bg=PANEL)
        rechts.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=(10, 4))
        kopf = tk.Frame(rechts, bg=PANEL)
        kopf.pack(fill="x")
        tk.Label(kopf, text=" LIVE ", bg=LIVE, fg="white", font=(SCHRIFT, 8, "bold")).pack(side="left")
        tk.Label(kopf, text=name, bg=PANEL, fg=TEXT, font=(SCHRIFT, 13, "bold")).pack(side="left", padx=(8, 0))
        zu = tk.Label(kopf, text="✕", bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 10), cursor="hand2")
        zu.pack(side="right")
        zu.bind("<Button-1>", schliessen)
        zu.bind("<Enter>", lambda e: zu.config(fg=TEXT))
        zu.bind("<Leave>", lambda e: zu.config(fg=GEDAEMPFT))
        tk.Label(rechts, text=spiel, bg=PANEL, fg=AKZENT_HELL, font=(SCHRIFT, 10, "bold"),
                 anchor="w").pack(fill="x", pady=(4, 0))
        kurz = titel if len(titel) <= 62 else titel[:60] + "…"
        tk.Label(rechts, text=kurz, bg=PANEL, fg=GEDAEMPFT, font=(SCHRIFT, 9), anchor="w",
                 justify="left", wraplength=breite - 120).pack(fill="x")
        Knopf(rechts, "▶  Ansehen", oeffnen, primaer=True, klein=True).pack(anchor="w", pady=(8, 0))

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
            balken.create_rectangle(0, 0, (breite - 2) * rest / gesamt, 3, fill=AKZENT, outline="")
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
            self.msgs.put(f"Update v{neu} verfügbar – Fenster öffnen und „Jetzt nach Updates suchen“ klicken.")
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
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(text)
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
