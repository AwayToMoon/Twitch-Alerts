<div align="center">

# 🌙 Twitch Live-Alert

**Dein Mond-Wächter für Twitch.**<br>
Ein Windows-Programm, das dich benachrichtigt, sobald deine Lieblings-Streamer live gehen – im dunklen Schwarz-Lila-Mond-Design.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![Twitch API](https://img.shields.io/badge/Twitch-API-9146FF?style=for-the-badge&logo=twitch&logoColor=white)
![Sprachen](https://img.shields.io/badge/Sprachen-Deutsch%20%7C%20English-9d6bff?style=for-the-badge)

<br>

<img src="screenshots/uebersicht.png" alt="Übersicht" width="330">&nbsp;&nbsp;&nbsp;<img src="screenshots/popup.png" alt="Pop-up-Benachrichtigungen" width="400">

</div>

---

## ✨ Funktionen

| | |
|---|---|
| 🔔 **Live-Alerts** | Pop-up mit Profilbild, Vorschaubild, Spiel, Titel, Zuschauerzahl und Live-Dauer |
| ★ **Favoriten** | Eigener Ton (Fanfare) und ein Pop-up, das stehen bleibt, bis du es wegklickst |
| ⏰ **„Später“-Knopf** | Erinnert dich nach X Minuten noch einmal, falls der Stream dann noch läuft |
| 📍 **Pop-up nach Wunsch** | Ecke, Monitor und Anzeigedauer frei wählbar |
| 🎮 **Spielmodus** | Bei Vollbild kommt kein störendes Pop-up, nur Ton und Push. Das Pop-up folgt danach |
| 📺 **Live-Übersicht & Mini-Fenster** | Wer ist live, mit Spiel und Zuschauern. Auf Wunsch als kleines Fenster, das immer oben bleibt |
| 🎛️ **Pro Streamer einstellbar** | Eigener Ton, eigene Farbe, Spielfilter („nur bei GTA melden“) |
| ⬇️ **Gefolgte Kanäle importieren** | Einmal bei Twitch anmelden, und deine Follows landen in der Liste |
| 🗓️ **Stream-Zeitplan** | „Papaplatte startet vermutlich in 15 Minuten“, wenn der Streamer einen Zeitplan veröffentlicht |
| ⏸️ **Pause & Ruhezeiten** | Alerts für eine Weile oder nachts stummschalten |
| 🔊 **Ton & Sprache** | Eigene `.wav`-Dateien und Sprachansage („Papaplatte ist live“) |
| 📲 **Handy-Push** | Über [ntfy](https://ntfy.sh), Discord oder Telegram |
| 📊 **Verlauf mit Diagrammen** | Live-Stunden pro Woche, typische Startzeiten, Export als CSV |
| 🎨 **Designs & Sprachen** | „Mond“, „Sonnenuntergang“ und „Hell“, Oberfläche auf Deutsch und Englisch |
| 💾 **Sichern & Übertragen** | Einstellungen exportieren und auf einem anderen PC wieder einlesen |
| 🔑 **Zugang testen** | Ein Klick zeigt, ob Client-ID und Secret stimmen, und sagt klar, was falsch ist |
| 🪟 **Infobereich** | Läuft unsichtbar neben der Uhr weiter, auf Wunsch minimiert gestartet |
| 🔄 **Updates** | Prüft beim Start auf neue Versionen und zeigt, was neu ist |

---

## 📥 Download (ohne Python)

Du willst nichts installieren? Dann nimm die fertige Windows-Version:

1. Öffne die **[Release-Seite](https://github.com/AwayToMoon/Twitch-Alerts/releases/latest)**.
2. Lade unter **Assets** die Datei **`TwitchLiveAlert.exe`** herunter.
3. Lege sie in einen **eigenen Ordner**, zum Beispiel `C:\TwitchAlert`. Dort speichert sie ihre Einstellungen.
4. Starte sie per Doppelklick und richte den Twitch-Zugang ein (Schritt 4 und 5 unten).

> ⚠️ **Windows-Warnung:** Die Datei ist nicht digital signiert. Windows zeigt deshalb beim ersten Start „Der Computer wurde durch Windows geschützt“. Klicke auf **Weitere Informationen → Trotzdem ausführen**. Manche Virenscanner schlagen bei solchen Programmen auch fälschlich an. Wer dem nicht traut, nutzt die Python-Variante, der Quellcode ist offen einsehbar.

---

## 🚀 Schnellstart (mit Python)

### 1. Python installieren

Lade Python von [python.org](https://www.python.org/downloads/) herunter (empfohlen: **3.10 oder neuer**).
Setze bei der Installation den Haken bei **„Add Python to PATH“**.

### 2. Programm herunterladen

Lade die Datei [`twitch_alert_gui.py`](twitch_alert_gui.py) herunter und lege sie in einen eigenen Ordner, zum Beispiel `C:\TwitchAlert`.

### 3. Pakete installieren

Öffne die Eingabeaufforderung und gib ein:

```bash
python -m pip install requests pillow pystray
```

> `pillow` und `pystray` sind optional. Ohne sie fehlen die Bilder im Pop-up und das Symbol im Infobereich, alles andere funktioniert.

### 4. Twitch-API-Zugang holen

Twitch verlangt für die Abfrage einen kostenlosen Zugang:

1. Gehe auf die [Twitch Developer Console](https://dev.twitch.tv/console) und logge dich ein (dafür muss die **Zwei-Faktor-Authentifizierung** aktiviert sein).
2. Klicke auf **„Anwendung registrieren“**.
3. Trage ein:
   - **Name:** beliebig, aber einzigartig (zum Beispiel `MeinLiveAlert123`)
   - **OAuth-Redirect-URL:** `http://localhost`
   - **Kategorie:** `Application Integration`
4. Öffne die Anwendung, kopiere die **Client-ID** und klicke auf **„Neues Secret“**, um das **Client Secret** zu erzeugen.

### 5. Starten

```bash
python twitch_alert_gui.py
```

Trage im Tab **System** Client-ID und Client Secret ein und klicke auf **🔑 Zugang testen**. Füge dann im Tab **Streamer** deine Lieblings-Streamer hinzu (oder importiere deine Follows) und klicke auf **▶ Starten**. Mit **🔔 Test** prüfst du, ob alles funktioniert.

---

## 🖥️ Ohne Konsolenfenster und mit Windows starten

1. Benenne `twitch_alert_gui.py` in **`twitch_alert_gui.pyw`** um (die Endung `.pyw` startet ohne schwarzes Fenster).
2. Finde den Pfad zu `pythonw.exe` heraus:
   ```bash
   where pythonw
   ```
3. Erstelle eine Verknüpfung (Rechtsklick auf den Desktop → Neu → Verknüpfung) mit diesem Ziel, angepasst an deine Pfade:
   ```
   "C:\Pfad\zu\pythonw.exe" "C:\TwitchAlert\twitch_alert_gui.pyw"
   ```
4. Für den **Autostart** kopierst du die Verknüpfung in den Autostart-Ordner (`Win + R`, dann `shell:startup`).
5. Optional: Gib der Verknüpfung das Mond-Icon (`twitch_alert.ico`): Rechtsklick → **Eigenschaften** → **Anderes Symbol…**.

> 💡 Setze in den Einstellungen **„Minimiert starten“**, dann läuft das Programm nach jedem Windows-Start unsichtbar im Infobereich.

---

## 📖 Bedienung

Das Programm hat sieben Tabs:

| Tab | Was du dort findest |
|---|---|
| **Übersicht** | Live-Liste, Start/Stopp, Pause, Test, Mini-Fenster und das Protokoll |
| **Streamer** | Streamer hinzufügen, entfernen oder von Twitch importieren, Einstellungen pro Streamer |
| **Alerts** | Ton, Sprache, Ruhezeiten, Zusatzmeldungen und Zeitplan-Hinweise |
| **Pop-up** | Ecke, Monitor, Dauer, Bilder, Spielmodus und „Später“-Erinnerung |
| **Handy** | Push-Benachrichtigungen aufs Smartphone |
| **Verlauf** | Liste, Diagramme und CSV-Export |
| **System** | API-Zugang, Intervall, Autostart, Designs, Sprache, Sichern und Updates |

Alle Änderungen gelten **sofort**, ein Neustart ist nur bei Design und Sprache nötig.

<details>
<summary><b>📸 Weitere Screenshots</b></summary>

<br>

<table>
<tr>
<td><img src="screenshots/streamer.png" alt="Streamer" width="300"></td>
<td><img src="screenshots/alerts.png" alt="Alerts" width="300"></td>
<td><img src="screenshots/popup_einstellungen.png" alt="Pop-up-Einstellungen" width="300"></td>
</tr>
<tr>
<td><img src="screenshots/handy.png" alt="Handy" width="300"></td>
<td><img src="screenshots/verlauf.png" alt="Verlauf mit Diagramm" width="300"></td>
<td><img src="screenshots/system.png" alt="System" width="300"></td>
</tr>
</table>

**Designs:** „Hell“ und „Sonnenuntergang“ (neben dem Standard „Mond“)

<img src="screenshots/designs.png" alt="Designs" width="620">

*Beispieldaten, aufgenommen in einer Testumgebung.*

</details>

---

## 🧭 Funktionen im Detail

<details>
<summary><b>★ Favoriten</b></summary>

Wähle im Tab **Streamer** einen Namen und schalte **★ Favorit** ein. Favoriten bekommen eine Fanfare (oder eine eigene `.wav` unter **Alerts**), ein goldenes Pop-up mit Stern, das **stehen bleibt, bis du es schließt**, und einen Stern in der Live-Liste.
</details>

<details>
<summary><b>🎛️ Einstellungen pro Streamer</b></summary>

- **Ton & Sprache** für diesen Streamer an- oder abschalten
- einen **eigenen Ton** (`.wav`)
- die **Farbe** des Pop-ups
- einen **Spielfilter**, zum Beispiel `GTA, Just Chatting`. Es wird nur gemeldet, wenn das aktuelle Spiel einen dieser Begriffe enthält. Leer bedeutet: immer melden.
</details>

<details>
<summary><b>⏰ „Später“-Knopf</b></summary>

Im Live-Pop-up erinnert dich **⏰ 10 min** (einstellbar im Tab **Pop-up**) nach der gewählten Zeit noch einmal, aber nur, wenn der Streamer dann immer noch live ist.
</details>

<details>
<summary><b>🎮 Spielmodus</b></summary>

Erkennt das Programm ein Fenster im **Vollbild** (Spiel, Video), wird das Pop-up nicht gezeigt, damit es dich nicht aus dem Spiel wirft. Ton und Push kommen weiterhin. Sobald du das Vollbild verlässt, erscheinen die zurückgestellten Pop-ups. Das lässt sich im Tab **Pop-up** abschalten.
</details>

<details>
<summary><b>⏸️ Pause</b></summary>

Über **⏸ Pause** schaltest du die Alerts für 30 Minuten, 1, 2 oder 4 Stunden oder bis zum Fortsetzen ab. Ist ein Streamer nach der Pause noch live, bekommst du die Meldung dann nachträglich.
</details>

<details>
<summary><b>⬇️ Gefolgte Kanäle importieren</b></summary>

Im Tab **Streamer** auf **⬇ Gefolgte Kanäle importieren** klicken. Es öffnet sich der Browser, du bestätigst die Anmeldung bei Twitch, und danach wählst du aus, welche Kanäle überwacht werden sollen.

- Das Programm bekommt nur das Recht, **deine Follows zu lesen**. Der Zugangsschlüssel wird **nicht gespeichert**.
- Dafür muss die **Redirect-URL** in der Twitch-Console **exakt** mit der im Tab **System** übereinstimmen (Standard: `http://localhost`).
- Ist Port 80 bei dir belegt, trage in der Twitch-Console zum Beispiel `http://localhost:3000` ein und dieselbe Adresse im Tab **System**.
</details>

<details>
<summary><b>🗓️ Stream-Zeitplan</b></summary>

Unter **Alerts → Stream startet bald** schaltest du ein, dass du kurz vor einem geplanten Stream benachrichtigt wirst (Vorwarnzeit einstellbar). Das funktioniert nur bei Streamern, die auf Twitch einen **Zeitplan veröffentlicht** haben. Der nächste Stream steht dann auch in der Live-Liste.
</details>

<details>
<summary><b>🗗 Mini-Fenster</b></summary>

Ein kleines, halbtransparentes Fenster, das **immer im Vordergrund** zeigt, wer live ist. Du kannst es am Kopf verschieben, ein Klick auf einen Namen öffnet den Stream. Ein- und ausschalten über **🗗 Mini** in der Übersicht.
</details>

<details>
<summary><b>📊 Verlauf</b></summary>

Das Programm merkt sich jeden Stream, den es live gesehen hat. Im Tab **Verlauf** wechselst du zwischen **Liste**, **Wochen** (Live-Stunden pro Woche) und **Uhrzeiten** (wann Streamer meist live gehen). Ein Filter zeigt einzelne Streamer, und **CSV exportieren** öffnet sich direkt in Excel.
</details>

<details>
<summary><b>💾 Einstellungen sichern und übertragen</b></summary>

Im Tab **System** kannst du alle Einstellungen als Datei exportieren und auf einem anderen PC importieren. Beim Export entscheidest du, ob **Zugangsdaten** (Client Secret, Push-Adressen) mitgehen. Wähle „Nein“, wenn du die Datei weitergeben willst.
</details>

---

## 📲 Handy-Push einrichten

<details>
<summary><b>ntfy</b> – am einfachsten, ohne Konto</summary>

1. Installiere die App **ntfy** auf deinem Handy.
2. Abonniere dort ein Topic, zum Beispiel `mein-twitch-alert-x7k2q9`.
3. Trage dasselbe Topic im Tab **Handy** ein und aktiviere den Schalter.

Wähle einen **langen, schwer zu erratenden Namen**, denn jeder, der ihn kennt, kann mitlesen.
</details>

<details>
<summary><b>Discord</b></summary>

Servereinstellungen → Integrationen → Webhooks → neuen Webhook erstellen → URL kopieren und im Tab **Handy** einfügen.
</details>

<details>
<summary><b>Telegram</b></summary>

1. Erstelle einen Bot bei [@BotFather](https://t.me/BotFather) und kopiere den **Bot-Token**.
2. Schreibe dem Bot einmal eine Nachricht.
3. Trage Token und deine **Chat-ID** im Tab **Handy** ein.
</details>

Mit **📲 Test-Push senden** prüfst du die Einrichtung.

---

## 🔄 Updates

Beim Start vergleicht das Programm seine Versionsnummer mit der Datei in diesem Repository. Gibt es eine neuere Version, zeigt es **was neu ist** und fragt dich:

1. Die neue Datei wird heruntergeladen und auf Fehler geprüft.
2. Die alte Version bleibt als `twitch_alert_gui.pyw.bak` erhalten.
3. Das Programm startet automatisch neu.

Manuell suchst du im Tab **System** über **⟳ Jetzt nach Updates suchen**.

> ℹ️ Das automatische Ersetzen funktioniert nur bei `.py`/`.pyw`. Die `.exe` weist dich bei einer neuen Version stattdessen darauf hin und öffnet die Download-Seite.
> Wenn du dieses Projekt **forkst**, ändere in der Datei die Konstanten `UPDATE_URL` und `RELEASES_URL` auf dein eigenes Repository.

---

## 🔒 Datenschutz und Sicherheit

- Deine Einstellungen liegen **nur lokal** im Programmordner (`twitch_alert_config.json`). Dort stehen auch Client Secret und Push-Zugangsdaten.
- **Lade diese Datei niemals auf GitHub hoch** und gib sie nicht weiter. Das Gleiche gilt für exportierte Einstellungsdateien mit Zugangsdaten.
- Es werden keine Daten an Dritte gesendet, außer an die Dienste, die du selbst aktivierst: Twitch (Abfrage, Bilder und optional deine Follows), GitHub (Update-Check) und optional ntfy, Discord oder Telegram.

---

## 🛠️ Fehlerbehebung

<details>
<summary><b>Ich bekomme keinen Alert</b></summary>

- Klicke auf **🔔 Test**. Kommt das Pop-up, funktioniert die Anzeige.
- Klicke im Tab **System** auf **🔑 Zugang testen**. Das sagt dir, ob Client-ID oder Secret falsch ist.
- Der Streamer muss mit seinem **Login-Namen** eingetragen sein (der Teil aus `twitch.tv/NAME`).
- Prüfe, ob die Alerts per **Pause** abgeschaltet sind (oben im Fenster steht dann „pausiert“).
- Prüfe einen eventuellen **Spielfilter** beim Streamer.
- Bist du im **Vollbild**? Dann wartet das Pop-up bis zum Ende (Spielmodus).
</details>

<details>
<summary><b>Der Ton fehlt</b></summary>

- Ist **Ton abspielen** im Tab **Alerts** an?
- Ist gerade eine **Ruhezeit** aktiv, oder ist der Ton für diesen Streamer abgeschaltet?
- Prüfe die Windows-Lautstärke und das Standard-Ausgabegerät.
</details>

<details>
<summary><b>Der Follow-Import klappt nicht</b></summary>

- Die **Redirect-URL** in der Twitch-Console muss **exakt** der im Tab **System** entsprechen (inklusive Port und ohne Schrägstrich am Ende).
- Meldet das Programm, dass der **Port belegt** ist, nutze eine andere Adresse wie `http://localhost:3000` und trage sie an beiden Stellen ein.
- Ein Firewall-Hinweis von Windows kann erscheinen. Erlaube den Zugriff nur für private Netzwerke.
</details>

<details>
<summary><b>Kein Symbol im Infobereich / keine Bilder im Pop-up</b></summary>

Installiere die optionalen Pakete:

```bash
python -m pip install pillow pystray
```
</details>

<details>
<summary><b><code>pip</code> wird nicht gefunden</b></summary>

Nutze immer die Form `python -m pip install ...`. Dann wird garantiert dasselbe Python verwendet, mit dem du das Programm startest.
</details>

<details>
<summary><b>Doppelklick auf die <code>.pyw</code> öffnet ein Auswahlmenü</b></summary>

Windows kennt die Endung noch nicht. Nutze die Verknüpfung aus dem Abschnitt „Ohne Konsolenfenster und mit Windows starten“.
</details>

---

## 📁 Dateien

| Datei | Zweck |
|---|---|
| `twitch_alert_gui.py` | Das Programm (alles in einer Datei) |
| `twitch_alert.ico` | Das Mond-Icon für Verknüpfungen und die `.exe` |
| `twitch_alert_config.json` | Deine Einstellungen, wird automatisch erzeugt |
| `twitch_alert_verlauf.json` | Der Stream-Verlauf, wird automatisch erzeugt |
| `twitch_alert_gui.pyw.bak` | Sicherung der Vorversion nach einem Update |

### Optional: als `.exe` bauen

```bash
python -m pip install pyinstaller
python -m PyInstaller --clean --onefile --noconsole --name TwitchLiveAlert --icon twitch_alert.ico --hidden-import pystray._win32 twitch_alert_gui.py
```

Die Datei `twitch_alert.ico` (das Mond-Symbol) muss dafür im selben Ordner wie das Programm liegen.

Die fertige `TwitchLiveAlert.exe` liegt danach im Ordner `dist`.

**Als Release veröffentlichen:** Im Repository unter **Releases → Create a new release** eine Versionsnummer wie `v2.2.0` vergeben (**Create new tag**), die `.exe` unten bei „Attach binaries“ hineinziehen und auf **Publish release** klicken.

---

## 🇬🇧 English summary

**Twitch Live-Alert** is a Windows desktop app that notifies you when your favorite streamers go live. It has a dark purple “moon” design (plus “Sunset” and “Light” themes) and an English interface (**System → Language**).

Highlights: pop-ups with profile and preview image, favorites (★) that stay until clicked, a “Later” reminder button, selectable corner/monitor/duration, a game mode for full screen, per-streamer sounds/colors/game filters, importing the channels you follow, stream-schedule heads-ups, pause and quiet hours, phone push (ntfy, Discord, Telegram), history charts with CSV export, a mini window, settings backup, and self-updating.

**Quick start:** download `TwitchLiveAlert.exe` from the [Releases](https://github.com/AwayToMoon/Twitch-Alerts/releases/latest) page, or install Python 3.10+, run `python -m pip install requests pillow pystray` and start `python twitch_alert_gui.py`. You need a free Twitch developer application (Client ID and Secret, redirect URL `http://localhost`, category “Application Integration”) – see steps 4 and 5 above.

---

## ⚖️ Hinweis

Dieses Projekt ist ein privates Hobbyprojekt und steht in keiner Verbindung zu Twitch Interactive, Inc. „Twitch“ ist eine Marke der jeweiligen Inhaber.

<div align="center">

<sub>Gebaut mit 🌙 und Python</sub>

</div>
