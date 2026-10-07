# SigmaBot betreiben

SigmaBot benötigt Python 3.11/3.12 und einen dauerhaft laufenden Prozess mit persistentem SQLite-Speicher. Genau eine Instanz je Bot-Token und Datenbank betreiben: mehrere Instanzen könnten Erinnerungen oder Giveaway-Ergebnisse mehrfach senden.

## Lokal

1. Eine virtuelle Python-Umgebung erstellen und `pip install -r requirements.txt` ausführen.
2. `.env.example` nach `.env` kopieren und lokale Werte eintragen.
3. Intents und Rollenpositionen wie in der [README](README.md) einrichten.
4. `python bot.py` starten. Ein fehlender oder unveränderter Beispiel-Token führt vor dem Datenbankstart zu einem verständlichen Fehler.

## Docker Compose

Die `.env` bleibt auf dem Host. Compose gibt die Werte an den Container weiter; `.dockerignore` hält Secrets aus dem Image heraus. Die SQLite-Datei inklusive WAL-Dateien liegt im eingebundenen Verzeichnis `./data`.

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

Vor dem Update die Datenbank sichern. Bei Änderungen `docker compose up -d --build` verwenden. Nicht mehrere Container-Replikate starten.

## systemd (Linux)

Das Projekt nach `/opt/sigmabot` installieren, dort eine `.venv` und `.env` erstellen und einen Benutzer `sigmabot` einrichten. Dieser Benutzer benötigt Leserechte für `.env` und Schreibrechte auf den konfigurierten Datenbankordner. `.env` nur für den Betreiber lesbar machen.

```bash
sudo cp sigmabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now sigmabot
sudo journalctl -u sigmabot -f
```

Die mitgelieferte Unit verwendet `/opt/sigmabot/.venv/bin/python` und das Arbeitsverzeichnis `/opt/sigmabot`. Pfade bei abweichender Installation anpassen.

## PM2

`ecosystem.config.js` startet einen Python-Prozess. Sicherstellen, dass `interpreter` auf die Python-Datei der installierten `.venv` zeigt; der Standardwert `python` verwendet die Umgebung des PM2-Prozesses. PM2 aus dem Projektverzeichnis starten, damit `.env` und Datenbankpfad stimmen.

```bash
pm2 start ecosystem.config.js
pm2 save
pm2 logs sigmabot
```

PM2-Cluster-Modus für diesen Bot nicht verwenden. PM2 benötigt kein `npm install` im Bot-Projekt.

## Plattformen mit flüchtigem Dateisystem

Der `Procfile` enthält den Worker-Startbefehl. SQLite auf einem flüchtigen Worker-Dateisystem verliert Daten beim Neustart/Deployment. Deshalb dort nur mit einem persistenten Volume betreiben. Eine externe PostgreSQL-Datenbank ist in diesem Projekt nicht implementiert.

## Datenbanksicherung

Eine laufende SQLite-Datei im WAL-Modus nicht einfach mit `cp` kopieren. Die SQLite-Backup-API verwenden, beispielsweise mit der SQLite-CLI:

```bash
sqlite3 data.db ".backup 'backup.db'"
```

Alternativ den Bot stoppen und die Datenbank zusammen mit vorhandenen `-wal`/`-shm`-Dateien sichern. Backup-Dateien enthalten Nutzerdaten und gehören nicht in GitHub. Vor jeder Aktualisierung sichern. Beim nächsten Start werden bestehende Tabellen erweitert; doppelte XP-Datensätze werden mit dem höchsten gespeicherten XP-Stand zusammengeführt, bei Abwesenheiten bleibt der neueste Eintrag erhalten.

## Updates und Checks

```bash
git pull --ff-only origin main
pip install -r requirements.txt
python -m pytest tests/ -v
python -m flake8 .
python -m black --check bot.py cogs tests
python -m pip check
```

Danach den verwendeten Dienst neu starten. Erst auf einem Testserver prüfen, insbesondere Moderations- und Rollenbefehle.

## Fehlerdiagnose

- Fehlender Token: `.env` bzw. Dienst-Umgebung prüfen, Token niemals in Logs oder Chat ausgeben.
- Privileged Intents: Server Members und Message Content im Developer Portal aktivieren.
- Berechtigungsfehler: Channel-Rechte und Bot-Rolle prüfen; die Bot-Rolle muss über den verwalteten Rollen liegen.
- SQLite-Schreibfehler: Datenbankpfad und Dateirechte prüfen. Eine bestehende Datenbank nicht zum Troubleshooting löschen.
- Extensions: Ladefehler brechen den Start ab, damit kein unbemerkt unvollständiger Bot online geht.
- Hintergrundjobs: Discord-HTTP-Fehler werden erneut versucht. Fehlende Channels/Guilds werden aufgeräumt.

Der Bot hat keinen HTTP-Health-Endpunkt. Betriebsüberwachung erfolgt über Prozessstatus und Logs.
