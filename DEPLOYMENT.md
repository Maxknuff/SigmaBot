# SigmaBot Deployment Guide

Umfassende Anleitung zum Deployment von SigmaBot auf verschiedenen Plattformen.

## Schnellstart (lokal)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "DISCORD_TOKEN=YOUR_TOKEN" > .env
python bot.py
```

## Docker (Production-ready)

### Docker Compose (empfohlen)

```bash
# Starten
docker-compose up -d

# Logs anschauen
docker-compose logs -f

# Stoppen
docker-compose down
```

**Vorteile:**
- Isolierte Umgebung
- Einfach skalierbar
- Reproduzierbar auf jedem System
- Automatisches Restart bei Fehlern

## Heroku (für kleine Projekte)

```bash
heroku create your-bot-name
heroku config:set DISCORD_TOKEN=your_token
git push heroku main
heroku ps:scale worker=1
```

**Limitierungen:**
- Kostenlos nur 550 Dyno-Stunden/Monat
- Kein 24/7 ohne Bezahlung
- SQLite wird bei Dyno-Restart gelöscht → externe DB erforderlich

## PM2 (Development/Kleine Server)

```bash
npm i -g pm2
pm2 start ecosystem.config.js
pm2 startup
pm2 save
```

**Features:**
- Auto-Restart bei Fehlern
- Resource-Monitoring
- Log-Rotation
- Cluster-Mode (mehrere Prozesse)

## systemd (Linux Production)

```bash
sudo cp sigmabot.service /etc/systemd/system/
sudo systemctl enable sigmabot
sudo systemctl start sigmabot
sudo journalctl -u sigmabot -f
```

**Vorteile:**
- Native Linux-Integration
- Automatisches Startup bei Boot
- Systemwide resource control
- Beste Performance

## Cloud-Anbieter

### AWS EC2

```bash
# Ubuntu 22.04 AMI
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
git clone https://github.com/yourusername/SigmaBot.git
cd SigmaBot
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Setze .env
systemctl enable sigmabot
```

### DigitalOcean / Linode

Ähnlich wie AWS, aber mit einfacherer DNS-Verwaltung. Nutze App Platform für Docker-Deployment oder Droplet für systemd.

### Oracle Cloud Free Tier

Kostenlos, mit 2 ARM vCPUs und 12 GB RAM. Perfekt für einen Discord-Bot.

## Monitoring & Wartung

### Logs rotieren

Verwende logrotate oder PM2's built-in rotation:

```bash
pm2 install pm2-auto-pull
```

### Datenbank-Backup

```bash
# Tägliches Backup
0 2 * * * cp /path/to/data.db /backup/data.db.$(date +\%Y\%m\%d)

# Mit Cloud-Sync (z. B. S3)
0 2 * * * aws s3 cp /path/to/data.db s3://my-bucket/sigmabot-backup.db
```

### Health Checks

Nutze `curl` in einem Cron-Job, um Uptime zu monitoren:

```bash
*/5 * * * * curl -f http://localhost:8080/health || systemctl restart sigmabot
```

(Erfordert Health-Endpoint in Bot - optional)

## Troubleshooting

**Bot startet nicht:**
```bash
python bot.py  # Direkt ausführen um Errors zu sehen
python -m py_compile bot.py  # Syntax-Check
```

**Datenbank-Fehler:**
```bash
rm data.db  # SQLite-DB neu erstellen (Datenverlust!)
# Oder Backup zurückstellen:
cp /backup/data.db data.db
```

**Memory-Leak:**
```bash
# Bei PM2: Memory-Limit setzen
pm2 start ecosystem.config.js --max-memory-restart 512M
```

**Discord-Verbindung-Fehler:**
```bash
# Token prüfen
echo $DISCORD_TOKEN

# Rate-Limiting? Logs anschauen
pm2 logs sigmabot | grep -i "rate"
```

## Performance-Tipps

1. **Datenbank**: Bei >1 Million Einträge → PostgreSQL statt SQLite
2. **Caching**: XP- und Level-Daten in-memory cachen für schnellere Abfragen
3. **Batch-Operations**: Mehrere Discord-API-Calls kombinieren
4. **Async-First**: Alle IO-Operationen müssen async sein

## Sicherheit

1. **Never commit `.env`** — Nutze `.env.example`
2. **Rate Limits** — Bot beachtet Discord-Limits automatisch
3. **Input-Validation** — Alle User-Inputs sanitieren
4. **API-Keys** — Nicht hardcoden, immer aus `.env`
5. **Datenbank-Zugriff** — Nur über prepared statements (schon implementiert)

## Update-Prozess

```bash
# 1. Neue Version pullen
git pull origin main

# 2. Abhängigkeiten updaten
pip install -r requirements.txt --upgrade

# 3. Tests ausführen
pytest tests/

# 4. Bot neu starten
pm2 restart sigmabot
# oder
sudo systemctl restart sigmabot
```
