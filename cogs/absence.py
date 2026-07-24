import time
import discord
from discord.ext import commands


class Absence(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def away(self, ctx, seconds: int, *, reason: str = 'Abwesend'):
        until = int(time.time()) + seconds
        await self.bot.db.execute('INSERT INTO absences (guild_id, user_id, until, reason) VALUES (?, ?, ?, ?)', (ctx.guild.id, ctx.author.id, until, reason))
        await self.bot.db.commit()
        await ctx.send(f'Abwesenheit gesetzt für {seconds} Sekunden: {reason}')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        # if message mentions someone who is away, notify
        for m in message.mentions:
            cur = await self.bot.db.execute('SELECT until, reason FROM absences WHERE guild_id = ? AND user_id = ?', (message.guild.id, m.id))
            row = await cur.fetchone()
            if row:
                until, reason = row
                if int(time.time()) < until:
                    await message.channel.send(f'{m.display_name} ist derzeit abwesend: {reason}')


async def setup(bot: commands.Bot):
    await bot.add_cog(Absence(bot))
