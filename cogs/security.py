import time
import time
import os
import re
import aiohttp
import urllib.parse
import discord
from discord.ext import commands


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
        key = os.getenv('VPN_API_KEY')
        if not key:
            return None
        url = f'https://ipqualityscore.com/api/json/ip/{key}/{ip}?strictness=1'
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, timeout=10) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                return None

    async def _check_url_with_ipquality(self, url_to_check: str):
        key = os.getenv('URL_SCAN_API_KEY')
        if not key:
            return None
        encoded = urllib.parse.quote_plus(url_to_check)
        api = f'https://ipqualityscore.com/api/json/url/{key}/{encoded}'
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(api, timeout=15) as resp:
                    if resp.status == 200:
                        return await resp.json()
            except Exception:
                return None

    def _heuristic_url_check(self, url: str) -> bool:
        s = url.lower()
        suspicious_keywords = ('free', 'click', 'verify', 'bank', 'password', 'login', 'reward', 'gift', 'claim')
        if any(k in s for k in suspicious_keywords):
            return True
        # too many dots or long hostnames
        host = urllib.parse.urlparse(url).netloc
        if host and (len(host) > 64 or host.count('.') > 5):
            return True
        return False

    async def is_suspicious_url(self, url: str) -> bool:
        # Prefer third-party API if available
        api_data = await self._check_url_with_ipquality(url)
        if api_data:
            # IPQualityScore returns fields like 'suspicious', 'malicious', 'risk_score'
            if api_data.get('suspicious') or api_data.get('malicious'):
                return True
            score = api_data.get('risk_score')
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
        if api_data.get('proxy') or api_data.get('vpn') or api_data.get('tor'):
            return True
        fraud = api_data.get('fraud_score')
        if isinstance(fraud, (int, float)) and fraud >= 75:
            return True
        return False

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        created = member.created_at.timestamp()
        age = time.time() - created
        if age < 60 * 60 * 24 * 7:  # account younger than 7 days
            try:
                await member.send('Dein Account ist sehr neu. Ein Moderator wird sich vergewissern, dass du kein Bot bist.')
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
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await message.channel.send(f'{message.author.mention} Dein Link wurde entfernt — möglicher Scam/Phishing.')
                except Exception:
                    pass
                # store automatic warn
                ts = int(time.time())
                await self.bot.db.execute('INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)', (message.guild.id, message.author.id, self.bot.user.id, 'Automatischer URL-Scanner: verdächtiger Link', ts))
                await self.bot.db.commit()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def checkip(self, ctx, ip: str):
        """Manueller IP-Check über konfigurierbare API (falls vorhanden)."""
        api_data = await self._check_ip_with_ipquality(ip)
        if not api_data:
            await ctx.send('Keine API konfiguriert oder Fehler bei Anfrage.')
            return
        await ctx.send(f'IP-Check Ergebnis: {api_data}')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def scanurl(self, ctx, url: str):
        """Manueller URL-Scan (verwendet externe API wenn konfiguriert)."""
        api_data = await self._check_url_with_ipquality(url)
        if api_data:
            await ctx.send(f'URL-Scan Ergebnis: {api_data}')
            return
        heur = self._heuristic_url_check(url)
        await ctx.send(f'Heuristischer Check: {"Verdächtig" if heur else "Nicht verdächtig"}')


async def setup(bot: commands.Bot):
    await bot.add_cog(Security(bot))
