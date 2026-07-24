import time
import discord
from discord.ext import commands, tasks


class Moderation(commands.Cog):
    """Advanced moderation with anti-raid, escalation, and spam detection."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.recent = {}  # guild_id -> {user_id: [timestamps]}
        self.raids = {}  # guild_id -> {count, last_time}
        self.raid_threshold = 5  # joins per 30 seconds
        self.escalation_loop.start()

    def cog_unload(self):
        self.escalation_loop.cancel()

    async def _get_warn_count(self, guild_id: int, user_id: int) -> int:
        cur = await self.bot.db.execute('SELECT COUNT(*) FROM warns WHERE guild_id = ? AND user_id = ?', (guild_id, user_id))
        row = await cur.fetchone()
        return row[0] if row else 0

    async def _escalate_user(self, guild: discord.Guild, member: discord.Member, warn_count: int):
        """Auto-escalation: mute -> kick -> ban based on warn count."""
        if warn_count >= 5:
            try:
                await member.ban(reason=f'Automatisches Ban nach {warn_count} Verwarnungen')
                for ch in guild.text_channels:
                    try:
                        await ch.send(f'{member.mention} wurde automatisch gebannt (5+ Verwarnungen).')
                        break
                    except Exception:
                        pass
            except Exception as e:
                print(f'Ban failed: {e}')
        elif warn_count == 3:
            try:
                await member.kick(reason=f'Automatisches Kick nach {warn_count} Verwarnungen')
                for ch in guild.text_channels:
                    try:
                        await ch.send(f'{member.mention} wurde automatisch gekickt (3 Verwarnungen).')
                        break
                    except Exception:
                        pass
            except Exception as e:
                print(f'Kick failed: {e}')
        elif warn_count == 2:
            try:
                mute_role = discord.utils.get(guild.roles, name='Muted')
                if not mute_role:
                    mute_role = await guild.create_role(name='Muted', reason='Auto-Mute')
                    for ch in guild.channels:
                        try:
                            await ch.set_permissions(mute_role, send_messages=False)
                        except Exception:
                            pass
                await member.add_roles(mute_role)
                for ch in guild.text_channels:
                    try:
                        await ch.send(f'{member.mention} wurde automatisch gemutet (2 Verwarnungen).')
                        break
                    except Exception:
                        pass
            except Exception as e:
                print(f'Mute failed: {e}')

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, user: discord.Member, *, reason: str = 'Keine Angabe'):
        ts = int(time.time())
        await self.bot.db.execute('INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)', (ctx.guild.id, user.id, ctx.author.id, reason, ts))
        await self.bot.db.commit()
        warn_count = await self._get_warn_count(ctx.guild.id, user.id)
        await ctx.send(f'{user.mention} wurde verwarnt: {reason} ({warn_count} total)')
        await self._escalate_user(ctx.guild, user, warn_count)

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, user: discord.Member, *, reason: str = None):
        """Mute a user (add Muted role)."""
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
        if not mute_role:
            mute_role = await ctx.guild.create_role(name='Muted', reason='Mute-Rolle')
            for ch in ctx.guild.channels:
                try:
                    await ch.set_permissions(mute_role, send_messages=False)
                except Exception:
                    pass
        try:
            await user.add_roles(mute_role)
            msg = f'{user.mention} wurde gemutet.'
            if reason:
                msg += f' Grund: {reason}'
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f'Fehler: {e}')

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, user: discord.Member):
        """Unmute a user."""
        mute_role = discord.utils.get(ctx.guild.roles, name='Muted')
        if not mute_role:
            await ctx.send('Mute-Rolle existiert nicht.')
            return
        try:
            await user.remove_roles(mute_role)
            await ctx.send(f'{user.mention} wurde entmutet.')
        except Exception as e:
            await ctx.send(f'Fehler: {e}')

    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warns(self, ctx, user: discord.Member = None):
        """List warns for a user."""
        user = user or ctx.author
        cur = await self.bot.db.execute('SELECT reason, timestamp FROM warns WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC', (ctx.guild.id, user.id))
        rows = await cur.fetchall()
        if not rows:
            await ctx.send(f'{user.mention} hat keine Verwarnungen.')
            return
        lines = [f'- {r[0]} (<t:{r[1]}:R>)' for r in rows[:10]]
        await ctx.send(f'Verwarnungen für {user.mention}:\n' + '\n'.join(lines))

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, user: discord.Member, *, reason: str = None):
        try:
            await user.kick(reason=reason)
            msg = f'{user} wurde gekickt.'
            if reason:
                msg += f' Grund: {reason}'
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f'Fehler: {e}')

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, user: discord.Member, *, reason: str = None):
        try:
            await user.ban(reason=reason)
            msg = f'{user} wurde gebannt.'
            if reason:
                msg += f' Grund: {reason}'
            await ctx.send(msg)
        except Exception as e:
            await ctx.send(f'Fehler: {e}')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Detect raids: mass joins trigger lockdown."""
        guild = member.guild
        raid_map = self.raids.setdefault(guild.id, {'count': 0, 'last_time': time.time()})
        now = time.time()
        
        if now - raid_map['last_time'] > 30:
            raid_map['count'] = 0
        
        raid_map['count'] += 1
        raid_map['last_time'] = now
        
        if raid_map['count'] >= self.raid_threshold:
            try:
                for ch in guild.text_channels:
                    try:
                        await ch.send('🚨 **RAID ALERT** — Channel lockdown aktiviert!')
                        break
                    except Exception:
                        pass
                for ch in guild.channels:
                    if isinstance(ch, discord.TextChannel):
                        try:
                            await ch.set_permissions(guild.default_role, send_messages=False)
                        except Exception:
                            pass
                raid_map['count'] = 0
            except Exception as e:
                print(f'Raid lockdown failed: {e}')

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        """Unlock all channels after raid."""
        try:
            for ch in ctx.guild.channels:
                if isinstance(ch, discord.TextChannel):
                    await ch.set_permissions(ctx.guild.default_role, send_messages=None)
            await ctx.send('Alle Channels entsperrt.')
        except Exception as e:
            await ctx.send(f'Fehler: {e}')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        guild_map = self.recent.setdefault(message.guild.id, {})
        arr = guild_map.setdefault(message.author.id, [])
        now = time.time()
        arr.append(now)
        while len(arr) > 8:
            arr.pop(0)
        if len(arr) >= 6 and (now - arr[0]) < 5.0:
            await message.channel.send(f'{message.author.mention} Spam erkannt — automatische Warnung.')
            ts = int(time.time())
            await self.bot.db.execute('INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)', (message.guild.id, message.author.id, self.bot.user.id, 'Automatische Spam-Warnung', ts))
            await self.bot.db.commit()
            warn_count = await self._get_warn_count(message.guild.id, message.author.id)
            await self._escalate_user(message.guild, message.author, warn_count)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        chan = message.channel
        log = f'Nachricht gelöscht von {message.author}: {message.content[:50]}'
        try:
            await chan.send(f'📝 {log}')
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
            await chan.send(f'✏️ {before.author} bearbeitete: "{before.content[:30]}" → "{after.content[:30]}"')
        except Exception:
            pass

    @tasks.loop(minutes=1)
    async def escalation_loop(self):
        """Periodic cleanup and escalation checks."""
        for guild_id in self.raids:
            now = time.time()
            if now - self.raids[guild_id]['last_time'] > 120:
                self.raids[guild_id]['count'] = 0


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
