import time
import discord
from discord import app_commands
from discord.ext import commands
from cogs.utils import bounded_text


async def close_ticket(bot, channel, actor, notify=None):
    cur = await bot.db.execute(
        "SELECT user_id FROM tickets WHERE guild_id = ? AND channel_id = ? AND status = ?",
        (channel.guild.id, channel.id, "open"),
    )
    row = await cur.fetchone()
    if not row:
        raise commands.BadArgument("Das ist kein offenes Ticket.")
    if actor.id != row[0] and not channel.permissions_for(actor).manage_channels:
        raise commands.MissingPermissions(["manage_channels"])
    if notify is not None:
        await notify("Ticket wird geschlossen...", ephemeral=True)
    await channel.delete(reason=f"Ticket geschlossen von {actor.id}")
    await bot.db.execute("UPDATE tickets SET status = ? WHERE channel_id = ?", ("closed", channel.id))
    await bot.db.commit()


class CloseButton(discord.ui.View):
    def __init__(self, bot, channel_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.channel_id = channel_id
        self.children[0].custom_id = f"ticket:close:{channel_id}"

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.red, emoji="🔒", custom_id="ticket:close")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild or interaction.channel_id != self.channel_id:
            await interaction.followup.send("Ungültiger Ticket-Channel.", ephemeral=True)
            return
        try:
            await close_ticket(self.bot, interaction.channel, interaction.user, notify=interaction.followup.send)
        except (commands.CommandError, discord.HTTPException):
            await interaction.followup.send(
                "Ticket konnte nicht geschlossen werden. Prüfe die Berechtigungen.", ephemeral=True
            )


class Tickets(commands.Cog):
    """Ticket-System mit Embeds und Close-Buttons."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        cur = await self.bot.db.execute("SELECT channel_id FROM tickets WHERE status = 'open'")
        for (channel_id,) in await cur.fetchall():
            self.bot.add_view(CloseButton(self.bot, channel_id))

    @commands.hybrid_command(description="Erstellt ein privates Support-Ticket.")
    @app_commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True, embed_links=True)
    @commands.cooldown(1, 30, commands.BucketType.member)
    @app_commands.describe(reason="Grund oder Beschreibung.")
    async def ticket(self, ctx, *, reason: str = "Support benötigt"):
        """Erstellt ein Support-Ticket."""
        bounded_text(reason, 1000)
        guild = ctx.guild
        mod_role = discord.utils.get(guild.roles, name="Moderator")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True),
        }
        if mod_role:
            overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")
        chan = await guild.create_text_channel(f"ticket-{ctx.author.id}", overwrites=overwrites, category=category)
        ts = int(time.time())
        await self.bot.db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (guild.id, chan.id, ctx.author.id, "open", ts),
        )
        await self.bot.db.commit()
        # Embed für Ticket-Infos
        embed = discord.Embed(
            title="📋 Ticket erstellt",
            description=f"Benutzer: {ctx.author.mention}\nGrund: {reason}",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Status", value="🟢 Offen", inline=True)
        embed.add_field(name="Erstellt", value=f"<t:{ts}:R>", inline=True)
        embed.set_footer(text=f"Ticket ID: {chan.id}")
        view = CloseButton(self.bot, chan.id)
        await chan.send(embed=embed, view=view)
        await ctx.send(f"✅ Ticket erstellt: {chan.mention}")

    @commands.hybrid_command(description="Zeigt Informationen zu einem Ticket.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(channel="Ticket-Channel; ohne Auswahl der aktuelle Channel.")
    async def ticketinfo(self, ctx, channel: discord.TextChannel = None):
        """Zeigt Ticket-Informationen."""
        channel = channel or ctx.channel
        cur = await self.bot.db.execute(
            "SELECT user_id, status, created_at FROM tickets WHERE channel_id = ?", (channel.id,)
        )
        row = await cur.fetchone()
        if not row:
            await ctx.send("Das ist kein Ticket-Channel.")
            return
        user_id, status, created_at = row
        user = await self.bot.fetch_user(user_id)
        embed = discord.Embed(
            title="📋 Ticket-Informationen", color=discord.Color.blue(), timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Ersteller", value=f"{user.mention}", inline=True)
        embed.add_field(name="Status", value=status.upper(), inline=True)
        embed.add_field(name="Erstellt", value=f"<t:{created_at}:R>", inline=False)
        embed.set_footer(text=f"Channel ID: {channel.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="Schließt ein offenes Support-Ticket.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    @app_commands.describe(channel="Ticket-Channel; ohne Auswahl der aktuelle Channel.")
    async def close(self, ctx, channel: discord.TextChannel = None):
        """Schließt ein Ticket manuell."""
        channel = channel or ctx.channel
        await close_ticket(self.bot, channel, ctx.author, notify=ctx.send)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
