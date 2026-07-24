import asyncio
import os
from dotenv import load_dotenv
import aiosqlite
import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
DB_PATH = os.getenv('DATABASE_PATH', 'data.db')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)


async def init_db():
    db = await aiosqlite.connect(DB_PATH)
    await db.execute('''CREATE TABLE IF NOT EXISTS warns (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, moderator_id INTEGER, reason TEXT, timestamp INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, timestamp INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS reminders (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, user_id INTEGER, remind_at INTEGER, content TEXT)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, user_id INTEGER, status TEXT, created_at INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS xp (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS giveaways (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, message_id INTEGER, ends_at INTEGER, prize TEXT, active INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, author_id INTEGER, content TEXT, done INTEGER)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS countdowns (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, channel_id INTEGER, end_at INTEGER, title TEXT)''')
    await db.execute('''CREATE TABLE IF NOT EXISTS absences (id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER, user_id INTEGER, until INTEGER, reason TEXT)''')
    await db.commit()
    return db


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')


async def load_cogs():
    for fname in ('moderation', 'community', 'organization', 'security', 'stats', 'tickets', 'xp', 'giveaway', 'todo', 'countdown', 'absence'):
        try:
            await bot.load_extension(f'cogs.{fname}')
            print(f'Loaded cog: {fname}')
        except Exception as e:
            print(f'Failed loading {fname}:', e)


async def main():
    bot.db = await init_db()
    await load_cogs()
    await bot.start(TOKEN)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Bot stopped')
