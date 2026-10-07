import time
import discord
from discord.ext import commands
from cogs.utils import bounded_text, positive_seconds


class Absence(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def away(self, ctx, seconds: int, *, reason: str = "Abwesend"):
        positive_seconds(seconds)
        bounded_text(reason, 1000)
        until = int(time.time()) + seconds
        await self.bot.db.execute(
            "INSERT INTO absences (guild_id, user_id, until, reason) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(guild_id, user_id) DO UPDATE SET until = excluded.until, reason = excluded.reason",
            (ctx.guild.id, ctx.author.id, until, reason),
        )
        await self.bot.db.commit()
        await ctx.send(f"Abwesenheit gesetzt für {seconds} Sekunden: {reason}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        await self.bot.db.execute("DELETE FROM absences WHERE until <= ?", (int(time.time()),))
        await self.bot.db.commit()
        # if message mentions someone who is away, notify
        for m in message.mentions:
            cur = await self.bot.db.execute(
                "SELECT until, reason FROM absences WHERE guild_id = ? AND user_id = ?", (message.guild.id, m.id)
            )
            row = await cur.fetchone()
            if row:
                until, reason = row
                if int(time.time()) < until:
                    await message.channel.send(f"{m.display_name} ist derzeit abwesend: {reason}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Absence(bot))
