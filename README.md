# SigmaBot

SigmaBot ist ein vielseitiger, modularer Discord-Bot für Server-Verwaltung, Community-Funktionen, Organisation und Sicherheit. Entwickelt, um Moderation zu automatisieren, die Community-Interaktion zu fördern und Admins mit nützlichen Statistik- und Organisationswerkzeugen zu unterstützen.

**Überblick**
- **Zweck:** Moderation, Community-Management, Organisation, Sicherheit und Statistiken.
- **Zielgruppe:** Server-Administratoren, Moderationsteams und aktive Communities.

**Quick Reference**

| Aktion | Befehl |
|--------|--------|
| Bot starten | `python bot.py` |
| Mit Docker starten | `docker-compose up -d` |
| Tests ausführen | `pytest tests/ -v` |
| Code linten | `flake8 . && black .` |
| Doku lesen | [DEPLOYMENT.md](DEPLOYMENT.md) |

**Features**

- **🛡️ Moderation:** Automatische Spam-Erkennung, Scam- und Phishing-Link-Blocker, Anti-Raid-System, AutoMute / AutoKick / AutoBan, Warnsystem mit Datenbank, Logging gelöschter und bearbeiteter Nachrichten.
- **👥 Community:** Verifizierungs-System, Reaktionsrollen, Levelsystem mit XP, Begrüßungs- und Abschiedsnachrichten, Geburtstags-Erinnerungen, Umfragen, Giveaway-System.
- **📅 Organisation:** Erinnerungen, Terminplaner, To-do-Listen, Countdown bis Events, Abwesenheits-System.
- **🔒 Sicherheit:** Account-Alter prüfen, verdächtige Nutzer erkennen, mehrere Einladungen erkennen, VPN-/Proxy-Erkennung (über APIs), Audit-Log-Auswertung.
- **📊 Statistiken:** Server-Statistiken, aktivste Mitglieder, Nachrichten pro Tag, Voice-Chat-Zeit.

**Kurze Feature-Beschreibungen**
- **Spam-Erkennung:** Heuristiken und Rate-Limits verhindern automatisierte Spammer. Automatische Spam-Warnung bei 6+ Nachrichten in 5 Sekunden.
- **Auto-Eskalation:** Warnungen triggern automatische Stufen — 2 Warnungen → Mute, 3 Warnungen → Kick, 5+ Warnungen → Ban.
- **Anti-Raid-System:** Erkennt Massenbeitritte (5+ in 30 Sekunden) → alle Channels werden automatisch gesperrt (nur Admins können entperren mit `!unlock`).
- **Link-Blocker:** Blockiert verdächtige URLs (heuristische Prüfung + optional IPQualityScore API); automatische Warnung beim Versuch.
- **Warnsystem:** Warnungen werden persistent in SQLite-DB gespeichert, Eskalationen automatisch angewendet.
- **Mute/Unmute:** Manuelle Mute-Befehle (`!mute @user` / `!unmute @user`), erstellt automatisch eine "Muted"-Rolle mit angepassten Berechtigungen.
- **Warns-Liste:** `!warns [@user]` zeigt alle Verwarnungen mit Zeitstempel und Grund.
- **Ticket-System:** Einfache Ticket-Erstellung für Support und Moderation mit konfigurierbaren Rollen.
- **Verifizierung:** Role-basiertes Verifizierungs-Flow (CAPTCHA / Reaktionsprüfung).
- **Levelsystem:** XP für Nachrichten und Voice-Aktivität, Rang- und Rollenbelohnungen.
- **Erinnerungen & Terminplaner:** PM- und Channel-Reminders, wiederkehrende Events und Kalendereinträge.
- **VPN-/Proxy-Checks:** Optionale API-Integration zur Reduzierung von Missbrauch.
- **Audit-Logs & Statistiken:** Übersicht zur Server-Gesundheit und Nutzer-Aktivität.

