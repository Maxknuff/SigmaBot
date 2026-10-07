import time
import discord
from discord.ext import commands


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ts = int(time.time())
        await self.bot.db.execute(
            "INSERT INTO messages (guild_id, user_id, timestamp) VALUES (?, ?, ?)",
            (message.guild.id, message.author.id, ts),
        )
        await self.bot.db.commit()

    @commands.command()
    async def serverstats(self, ctx: commands.Context):
        cur = await self.bot.db.execute("SELECT COUNT(*) FROM messages WHERE guild_id = ?", (ctx.guild.id,))
        row = await cur.fetchone()
        total = row[0] if row else 0
        await ctx.send(f"Gesamtanzahl Nachrichten (aufgezeichnet): {total}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
