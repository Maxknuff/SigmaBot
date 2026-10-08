import time
import random
import re
import discord
from discord import app_commands
from discord.ext import commands, tasks
from cogs.utils import snowflake, bounded_text, positive_seconds


class JoinButton(discord.ui.View):
    def __init__(self, bot, giveaway_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.giveaway_id = giveaway_id
        self.children[0].custom_id = f"giveaway:join:{giveaway_id}"

    @discord.ui.button(label="Teilnehmen", style=discord.ButtonStyle.green, emoji="🎉", custom_id="giveaway:join")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        async with self.bot.db_lock:
            cur = await self.bot.db.execute(
                "INSERT OR IGNORE INTO giveaway_entries (message_id, user_id) "
                "SELECT message_id, ? FROM giveaways WHERE id = ? AND guild_id = ? AND active = 1 AND ends_at > ?",
                (interaction.user.id, self.giveaway_id, interaction.guild_id, int(time.time())),
            )
            await self.bot.db.commit()
            if cur.rowcount:
                text = "✅ Du nimmst am Giveaway teil!"
            else:
                text = "Du nimmst bereits teil oder das Giveaway ist beendet."
        await interaction.followup.send(text, ephemeral=True)


class Giveaway(commands.Cog):
    """Giveaway-System mit persistenten Teilnehmern und Button-UI."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_giveaways.start()

    async def cog_load(self):
        cur = await self.bot.db.execute("SELECT id, message_id FROM giveaways WHERE active = 1")
        for gid, message_id in await cur.fetchall():
            self.bot.add_view(JoinButton(self.bot, gid), message_id=message_id)

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.hybrid_command(description="Startet ein Giveaway mit Teilnahme-Button.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(embed_links=True, read_message_history=True)
    @app_commands.describe(
        seconds="Dauer in Sekunden, mindestens 1 und maximal 31536000.",
        winners="Anzahl der Gewinner zwischen 1 und 100.",
        prize="Preis des Giveaways.",
    )
    async def giveaway(self, ctx, seconds: int, winners: int = 1, *, prize: str = "Preis"):
        positive_seconds(seconds)
        bounded_text(prize, 500)
        if not 1 <= winners <= 100:
            raise commands.BadArgument("Die Gewinneranzahl muss zwischen 1 und 100 liegen.")
        ends = int(time.time()) + seconds
        embed = discord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=f"**Preis:** {prize}\n\n**Gewinner:** {winners}\n**Endet:** <t:{ends}:R>",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow(),
        )
        embed.set_footer(text="Klick den Button um teilzunehmen!")
        # The event itself needs a public message so members can participate.
        msg = await ctx.channel.send(embed=embed)
        cur = await self.bot.db.execute(
            "INSERT INTO giveaways (guild_id, channel_id, message_id, ends_at, prize, active, winners) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (ctx.guild.id, ctx.channel.id, msg.id, ends, prize, winners),
        )
        await self.bot.db.commit()
        await msg.edit(view=JoinButton(self.bot, cur.lastrowid))
        await ctx.send(f"✅ Giveaway für **{prize}** gestartet! {winners} Gewinner.")

    async def _participants(self, message):
        # Preserve reaction-based participation in existing giveaways.
        for reaction in message.reactions:
            if str(reaction.emoji) == "🎉":
                async for user in reaction.users():
                    if not user.bot:
                        await self.bot.db.execute(
                            "INSERT OR IGNORE INTO giveaway_entries (message_id, user_id) VALUES (?, ?)",
                            (message.id, user.id),
                        )
        await self.bot.db.commit()
        cur = await self.bot.db.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (message.id,))
        return [r[0] for r in await cur.fetchall()]

    @commands.hybrid_command(description="Lost neue Gewinner eines beendeten Giveaways aus.")
    @app_commands.guild_only()
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        message_id="Discord-Nachrichten-ID als Text aus dem Entwicklermodus kopieren.",
        winners="Anzahl der Gewinner zwischen 1 und 100.",
    )
    async def reroll(self, ctx, message_id: str, winners: int = 1):
        message_id = snowflake(message_id)
        if not 1 <= winners <= 100:
            raise commands.BadArgument("Die Gewinneranzahl muss zwischen 1 und 100 liegen.")
        cur = await self.bot.db.execute(
            "SELECT active FROM giveaways WHERE message_id = ? AND guild_id = ? AND channel_id = ?",
            (message_id, ctx.guild.id, ctx.channel.id),
        )
        row = await cur.fetchone()
        if not row or row[0]:
            await ctx.send("Kein beendetes Giveaway in diesem Channel gefunden.")
            return
        cur = await self.bot.db.execute("SELECT user_id FROM giveaway_entries WHERE message_id = ?", (message_id,))
        participants = [r[0] for r in await cur.fetchall()]
        if not participants:
            # Existing finished giveaways may only have reaction-based participants.
            try:
                message = await ctx.channel.fetch_message(message_id)
                participants = await self._participants(message)
            except discord.HTTPException:
                pass
        if not participants:
            await ctx.send("Keine Teilnehmer.")
            return
        selected = random.sample(participants, min(winners, len(participants)))
        await ctx.send("🎊 Neue Gewinner: " + ", ".join(f"<@{uid}>" for uid in selected))

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        cur = await self.bot.db.execute(
            "SELECT id, guild_id, channel_id, message_id, prize, winners FROM giveaways "
            "WHERE ends_at <= ? AND active = 1",
            (int(time.time()),),
        )
        for gid, guild_id, channel_id, message_id, prize, winners in await cur.fetchall():
            guild = self.bot.get_guild(guild_id)
            channel = guild.get_channel_or_thread(channel_id) if guild else None
            if not guild:
                await self._finish(gid)
                continue
            try:
                channel = channel or await guild.fetch_channel(channel_id)
                msg = await channel.fetch_message(message_id)
                # Older databases did not store the requested count. Recover it from the existing embed.
                if winners == 1 and msg.embeds:
                    match = re.search(r"Gewinner:\*{0,2}\s*(\d+)", msg.embeds[0].description or "")
                    if match:
                        winners = max(1, min(100, int(match[1])))
                participants = await self._participants(msg)
                selected = random.sample(participants, min(max(1, winners), len(participants)))
                text = ", ".join(f"<@{uid}>" for uid in selected) if selected else "Leider keine Teilnehmer."
                embed = discord.Embed(
                    title="🎊 Giveaway beendet!",
                    description=f"**Preis:** {prize}\n\n**Gewinner:** {text}",
                    color=discord.Color.gold(),
                )
                await channel.send(embed=embed)
            except discord.NotFound:
                await self._finish(gid)
                continue
            except discord.HTTPException:
                continue  # Retry without terminating the background loop.
            await self._finish(gid)
            try:
                await msg.edit(view=None)
            except discord.HTTPException:
                pass

    async def _finish(self, gid):
        await self.bot.db.execute("UPDATE giveaways SET active = 0 WHERE id = ?", (gid,))
        await self.bot.db.commit()

    @check_giveaways.before_loop
    async def before_giveaways(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