**Installation & Schnellstart**
1. Bot-Anwendung auf dem Discord-Developer-Portal erstellen und Token generieren.
2. Bot mit den benötigten Berechtigungen einladen (Moderation, Nachrichten-Management, View-Audit-Log, Manage-Roles).
3. Konfigurationsdatei oder Umgebungsvariablen anlegen (`.env`): `DISCORD_TOKEN`, `DATABASE_URL`, `API_KEYS`.
4. Datenbank einrichten (z. B. PostgreSQL / SQLite) und Migrationen ausführen.
5. Bot starten: `npm install` und `npm start` bzw. `python bot.py` je nach Implementierung.

**Konfiguration**
- **Datenbank:** Warn-Logs, Ticket-Historie und XP werden persistent gespeichert.
- **APIs:** VPN-/Proxy-Checks und eventuell URL-Scanning können über externe APIs konfiguriert werden.
- **Rollen & Rechte:** Für Moderations-Automationen werden spezielle Moderations-Rollen empfohlen.

**Befehle & Permissions**
- Administrations-Commands sind standardmäßig Moderatoren und Admins vorbehalten.
- Viele Module lassen sich ein- und ausschalten, und Verhalten kann pro-Server feinjustiert werden.

**Support & Mitwirken**
- Issues und Feature-Requests bitte im Repository öffnen.
- Vorschläge, Bugfixes und PRs sind willkommen — bitte Coding-Standards beachten.

**Datenschutz & Sicherheit**
- Nutzt möglichst sichere API-Keys und speichert keine sensiblen Daten unverschlüsselt.
- Informiere deine Community über aktivierte Überwachungs- und Moderationsfunktionen.

**Lizenz**
- Dieses Projekt ist Open Source — Lizenzangabe nach Wunsch ergänzen.

Mehr Details zur Einrichtung und zu einzelnen Modulen findest du im Repository.

**Installieren & Starten (konkret)**
1. Kopiere `.env.example` zu `.env` und fülle `DISCORD_TOKEN` aus.
2. Erstelle ein virtuelles Environment und installiere Abhängigkeiten:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Starte den Bot:

```bash
python bot.py
```

**Implementierte Module (aktuell)**
- `cogs/moderation.py` — Warns, Kick, Ban, Anti-Raid, Auto-Eskalation (Mute/Kick/Ban), Spam-Erkennung, Logging
- `cogs/community.py` — Begrüßungs- und Abschiedsnachrichten, einfache Reaction-Role-Hilfe
- `cogs/organization.py` — Erinnerungen (Remind) mit Hintergrund-Dispatcher
- `cogs/security.py` — Account-Alter-Prüfung, IP/VPN-Check (IPQualityScore API), URL-Scanning
- `cogs/stats.py` — Nachrichten-Zählung, einfache Serverstatistik
- `cogs/tickets.py` — Ticket-System mit Embeds, Close-Buttons, Ticket-Info
- `cogs/xp.py` — Einfaches XP/Level-System
- `cogs/giveaway.py` — Giveaway mit Embeds, multi-Gewinner, Reroll-Funktion
- `cogs/todo.py` — Kanal-basierte To-do-Listen
- `cogs/countdown.py` — Countdown-Ankündigungen
- `cogs/absence.py` — Abwesenheits-Status und Benachrichtigung bei Erwähnung

**Moderation: Anti-Raid & Auto-Eskalation**

SigmaBot bietet umfassende Moderationsfunktionen mit automatischer Eskalation:

- **Warn-System:** `!warn @user [Grund]` — Verwarnt einen User und zeigt aktuelle Warn-Zahl an.
  - 2 Warnungen → automatisches **Mute** (Muted-Rolle entfernt send_messages Recht)
  - 3 Warnungen → automatisches **Kick**
  - 5+ Warnungen → automatisches **BAN**
