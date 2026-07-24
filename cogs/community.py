import discord
from discord.ext import commands


class Community(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        # welcome channel: first text channel
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if channel:
            await channel.send(f'Willkommen {member.mention}! Bitte verifiziere dich, damit du vollen Zugriff erhältst.')

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        guild = member.guild
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if channel:
            await channel.send(f'{member.display_name} hat den Server verlassen.')

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def reactionrole(self, ctx, message_id: int, emoji: str, role: discord.Role):
        try:
            msg = await ctx.channel.fetch_message(message_id)
            await msg.add_reaction(emoji)
            await ctx.send('Reaktionsrolle eingerichtet.')
        except Exception as e:
            await ctx.send(f'Fehler: {e}')


async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))
