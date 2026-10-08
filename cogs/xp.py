import asyncio
import random
import time
import discord
from discord import app_commands
from discord.ext import commands


class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.last_gain = {}
        self.lock = asyncio.Lock()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        key = (message.guild.id, message.author.id)
        async with self.lock:
            now = time.monotonic()
            self.last_gain = {k: ts for k, ts in self.last_gain.items() if now - ts < 60}
            if key in self.last_gain:
                return
            gain = random.randint(5, 12)
            cur = await self.bot.db.execute("SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?", key)
            row = await cur.fetchone()
            xp, old_level = row if row else (0, 1)
            xp += gain
            level = max(old_level, 1, xp // 100)
            await self.bot.db.execute(
                "INSERT INTO xp (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp, level = excluded.level",
                (*key, xp, level),
            )
            await self.bot.db.commit()
            self.last_gain[key] = now
        if level > old_level:
            try:
                await message.channel.send(f"{message.author.mention} hat Level {level} erreicht!")
            except discord.HTTPException:
                pass

    @commands.hybrid_command(description="Zeigt Level und XP eines Mitglieds.")
    @app_commands.guild_only()
    @app_commands.describe(member="Mitglied; ohne Auswahl wird dein eigener Stand angezeigt.")
    async def level(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        cur = await self.bot.db.execute(
            "SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?",
            (ctx.guild.id, member.id),
        )
        row = await cur.fetchone()
        if not row:
            await ctx.send("Keine Daten.")
            return
        xp, level = row
        await ctx.send(f"{member.display_name}: Level {level}, XP {xp}")


async def setup(bot: commands.Bot):
    await bot.add_cog(XP(bot))
