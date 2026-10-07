import logging
import discord
from discord.ext import commands

log = logging.getLogger(__name__)


def positive_seconds(seconds):
    if not 0 < seconds <= 31536000:
        raise commands.BadArgument("Die Dauer muss zwischen 1 Sekunde und 365 Tagen liegen.")


def bounded_text(text, limit=1800):
    if not text.strip() or len(text) > limit:
        raise commands.BadArgument(f"Der Text muss zwischen 1 und {limit} Zeichen lang sein.")


async def send_chunks(destination, text):
    for start in range(0, len(text), 1900):
        await destination.send(text[start : start + 1900], allowed_mentions=discord.AllowedMentions.none())


async def deliver(bot, guild_id, channel_id, text):
    """Retry transient failures; discard jobs only for permanently missing destinations."""
    guild = bot.get_guild(guild_id)
    if guild is None:
        return True
    channel = guild.get_channel_or_thread(channel_id)
    if channel is None:
        try:
            channel = await guild.fetch_channel(channel_id)
        except discord.NotFound:
            return True
        except discord.HTTPException:
            return False
    try:
        await channel.send(text)
    except discord.NotFound:
        return True
    except discord.HTTPException:
        log.warning("Scheduled message could not be delivered to channel %s", channel_id)
        return False
    return True
