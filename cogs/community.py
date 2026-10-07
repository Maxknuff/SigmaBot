import discord
from discord.ext import commands


def emoji_key(emoji):
    parsed = discord.PartialEmoji.from_str(str(emoji))
    return str(parsed.id) if parsed.id else parsed.name


def assignable(role, guild, actor):
    return (
        not role.is_default()
        and not role.managed
        and not role.permissions.administrator
        and role < guild.me.top_role
        and (actor.id == guild.owner_id or role < actor.top_role)
    )


class Community(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _announce(self, guild, text):
        channel = next((c for c in guild.text_channels if c.permissions_for(guild.me).send_messages), None)
        if channel:
            try:
                await channel.send(text)
            except discord.HTTPException:
                pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self._announce(member.guild, f"Willkommen {member.mention}!")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self._announce(member.guild, f"{member.display_name} hat den Server verlassen.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, add_reactions=True, read_message_history=True)
    async def reactionrole(self, ctx, message_id: int, emoji: str, role: discord.Role):
        if not assignable(role, ctx.guild, ctx.author):
            raise commands.BadArgument("Diese Rolle kann nicht als Reaktionsrolle vergeben werden.")
        msg = await ctx.channel.fetch_message(message_id)
        await msg.add_reaction(emoji)
        await self.bot.db.execute(
            "INSERT INTO reaction_roles (guild_id, channel_id, message_id, emoji, role_id) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(guild_id, message_id, emoji) DO UPDATE SET role_id = excluded.role_id",
            (ctx.guild.id, ctx.channel.id, message_id, emoji_key(emoji), role.id),
        )
        await self.bot.db.commit()
        await ctx.send("Reaktionsrolle eingerichtet.")

    async def _reaction_role(self, payload, add):
        if not payload.guild_id or payload.user_id == self.bot.user.id:
            return
        cur = await self.bot.db.execute(
            "SELECT role_id FROM reaction_roles WHERE guild_id = ? AND channel_id = ? "
            "AND message_id = ? AND emoji = ?",
            (payload.guild_id, payload.channel_id, payload.message_id, emoji_key(payload.emoji)),
        )
        row = await cur.fetchone()
        guild = self.bot.get_guild(payload.guild_id)
        if not row or not guild:
            return
        role = guild.get_role(row[0])
        if not role or not assignable(role, guild, guild.me):
            return
        try:
            member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
            if member.bot:
                return
            if add:
                await member.add_roles(role, reason="Reaktionsrolle")
            else:
                await member.remove_roles(role, reason="Reaktionsrolle entfernt")
        except discord.HTTPException:
            return

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self._reaction_role(payload, True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self._reaction_role(payload, False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Community(bot))
