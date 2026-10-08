# SigmaBot

Ein bestehender, modularer Discord-Bot in Python. Alle Befehle sind Discord-Slash-Commands und laufen auf Servern. Nachrichten mit `!` lösen keine Befehle mehr aus. `/help` zeigt Administratoren die verfügbaren Befehle. **Alle Slash-Commands außer `/ticket` erfordern die Discord-Berechtigung Administrator.** `/ticket` bleibt für normale Servermitglieder verfügbar.

## Starten

Python 3.11 oder 3.12 verwenden (Docker verwendet 3.11):

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`.env.example` nach `.env` kopieren und den Discord-Token lokal eintragen. Dann `python bot.py` ausführen. Der Bot erstellt die SQLite-Datenbank und migriert vorhandene Tabellen beim Start. Vor Updates eine Datenbanksicherung anlegen.

Im Discord Developer Portal die **Server Members Intent** und **Message Content Intent** aktivieren. Der Bot braucht Zugang zu den verwendeten Channels. Je nach Funktion benötigt er zusätzlich Manage Roles, Moderate Members, Manage Channels, Manage Messages, Kick Members, Ban Members, Add Reactions, Read Message History und Embed Links. Seine Rolle muss über den Rollen liegen, die er verwaltet. Administrator ist nicht erforderlich.

## Konfiguration

| Variable | Verwendung |
| --- | --- |
| `DISCORD_TOKEN` | Erforderlicher Bot-Token |
| `DATABASE_PATH` | SQLite-Datei, Standard `data.db` |
| `VPN_API_KEY` | Optionaler IPQualityScore-Key für manuelle IP-Checks |
| `URL_SCAN_API_KEY` | Optionaler IPQualityScore-Key für URL-Scans |

Secrets ausschließlich in Umgebungsvariablen oder `.env` speichern. `.gitignore` schützt Secrets, Datenbanken, Logs und lokale Python-Umgebungen; `.dockerignore` verhindert deren Aufnahme in das Image. Ohne URL-API verwendet der Bot eine begrenzte Heuristik für verdächtige Discord-Imitationen. Das ist kein vollständiger Phishing-Schutz. Discord stellt Bots keine Mitglieder-IP-Adressen bereit; `/checkip` prüft nur die manuell angegebene IP.

## Befehle und Funktionen

| Modul | Befehle / Verhalten |
| --- | --- |
| Moderation | `/warn`, `/warns`, `/mute`, `/unmute`, `/kick`, `/ban`, `/unlock`; Spam-Erkennung und Anti-Raid |
| Community | Begrüßung/Abschied; `/reactionrole <message_id> <emoji> <role>` im Channel der Nachricht |
| Organisation | `/remind <seconds> <text>` |
| Sicherheit | `/checkip <ip>`, `/scanurl <url>`; Account-Alter-Hinweis und URL-Scanner |
| Statistik | `/serverstats` zählt aufgezeichnete Nachrichten |
| Tickets | `/ticket [Grund]`, `/ticketinfo [Channel]`, `/close [Channel]` |
| XP | `/level [Mitglied]`; XP für Nachrichten, höchstens einmal je Minute pro Mitglied |
| Giveaways | `/giveaway <seconds> [winners=1] <prize>`, `/reroll <message_id> [winners=1]` |
| Aufgaben | `/todo_add <text>`, `/todo_list`, `/todo_done <id>` für den aktuellen Channel |
| Countdown | `/countdown <seconds> [Titel]` |
| Abwesenheit | `/away <seconds> [Grund]`; Hinweise bei Erwähnung |

- Spam-Erkennung: sechs Nachrichten innerhalb von fünf Sekunden; höchstens eine automatische Spam-Verwarnung je 30 Sekunden und Mitglied.
- Eskalation: zwei Verwarnungen → Discord-Timeout für 28 Tage; drei → Kick; fünf oder mehr → Ban. Rollen-Hierarchie und Server-Eigentümer werden berücksichtigt.
- `/mute` nutzt einen Discord-Timeout für maximal 28 Tage, damit andere Rollen den Mute nicht übersteuern. `/unmute` entfernt den Timeout und eine eventuell vorhandene alte `Muted`-Rolle. Für Timeout-Aktionen braucht der Bot Moderate Members.
- Anti-Raid: fünf Beitritte innerhalb von 30 Sekunden. Vorige Channel-Overwrites werden gespeichert und durch `/unlock` wiederhergestellt. Explizite Senderechte anderer Rollen und Administratorrechte können eine Sperre für `@everyone` übersteuern.
- Reaktionsrollen: Zuordnung wird gespeichert. Raw-Reaction-Events vergeben/entfernen Rollen auch ohne Nachrichten-Cache; Administratorrollen sind ausgeschlossen.
- Giveaways: Teilnehmer und Gewinneranzahl liegen in SQLite. Buttons werden nach Neustarts registriert. Bestehende 🎉-Reaktionen werden beim Ablauf übernommen; Reroll verwendet die gespeicherten Teilnehmer eines beendeten Giveaways.
- Tickets: private Channels mit Ersteller und optionaler Rolle `Moderator`. Der dauerhafte Close-Button darf vom Ersteller oder von Mitgliedern mit Manage Channels genutzt werden. `/close` erfordert Manage Channels und akzeptiert ausschließlich offene Tickets.
- Erinnerungen und Countdowns warten auf Discord-Bereitschaft. Fehlgeschlagene Zustellungen werden erneut versucht; dauerhaft fehlende Ziele werden aufgeräumt. Bei einem Prozessabbruch genau zwischen Versand und Datenbank-Commit kann eine Ankündigung erneut gesendet werden.
- Abwesenheit: ein aktueller Eintrag pro Mitglied; ein erneutes `/away` ersetzt den bisherigen Status.

