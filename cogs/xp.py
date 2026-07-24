import random
import discord
from discord.ext import commands


class XP(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        user_id = message.author.id
        cur = await self.bot.db.execute('SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
        row = await cur.fetchone()
        gain = random.randint(5, 12)
        if row:
            xp, level = row
            xp += gain
            next_level = (level + 1) * 100
            if xp >= next_level:
                level += 1
                await message.channel.send(f'{message.author.mention} hat Level {level} erreicht!')
            await self.bot.db.execute('UPDATE xp SET xp = ?, level = ? WHERE guild_id = ? AND user_id = ?', (xp, level, guild_id, user_id))
        else:
            xp = gain
            level = 1
            await self.bot.db.execute('INSERT INTO xp (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)', (guild_id, user_id, xp, level))
        await self.bot.db.commit()

    @commands.command()
    async def level(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        cur = await self.bot.db.execute('SELECT xp, level FROM xp WHERE guild_id = ? AND user_id = ?', (ctx.guild.id, member.id))
        row = await cur.fetchone()
        if not row:
            await ctx.send('Keine Daten.')
            return
        xp, level = row
        await ctx.send(f'{member.display_name}: Level {level}, XP {xp}')


async def setup(bot: commands.Bot):
    await bot.add_cog(XP(bot))