- **Manuelle Befehle:** `!mute @user [Grund]` / `!unmute @user` / `!kick @user [Grund]` / `!ban @user [Grund]`
- **Warns-Liste:** `!warns [@user]` — zeigt alle Verwarnungen mit Zeitstempel (neueste zuerst, max. 10 angezeigt)
- **Anti-Raid:** Automatische Erkennung von Massenbeitritten (5+ in 30 Sekunden) → alle Channels werden gesperrt
- **Raid-Entsperrung:** `!unlock` — entsperrt alle Channels nach Raid-Lockdown (nur Admins)
- **Spam-Schutz:** Automatische Warnung bei 6+ Nachrichten in 5 Sekunden

**Tickets & Support-System**

Tickets helfen dabei, Support-Anfragen organisiert zu verwalten:

- **Ticket erstellen:** `!ticket [Grund]` — erstellt einen privaten Channel mit dem Nutzer und Mods
  - Automatische Überschrift mit Embed (Ersteller, Grund, Status, Zeitstempel)
  - Close-Button im Ticket zum schnellen Schließen
  - Moderatoren bekommen automatisch Zugriff (wenn "Moderator"-Rolle existiert)
- **Ticket-Info:** `!ticketinfo [Channel]` — zeigt Ticket-Details (Ersteller, Status, Erstellungszeit)
- **Ticket schließen:** `!close [Channel]` — schließt und löscht ein Ticket mit Bestätig-Embed

**Giveaway-System (erweitert)**

Giveaways mit schöner UI und Teilnehmer-Verwaltung:

- **Giveaway starten:** `!giveaway <Sekunden> [Gewinner=1] <Preis>` — startet ein Giveaway
  - Goldenes Embed mit Preis, Anzahl Gewinner, Countdown (`<t:timestamp:R>`)
  - Teilnehmen durch 🎉-Reaktion
  - Automatische Gewinner-Auslosung nach Zeit
- **Giveaway-Gewinner:** Bot zeigt Gewinner in separatem Embed an, sortiert nach Anzahl Gewinner
- **Reroll:** `!reroll <message_id> [Gewinner=1]` — rollt beendetes Giveaway neu aus
- **Persistente Teilnehmer:** Teilnehmer-Liste wird über Reactions verwaltet; beim Ablauf werden alle nicht-Bot-User berücksichtigt

**Sicherheit: API-Integration für IP/URL-Scans**

SigmaBot kann optionale Drittanbieter-APIs nutzen, um IPs, VPN/Proxy-Nutzung und URLs auf Betrug bzw. Phishing zu prüfen.

- `VPN_API_KEY`: (optional) API-Key für IP/Proxy/VPN-Erkennung (z. B. IPQualityScore). Wird für `!checkip` genutzt.
- `URL_SCAN_API_KEY`: (optional) API-Key zum Scannen von URLs (z. B. IPQualityScore URL-Endpoint). Wird für automatisches Entfernen verdächtiger Links und `!scanurl` genutzt.

Wenn keine API-Keys konfiguriert sind, nutzt SigmaBot heuristische Prüfungen (Keyword-Checks, ungewöhnlich lange Hostnamen) als Fallback.

Beispiel `.env`-Erweiterung:

```env
DISCORD_TOKEN=...
DATABASE_PATH=data.db
VPN_API_KEY=your_ipqualityscore_key_here
URL_SCAN_API_KEY=your_ipqualityscore_key_here
```

Hinweis: Drittanbieter-APIs haben Rate-Limits und Kosten — nutze Keys verantwortungsvoll.

**Testing & Linting**

SigmaBot enthält Tests und Linting-Konfiguration:

- **Tests ausführen:** `pytest tests/` — führt alle Tests mit pytest aus
- **Linting:** `flake8 .` — prüft Code-Stil (max 120 Zeichen, PEP8-konform)
- **Code formatieren:** `black .` — formatiert Code einheitlich
- **Alle zusammen:** `pytest tests/ && flake8 . && black .`

