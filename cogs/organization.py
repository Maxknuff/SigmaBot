import time
import asyncio
import discord
from discord.ext import commands, tasks


class Organization(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @commands.command()
    async def remind(self, ctx, seconds: int, *, text: str):
        ts = int(time.time()) + seconds
        await self.bot.db.execute('INSERT INTO reminders (guild_id, channel_id, user_id, remind_at, content) VALUES (?, ?, ?, ?, ?)', (ctx.guild.id, ctx.channel.id, ctx.author.id, ts, text))
        await self.bot.db.commit()
        await ctx.send(f'Erinnerung gesetzt in {seconds} Sekunden.')

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        now = int(time.time())
        cur = await self.bot.db.execute('SELECT id, guild_id, channel_id, user_id, content FROM reminders WHERE remind_at <= ?', (now,))
        rows = await cur.fetchall()
        for row in rows:
            rid, gid, cid, uid, content = row
            guild = self.bot.get_guild(gid)
            if guild:
                channel = guild.get_channel(cid)
                member = guild.get_member(uid)
                if channel:
                    mention = member.mention if member else 'User'
                    await channel.send(f'Erinnerung für {mention}: {content}')
            await self.bot.db.execute('DELETE FROM reminders WHERE id = ?', (rid,))
        await self.bot.db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(Organization(bot))