Nicht implementiert sind CAPTCHA-Verifizierung, Geburtstage, Umfragen, Kalenderintegration, Voice-XP/-Statistiken und Audit-Log-Auswertung. Frühere Dokumentation führte diese als vorhandene Funktionen auf.

## Struktur

`bot.py` verwaltet Start, Datenbank, Migrationen und Fehlerbehandlung. `cogs/` enthält elf Erweiterungen und gemeinsame Helfer. Alle verwenden `bot.db`. Die `tests/` prüfen sowohl bestehende Basistests als auch reale Cog- und SQLite-Abläufe mit simulierten Discord-Antworten. Die Slash-Commands werden beim Bot-Start global und nach der Verbindung direkt mit den verbundenen Servern synchronisiert.

## Prüfen

```bash
python -m pytest tests/ -v
python -m flake8 .
python -m black --check bot.py main.py cogs tests
python -m pip check
```

Tests benötigen weder Bot-Token noch Discord-Verbindung. Ein Test auf einem echten Discord-Testserver ist zusätzlich erforderlich, um Intents, Rollenpositionen und Channel-Berechtigungen der jeweiligen Installation zu prüfen.

Weitere Betriebsanweisungen stehen in [DEPLOYMENT.md](DEPLOYMENT.md).


## Slash-Commands aktivieren

Nach dem Update den Bot auf dem Hosting neu starten. Beim Start registriert er alle Befehle inklusive `/help` global bei Discord und nach dem Login direkt auf den verbundenen Servern. Nach einem erneuten Gateway-Verbindungsaufbau werden bereits synchronisierte Server nicht nochmals registriert; neu beigetretene Server werden automatisch ergänzt. In einem Server-Channel `/` eingeben und SigmaBot auswählen; die Argumente erscheinen als Eingabefelder. Der Bot muss mit den OAuth2-Scopes `bot` und `applications.commands` installiert sein, und Mitglieder benötigen im Channel die Berechtigung „Anwendungsbefehle verwenden“. Bei fehlenden Befehlen die Installation und die Startlogs prüfen; gegebenenfalls Discord neu laden. Für alle Slash-Commands außer `/ticket` ist Administrator erforderlich. Die Bot-Berechtigungen für die jeweiligen Aktionen bleiben erforderlich.

`/reactionrole` und `/reroll` erwarten die Nachrichten-ID als Text, damit die langen Discord-IDs ohne Zahlenrundung erhalten bleiben. Nachrichtenauswertung für Moderation, XP und Statistik bleibt aktiv, weshalb Message Content und Server Members Intents weiterhin benötigt werden.


### Wenn die Befehle nicht in der Liste erscheinen

Im Hosting-Log muss nach `Logged in as ...` für deinen Server `Registered 24 slash commands directly for server ...` stehen. Das Log enthält außerdem einen Installationslink für die tatsächlich angemeldete App. Stimmen Bot-Name oder App-ID nicht mit deiner erwarteten App überein, prüfe die Anwendung, zu der der konfigurierte Token gehört; den Token niemals posten.

Den Installationslink als Server-Administrator öffnen und denselben Bot mit `bot` und `applications.commands` autorisieren. Den Bot dafür nicht vom Server entfernen. In den Channel-/Rollenberechtigungen muss „Anwendungsbefehle verwenden“ erlaubt sein. Unter Servereinstellungen → Integrationen → der betreffenden App prüfen, ob die Commands für deine Rolle und den Channel freigegeben sind. Danach Discord neu laden und `/help` im Server-Channel auswählen. Das reine Schreiben von `/help` als gewöhnliche Nachricht führt keinen Command aus.

Die globale Meldung `Registered 24 slash commands` bestätigt die API-Registrierung, aber nicht die Sichtbarkeit für eine bestimmte Rolle in einem bestimmten Server. Bei `Slash registration denied` fehlen der Server-App die nötigen Installationsrechte; der im Log angezeigte Link autorisiert genau diese App. HTTP-Fehler bei einer einzelnen Server-Registrierung stoppen den übrigen Bot nicht.


### Administrator-Zugriff

Die Anzeige aller Commands außer `/ticket` ist standardmäßig auf Administratoren beschränkt. Zusätzlich prüft der Bot bei jeder Ausführung die echte Serverberechtigung `Administrator`; der Name einer Rolle, einzelne Moderationsrechte oder manuelle Discord-Command-Freigaben umgehen diese Prüfung nicht. Diese Regel gilt auch für `/help`, `/level` und die Organisationsbefehle. `/ticket` benötigt keine Administratorrechte; die Ticket-Erstellung behält den bestehenden Cooldown und die erforderlichen Bot-Rechte.

Nach dem Update den Bot neu starten, damit globale und serverbezogene Command-Berechtigungen neu synchronisiert werden.


### Private Command-Rückmeldungen

Antworten auf Slash-Commands sind „Nur für dich“-Nachrichten: Bestätigungen, Fehler, Listen und mehrteilige Antworten sehen nur die Person, die den Befehl ausführt. Auch die anfängliche Warteanzeige ist privat. Eine manuell ausgelöste Verwarnungs-Eskalation erzeugt keine zusätzliche öffentliche Bestätigung.

Der eigentliche Giveaway-Beitrag mit Teilnahme-Button bleibt öffentlich, damit Mitglieder teilnehmen können; die Rückmeldung an den Administrator bleibt privat. Ticket-Inhalte bleiben im privaten Ticket-Channel. Automatische Channel-Ankündigungen wie fällige Erinnerungen, Countdown-Enden und Giveaway-Ergebnisse behalten ihren bisherigen Empfängerkreis.
