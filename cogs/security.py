import time
import os
import ipaddress
import json
import re
import aiohttp
import urllib.parse
import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import send_chunks

URL_REGEX = re.compile(r"(https?://[^\s]+)")


class Security(commands.Cog):
    """Security cog with optional IP/VPN checks and URL scanning.
    Requires environment variables to enable third-party checks:
    - `VPN_API_KEY` for IP/Proxy/VPN detection (IPQualityScore)
    - `URL_SCAN_API_KEY` for URL scanning (IPQualityScore URL endpoint)
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _check_ip_with_ipquality(self, ip: str):
        try:
            ip = str(ipaddress.ip_address(ip))
        except ValueError as exc:
            raise commands.BadArgument("Ungültige IP-Adresse.") from exc
        key = os.getenv("VPN_API_KEY")
        if not key:
            return None
        url = f"https://ipqualityscore.com/api/json/ip/{key}/{ip}?strictness=1"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get("success") is not False:
                            return data
            except Exception:
                return None

    async def _check_url_with_ipquality(self, url_to_check: str):
        parsed = urllib.parse.urlparse(url_to_check)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise commands.BadArgument("Bitte gib eine gültige HTTP(S)-URL ohne Zugangsdaten an.")
        key = os.getenv("URL_SCAN_API_KEY")
        if not key:
            return None
        encoded = urllib.parse.quote(url_to_check, safe="")
        api = f"https://ipqualityscore.com/api/json/url/{key}/{encoded}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if isinstance(data, dict) and data.get("success") is not False:
                            return data
            except Exception:
                return None

    def _heuristic_url_check(self, url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        # Generic terms such as login/bank/free also occur on legitimate sites.
        # Only flag obvious Discord impersonation; the API can catch more threats.
        official = ("discord.com", "discord.gg", "discordapp.com", "discord.gift")
        if any(host == domain or host.endswith("." + domain) for domain in official):
            return False
        return ("discord" in host or "dlscord" in host) and any(
            word in url.lower() for word in ("nitro", "gift", "claim", "login", "verify")
        )

    async def is_suspicious_url(self, url: str) -> bool:
        # Prefer third-party API if available
        api_data = await self._check_url_with_ipquality(url)
        if api_data:
            # IPQualityScore returns fields like 'suspicious', 'malicious', 'risk_score'
            if api_data.get("suspicious") or api_data.get("malicious"):
                return True
            score = api_data.get("risk_score")
            if isinstance(score, (int, float)) and score >= 50:
                return True
            return False
        # fallback heuristics
        return self._heuristic_url_check(url)

    async def is_suspicious_ip(self, ip: str) -> bool:
        api_data = await self._check_ip_with_ipquality(ip)
        if not api_data:
            return False
        # IPQualityScore includes 'proxy', 'tor', 'vpn', and 'fraud_score'
        if api_data.get("proxy") or api_data.get("vpn") or api_data.get("tor"):
            return True
        fraud = api_data.get("fraud_score")
        if isinstance(fraud, (int, float)) and fraud >= 75:
            return True
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        created = member.created_at.timestamp()
        age = time.time() - created
        if age < 60 * 60 * 24 * 7:  # account younger than 7 days
            try:
                await member.send(
                    "Dein Account ist sehr neu. Ein Moderator wird sich vergewissern, dass du kein Bot bist."
                )
            except Exception:
                pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        text = message.content
        urls = URL_REGEX.findall(text)
        if not urls:
            return
        for url in urls:
            try:
                suspicious = await self.is_suspicious_url(url)
            except Exception:
                suspicious = False
            if suspicious:
                removed = False
                try:
                    await message.delete()
                    removed = True
                except Exception:
                    pass
                try:
                    action = "entfernt" if removed else "als verdächtig erkannt"
                    await message.channel.send(
                        f"{message.author.mention} Dein Link wurde {action} — möglicher Scam/Phishing."
                    )
                except Exception:
                    pass
                # store automatic warn
                ts = int(time.time())
                await self.bot.db.execute(
                    "INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (
                        message.guild.id,
                        message.author.id,
                        self.bot.user.id,
                        "Automatischer URL-Scanner: verdächtiger Link",
                        ts,
                    ),
                )
                await self.bot.db.commit()
                moderation = self.bot.get_cog("Moderation")
                if moderation:
                    count = await moderation._get_warn_count(message.guild.id, message.author.id)
                    await moderation._escalate_user(message.guild, message.author, count)
                break  # Only one warning per message.

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await self.on_message(after)

    @commands.hybrid_command(description="Prüft eine IP-Adresse über die konfigurierte API.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(ip="IP-Adresse, die geprüft werden soll.")
    async def checkip(self, ctx, ip: str):
        """Manueller IP-Check über konfigurierbare API (falls vorhanden)."""
        api_data = await self._check_ip_with_ipquality(ip)
        if not api_data:
            await ctx.send("Keine API konfiguriert oder Fehler bei Anfrage.")
            return
        result = {k: api_data[k] for k in ("proxy", "vpn", "tor", "fraud_score") if k in api_data}
        await send_chunks(ctx, "IP-Check Ergebnis: " + json.dumps(result, ensure_ascii=False))

    @commands.hybrid_command(description="Prüft eine URL auf verdächtige Inhalte.")
    @app_commands.guild_only()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    @app_commands.describe(url="HTTP(S)-URL, die geprüft werden soll.")
    async def scanurl(self, ctx, url: str):
        """Manueller URL-Scan (verwendet externe API wenn konfiguriert)."""
        api_data = await self._check_url_with_ipquality(url)
        if api_data:
            result = {k: api_data[k] for k in ("suspicious", "malicious", "risk_score") if k in api_data}
            await send_chunks(ctx, "URL-Scan Ergebnis: " + json.dumps(result, ensure_ascii=False))
            return
        heur = self._heuristic_url_check(url)
        await ctx.send(f'Heuristischer Check: {"Verdächtig" if heur else "Nicht verdächtig"}')


async def setup(bot: commands.Bot):
    await bot.add_cog(Security(bot))
