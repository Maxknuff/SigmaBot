import time
import discord
from discord.ext import commands, tasks


class Countdown(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loop.start()

    def cog_unload(self):
        self.loop.cancel()

    @commands.command()
    async def countdown(self, ctx, seconds: int, *, title: str = 'Event'):
        end_at = int(time.time()) + seconds
        await self.bot.db.execute('INSERT INTO countdowns (guild_id, channel_id, end_at, title) VALUES (?, ?, ?, ?)', (ctx.guild.id, ctx.channel.id, end_at, title))
        await self.bot.db.commit()
        await ctx.send(f'Countdown für **{title}** gestartet ({seconds} Sekunden).')

    @tasks.loop(seconds=15)
    async def loop(self):
        now = int(time.time())
        cur = await self.bot.db.execute('SELECT id, guild_id, channel_id, title FROM countdowns WHERE end_at <= ?', (now,))
        rows = await cur.fetchall()
        for r in rows:
            cid, gid, channel_id, title = r
            guild = self.bot.get_guild(gid)
            if not guild:
                continue
            channel = guild.get_channel(channel_id)
            if channel:
                await channel.send(f'Countdown beendet: **{title}**')
            await self.bot.db.execute('DELETE FROM countdowns WHERE id = ?', (cid,))
        await self.bot.db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(Countdown(bot))
