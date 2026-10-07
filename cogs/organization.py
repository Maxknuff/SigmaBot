import time
from discord.ext import commands, tasks
from cogs.utils import bounded_text, deliver, positive_seconds


class Organization(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @commands.command()
    async def remind(self, ctx, seconds: int, *, text: str):
        positive_seconds(seconds)
        bounded_text(text)
        ts = int(time.time()) + seconds
        await self.bot.db.execute(
            "INSERT INTO reminders (guild_id, channel_id, user_id, remind_at, content) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, ctx.channel.id, ctx.author.id, ts, text),
        )
        await self.bot.db.commit()
        await ctx.send(f"Erinnerung gesetzt in {seconds} Sekunden.")

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        now = int(time.time())
        cur = await self.bot.db.execute(
            "SELECT id, guild_id, channel_id, user_id, content FROM reminders WHERE remind_at <= ?", (now,)
        )
        rows = await cur.fetchall()
        for row in rows:
            rid, gid, cid, uid, content = row
            if await deliver(self.bot, gid, cid, f"Erinnerung für <@{uid}>: {content}"):
                await self.bot.db.execute("DELETE FROM reminders WHERE id = ?", (rid,))
                await self.bot.db.commit()
        await self.bot.db.commit()

    @reminder_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Organization(bot))
