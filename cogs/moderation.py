import time
from datetime import timedelta
import discord
from discord.ext import commands, tasks
from cogs.utils import bounded_text, send_chunks


class Moderation(commands.Cog):
    """Advanced moderation with anti-raid, escalation, and spam detection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recent = {}  # guild_id -> {user_id: [timestamps]}
        self.spam_warned = {}
        self.raids = {}  # guild_id -> {count, last_time}
        self.raid_threshold = 5  # joins per 30 seconds
        self.escalation_loop.start()

    def cog_unload(self):
        self.escalation_loop.cancel()

    def _validate_target(self, ctx, user):
        if (
            user.id in (ctx.author.id, ctx.guild.owner_id, self.bot.user.id)
            or user.top_role >= ctx.guild.me.top_role
            or (ctx.author.id != ctx.guild.owner_id and user.top_role >= ctx.author.top_role)
        ):
            raise commands.BadArgument("Dieses Mitglied kann von dir oder dem Bot nicht moderiert werden.")

    async def _get_warn_count(self, guild_id: int, user_id: int) -> int:
        cur = await self.bot.db.execute(
            "SELECT COUNT(*) FROM warns WHERE guild_id = ? AND user_id = ?", (guild_id, user_id)
        )
        row = await cur.fetchone()
        return row[0] if row else 0

    async def _escalate_user(self, guild: discord.Guild, member: discord.Member, warn_count: int):
        """Auto-escalation: mute -> kick -> ban based on warn count."""
        if member.id == guild.owner_id or member.top_role >= guild.me.top_role:
            return
        if warn_count >= 5:
            try:
                await member.ban(reason=f"Automatisches Ban nach {warn_count} Verwarnungen")
                for ch in guild.text_channels:
                    try:
                        await ch.send(f"{member.mention} wurde automatisch gebannt (5+ Verwarnungen).")
                        break
                    except Exception:
                        pass
            except Exception as e:
                print(f"Ban failed: {e}")
        elif warn_count == 3:
            try:
                await member.kick(reason=f"Automatisches Kick nach {warn_count} Verwarnungen")
                for ch in guild.text_channels:
                    try:
                        await ch.send(f"{member.mention} wurde automatisch gekickt (3 Verwarnungen).")
                        break
                    except Exception:
                        pass
            except Exception as e:
                print(f"Kick failed: {e}")
        elif warn_count == 2:
            try:
                await member.timeout(timedelta(days=28), reason="Auto-Mute nach 2 Verwarnungen")
                for ch in guild.text_channels:
                    try:
                        await ch.send(f"{member.mention} wurde automatisch für 28 Tage gemutet.")
                        break
                    except discord.HTTPException:
                        pass
            except discord.HTTPException:
                print("Auto-Mute fehlgeschlagen: Bot-Rechte und Rollen-Hierarchie prüfen.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(send_messages=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str = "Keine Angabe"):
        self._validate_target(ctx, user)
        bounded_text(reason, 1000)
        ts = int(time.time())
        await self.bot.db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, user.id, ctx.author.id, reason, ts),
        )
        await self.bot.db.commit()
        warn_count = await self._get_warn_count(ctx.guild.id, user.id)
        await ctx.send(f"{user.mention} wurde verwarnt: {reason} ({warn_count} total)")
        await self._escalate_user(ctx.guild, user, warn_count)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx, user: discord.Member, *, reason: str = None):
        """Mute a user for up to 28 days using Discord timeout."""
        self._validate_target(ctx, user)
        if reason:
            bounded_text(reason, 400)
        await user.timeout(timedelta(days=28), reason=reason or "Mute")
        await ctx.send(f"{user.mention} wurde für 28 Tage gemutet.")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(moderate_members=True, manage_roles=True)
    async def unmute(self, ctx, user: discord.Member):
        """Remove timeout and any legacy Muted role."""
        self._validate_target(ctx, user)
        await user.timeout(None, reason="Unmute")
        mute_role = discord.utils.get(ctx.guild.roles, name="Muted")
        if mute_role and mute_role in user.roles:
            await user.remove_roles(mute_role)
        await ctx.send(f"{user.mention} wurde entmutet.")

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warns(self, ctx, user: discord.Member = None):
        """List warns for a user."""
        user = user or ctx.author
        cur = await self.bot.db.execute(
            "SELECT reason, timestamp FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC",
            (ctx.guild.id, user.id),
        )
        rows = await cur.fetchall()
        if not rows:
            await ctx.send(f"{user.mention} hat keine Verwarnungen.")
            return
        lines = [f"- {r[0]} (<t:{r[1]}:R>)" for r in rows[:10]]
        await send_chunks(ctx, f"Verwarnungen für {user.mention}:\n" + "\n".join(lines))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason: str = None):
        self._validate_target(ctx, user)
        try:
            await user.kick(reason=reason)
            msg = f"{user} wurde gekickt."
            if reason:
                msg += f" Grund: {reason}"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Fehler: {e}")

    @commands.command()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, *, reason: str = None):
        self._validate_target(ctx, user)
        try:
            await user.ban(reason=reason)
            msg = f"{user} wurde gebannt."
            if reason:
                msg += f" Grund: {reason}"
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f"Fehler: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Detect raids: mass joins trigger lockdown."""
        guild = member.guild
        now = time.time()
        raid_map = self.raids.setdefault(guild.id, {"joins": [], "last_time": now})
        raid_map["joins"] = [ts for ts in raid_map["joins"] if now - ts < 30]
        raid_map["joins"].append(now)
        raid_map["last_time"] = now
        if len(raid_map["joins"]) >= self.raid_threshold:
            try:
                for ch in guild.text_channels:
                    try:
                        await ch.send("🚨 **RAID ALERT** — Channel lockdown aktiviert!")
                        break
                    except Exception:
                        pass
                for ch in guild.channels:
                    if isinstance(ch, discord.TextChannel):
                        try:
                            old = ch.overwrites_for(guild.default_role).send_messages
                            await self.bot.db.execute(
                                "INSERT OR IGNORE INTO raid_overwrites (guild_id, channel_id, send_messages) "
                                "VALUES (?, ?, ?)",
                                (guild.id, ch.id, old),
                            )
                            await self.bot.db.commit()
                            overwrite = ch.overwrites_for(guild.default_role)
                            overwrite.send_messages = False
                            await ch.set_permissions(guild.default_role, overwrite=overwrite)
                        except Exception:
                            pass
                raid_map["joins"].clear()
            except Exception as e:
                print(f"Raid lockdown failed: {e}")

    @commands.command()
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        """Unlock all channels after raid."""
        cur = await self.bot.db.execute(
            "SELECT channel_id, send_messages FROM raid_overwrites WHERE guild_id = ?",
            (ctx.guild.id,),
        )
        failed = 0
        for channel_id, previous in await cur.fetchall():
            ch = ctx.guild.get_channel(channel_id)
            if ch:
                try:
                    overwrite = ch.overwrites_for(ctx.guild.default_role)
                    overwrite.send_messages = None if previous is None else bool(previous)
                    await ch.set_permissions(ctx.guild.default_role, overwrite=overwrite)
                except discord.HTTPException:
                    failed += 1
                    continue
            await self.bot.db.execute("DELETE FROM raid_overwrites WHERE channel_id = ?", (channel_id,))
        await self.bot.db.commit()
        await ctx.send(f"Raid-Sperren aufgehoben. Nicht wiederhergestellte Channels: {failed}.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_map = self.recent.setdefault(message.guild.id, {})
        arr = guild_map.setdefault(message.author.id, [])
        now = time.time()
        arr.append(now)
        arr[:] = [ts for ts in arr if now - ts < 5.0]
        key = (message.guild.id, message.author.id)
        if len(arr) >= 6 and now - self.spam_warned.get(key, 0) >= 30:
            if message.author.id == message.guild.owner_id or message.author.top_role >= message.guild.me.top_role:
                return
            self.spam_warned[key] = now
            try:
                await message.channel.send(f"{message.author.mention} Spam erkannt — automatische Warnung.")
            except discord.HTTPException:
                pass
            ts = int(time.time())
            await self.bot.db.execute(
                "INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (message.guild.id, message.author.id, self.bot.user.id, "Automatische Spam-Warnung", ts),
            )
            await self.bot.db.commit()
            warn_count = await self._get_warn_count(message.guild.id, message.author.id)
            await self._escalate_user(message.guild, message.author, warn_count)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        chan = message.channel
        log = f"Nachricht gelöscht von {message.author}"
        try:
            await chan.send(f"📝 {log}")
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return
        chan = before.channel
        try:
            await chan.send(f"✏️ {before.author} hat eine Nachricht bearbeitet.")
        except Exception:
            pass

    @tasks.loop(minutes=1)
    async def escalation_loop(self):
        """Periodic cleanup and escalation checks."""
        self.spam_warned = {key: ts for key, ts in self.spam_warned.items() if time.time() - ts < 30}
        for guild_id in self.recent:
            self.recent[guild_id] = {
                uid: arr for uid, arr in self.recent[guild_id].items() if arr and time.time() - arr[-1] < 5
            }
        for guild_id in self.raids:
            now = time.time()
            if now - self.raids[guild_id]["last_time"] > 120:
                self.raids[guild_id]["joins"].clear()

    @escalation_loop.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