Tests umfassen:
- Bot-Initialisierung und Datenbank-Verbindung
- Moderation (Warn-Counts, Spam-Detection)
- Giveaway-Logik (Winner-Selektion, Embeds)
- Ticket-System (Erstellung, Schließen)

**Deployment**

**Option 1: Docker (empfohlen für Production)**

Schnellstart mit Docker Compose:

```bash
# 1. .env Datei erstellen (oder existierende verwenden)
cp .env.example .env
# Bearbeite .env und setze DISCORD_TOKEN

# 2. Mit Docker Compose starten
docker-compose up -d

# 3. Logs anschauen
docker-compose logs -f sigmabot

# 4. Bot stoppen
docker-compose down
```

Oder manuell mit Docker:

```bash
# Image bauen
docker build -t sigmabot .

# Container starten
docker run -d --name sigmabot --env-file .env -v $(pwd)/data:/app/data sigmabot

# Logs anschauen
docker logs -f sigmabot

# Stoppen
docker stop sigmabot && docker rm sigmabot
```

**Option 2: Heroku**

Heroku bietet kostenlose Tier mit einigen Limitierungen (kein 24/7, Worker-Dynos).

```bash
# 1. Heroku CLI installieren: https://devcenter.heroku.com/articles/heroku-cli

# 2. App erstellen
heroku create your-bot-name

# 3. Environment Variablen setzen
heroku config:set DISCORD_TOKEN=your_token_here
heroku config:set DATABASE_PATH=/tmp/data.db

# 4. Deployen
git push heroku main

# 5. Logs anschauen
heroku logs --tail

# 6. Worker-Dyno starten (kostenpflichtig)
heroku ps:scale worker=1
```

**Option 3: PM2 (Node.js Process Manager — Linux/Mac)**

PM2 managed den Bot als Prozess mit Auto-Restart:

```bash
# 1. PM2 installieren (erfordert Node.js)
npm install -g pm2

# 2. Bot mit PM2 starten
pm2 start ecosystem.config.js

# 3. Status anschauen
pm2 status

# 4. Logs anschauen
pm2 logs sigmabot

# 5. Auto-Restart beim Reboot aktivieren
pm2 startup
pm2 save

# 6. Bot stoppen
pm2 stop sigmabot
pm2 delete sigmabot
```

**Option 4: systemd (Linux — Production)**

systemd ist für Linux-Server optimal:

```bash
# 1. Bot-User erstellen (optional, aber empfohlen)
sudo useradd -m -s /bin/bash sigmabot

# 2. Bot in /opt installieren
sudo mkdir -p /opt/sigmabot
sudo cp -r . /opt/sigmabot
sudo chown -R sigmabot:sigmabot /opt/sigmabot

# 3. Virtual Environment erstellen
cd /opt/sigmabot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. .env mit DISCORD_TOKEN setzen
nano .env

# 5. systemd Service installieren
sudo cp sigmabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sigmabot
sudo systemctl start sigmabot

# 6. Status anschauen
sudo systemctl status sigmabot
sudo journalctl -u sigmabot -f
```

**Skalierung & Monitoring**

- **Datenbank-Backup:** Regelmäßig `data.db` sichern (z. B. täglich auf S3/Google Drive)
- **Rate Limiting:** Discord hat strikte Rate-Limits — der Bot beachtet diese automatisch
- **Performance:** Bei >100k Nachrichten/Tag erwäge Migration zu PostgreSQL statt SQLite
- **Uptime Monitoring:** Tools wie UptimeRobot oder pingpong.one können HTTP-Health-Checks durchführen

**Entwicklung lokal**

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # oder .venv\Scripts\activate auf Windows
pip install -r requirements.txt

# .env mit Token füllen
echo "DISCORD_TOKEN=your_test_token" > .env

# Bot starten
python bot.py

# Tests ausführen
pytest tests/ -v

# Code formatieren & linten
black .
flake8 .
```

Datei: [README.md](README.md)
