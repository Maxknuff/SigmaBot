import time
from discord.ext import commands, tasks
from cogs.utils import bounded_text, deliver, positive_seconds


class Countdown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loop.start()

    def cog_unload(self):
        self.loop.cancel()

    @commands.command()
    async def countdown(self, ctx, seconds: int, *, title: str = "Event"):
        positive_seconds(seconds)
        bounded_text(title, 1000)
        end_at = int(time.time()) + seconds
        await self.bot.db.execute(
            "INSERT INTO countdowns (guild_id, channel_id, end_at, title) VALUES (?, ?, ?, ?)",
            (ctx.guild.id, ctx.channel.id, end_at, title),
        )
        await self.bot.db.commit()
        await ctx.send(f"Countdown für **{title}** gestartet ({seconds} Sekunden).")

    @tasks.loop(seconds=15)
    async def loop(self):
        now = int(time.time())
        cur = await self.bot.db.execute(
            "SELECT id, guild_id, channel_id, title FROM countdowns WHERE end_at <= ?", (now,)
        )
        rows = await cur.fetchall()
        for r in rows:
            cid, gid, channel_id, title = r
            if await deliver(self.bot, gid, channel_id, f"Countdown beendet: **{title}**"):
                await self.bot.db.execute("DELETE FROM countdowns WHERE id = ?", (cid,))
                await self.bot.db.commit()
        await self.bot.db.commit()

    @loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Countdown(bot))
