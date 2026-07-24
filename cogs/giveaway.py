import time
import random
import discord
from discord.ext import commands, tasks


class JoinButton(discord.ui.View):
    def __init__(self, bot, giveaway_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.giveaway_id = giveaway_id

    @discord.ui.button(label='Teilnehmen', style=discord.ButtonStyle.green, emoji='🎉')
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Nutzer-ID speichern (einfache in-memory Liste für Demo; könnte auch DB sein)
        # Hier verwenden wir nur die Nachricht selbst
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send('✅ Du nimmst am Giveaway teil!', ephemeral=True)


class Giveaway(commands.Cog):
    """Giveaway-System mit Embeds und Button-UI."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.giveaway_participants = {}  # msg_id -> set(user_ids)
        self.check_giveaways.start()

    def cog_unload(self):
        self.check_giveaways.cancel()

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def giveaway(self, ctx, seconds: int, winners: int = 1, *, prize: str = 'Preis'):
        """Startet ein Giveaway mit angegebenem Zeitlimit und Gewinneranzahl."""
        ends = int(time.time()) + seconds
        
        # Embed für Giveaway
        embed = discord.Embed(
            title='🎉 GIVEAWAY 🎉',
            description=f'**Preis:** {prize}\n\n**Gewinner:** {winners}\n**Endet:** <t:{ends}:R>',
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text='Klick den Button um teilzunehmen!')
        
        msg = await ctx.send(embed=embed)
        
        # Speichere Giveaway in DB
        await self.bot.db.execute(
            'INSERT INTO giveaways (guild_id, channel_id, message_id, ends_at, prize, active) VALUES (?, ?, ?, ?, ?, ?)',
            (ctx.guild.id, ctx.channel.id, msg.id, ends, prize, 1)
        )
        await self.bot.db.commit()
        
        # Initialisiere Teilnehmer-Liste
        self.giveaway_participants[msg.id] = set()
        
        await ctx.send(f'✅ Giveaway für **{prize}** gestartet! {winners} Gewinner.', delete_after=10)

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def reroll(self, ctx, message_id: int, *, winners: int = 1):
        """Rerollt ein beendetes Giveaway."""
        try:
            msg = await ctx.channel.fetch_message(message_id)
        except Exception:
            await ctx.send('Nachricht nicht gefunden.')
            return
        
        participants = self.giveaway_participants.get(message_id, set())
        if not participants:
            await ctx.send('Keine Teilnehmer.')
            return
        
        if winners > len(participants):
            winners = len(participants)
        
        selected_winners = random.sample(list(participants), winners)
        winner_mentions = ', '.join([f'<@{uid}>' for uid in selected_winners])
        
        embed = discord.Embed(
            title='🎊 Neue Gewinner (Reroll)',
            description=f'**Gewinner:** {winner_mentions}',
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        await ctx.send(embed=embed)

    @tasks.loop(seconds=15)
    async def check_giveaways(self):
        """Überprüft beendete Giveaways und zieht Gewinner."""
        now = int(time.time())
        cur = await self.bot.db.execute('SELECT id, guild_id, channel_id, message_id, prize FROM giveaways WHERE ends_at <= ? AND active = 1', (now,))
        rows = await cur.fetchall()
        
        for row in rows:
            gid, guild_id, channel_id, message_id, prize = row[0], row[1], row[2], row[3], row[4]
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
            
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            try:
                msg = await channel.fetch_message(message_id)
            except Exception:
                continue
            
            # Sammle Teilnehmer von Reactions
            participants = self.giveaway_participants.get(message_id, set())
            for react in msg.reactions:
                if str(react.emoji) == '🎉':
                    async for u in react.users():
                        if not u.bot:
                            participants.add(u.id)
            
            # Anzahl der Gewinner
            winners_count = 1  # default
            # Extrahiere aus Embed falls vorhanden
            if msg.embeds:
                desc = msg.embeds[0].description or ''
                if 'Gewinner:' in desc:
                    try:
                        winners_count = int(desc.split('Gewinner:')[1].split('\n')[0].strip())
                    except ValueError:
                        pass
            
            if participants:
                if winners_count > len(participants):
                    winners_count = len(participants)
                
                selected_winners = random.sample(list(participants), winners_count)
                winner_mentions = ', '.join([f'<@{uid}>' for uid in selected_winners])
                
                embed = discord.Embed(
                    title='🎊 Giveaway beendet!',
                    description=f'**Preis:** {prize}\n\n**Gewinner ({winners_count}):** {winner_mentions}',
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                await channel.send(embed=embed)
            else:
                embed = discord.Embed(
                    title='🎊 Giveaway beendet',
                    description='Leider keine Teilnehmer.',
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                await channel.send(embed=embed)
            
            await self.bot.db.execute('UPDATE giveaways SET active = 0 WHERE message_id = ?', (message_id,))
        
        await self.bot.db.commit()


async def setup(bot: commands.Bot):
    await bot.add_cog(Giveaway(bot))
