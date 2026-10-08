import os
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
import aiosqlite
import discord
from discord.ext import commands
from discord import app_commands
from cogs.utils import send_chunks

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB_PATH = os.getenv("DATABASE_PATH", "data.db")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
EXTENSIONS = (
    "moderation",
    "community",
    "organization",
    "security",
    "stats",
    "tickets",
    "xp",
    "giveaway",
    "todo",
    "countdown",
    "absence",
)
log = logging.getLogger(__name__)


async def guild_only(ctx):
    if ctx.guild is None:
        raise commands.NoPrivateMessage()
    return True


@commands.hybrid_command(name="help", description="Zeigt die verfügbaren Slash-Commands.")
@app_commands.guild_only()
async def slash_help(ctx):
    lines = [
        f"/{command.name} — {command.description}"
        for command in sorted(ctx.bot.tree.get_commands(), key=lambda command: command.name)
    ]
    await send_chunks(ctx, "Verfügbare Befehle:\n" + "\n".join(lines))


async def defer_slash(ctx):
    if ctx.interaction is not None and not ctx.interaction.response.is_done():
        await ctx.defer()


class SigmaBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=[],
            help_command=None,
            intents=intents,
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
        )
        self.add_command(slash_help.copy())
        self.add_check(guild_only)
        self.before_invoke(defer_slash)
        self.db = None
        self.db_lock = asyncio.Lock()
        self._guild_sync_lock = asyncio.Lock()
        self._synced_guilds = set()

    async def setup_hook(self):
        self.db = await init_db()
        await load_cogs(self)
        synced = await self.tree.sync()
        log.info("Registered %s slash commands", len(synced))

    def installation_url(self):
        if self.application_id is None:
            return None
        return discord.utils.oauth_url(self.application_id, scopes=("bot", "applications.commands"))

    async def sync_guild_commands(self, guild):
        # Guild commands are immediately available and replace stale guild schemas.
        # Sync once per server per process, not on every Gateway reconnect.
        async with self._guild_sync_lock:
            if guild.id in self._synced_guilds:
                return
            self.tree.copy_global_to(guild=guild)
            try:
                synced = await self.tree.sync(guild=guild)
            except discord.Forbidden:
                log.error(
                    "Slash registration denied for server %s. Authorize this app with bot and "
                    "applications.commands: %s",
                    guild.id,
                    self.installation_url(),
                )
                return
            except discord.HTTPException as error:
                log.error(
                    "Slash registration failed for server %s (HTTP %s, Discord code %s); "
                    "will retry on the next connection.",
                    guild.id,
                    error.status,
                    error.code,
                )
                return
            self._synced_guilds.add(guild.id)
            log.info(
                "Registered %s slash commands directly for server %s: %s",
                len(synced),
                guild.id,
                ", ".join(sorted(command.name for command in synced)),
            )

    async def sync_connected_guilds(self):
        log.info("Connected to %s servers. App installation link: %s", len(self.guilds), self.installation_url())
        if not self.guilds:
            log.warning("This bot is not connected to any server. Install it using the link above.")
        for guild in self.guilds:
            await self.sync_guild_commands(guild)

    async def on_guild_join(self, guild):
        await self.sync_guild_commands(guild)

    async def on_guild_remove(self, guild):
        self._synced_guilds.discard(guild.id)
        self.tree.clear_commands(guild=guild)

    async def on_message(self, message):
        # Cog listeners still receive messages; text commands are no longer invoked.
        return

    async def close(self):
        background = []
        for cog in self.cogs.values():
            for name in ("reminder_loop", "loop", "check_giveaways", "escalation_loop"):
                loop = getattr(cog, name, None)
                if loop is not None and loop.get_task() is not None:
                    loop.cancel()
                    background.append(loop.get_task())
        if background:
            await asyncio.gather(*background, return_exceptions=True)
        try:
            await super().close()
        finally:
            if self.db is not None:
                await self.db.close()
                self.db = None


bot = SigmaBot()


async def init_db():
    if DB_PATH != ":memory:":
        Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    try:
        await initialize_tables(db)
    except BaseException:
        await db.close()
        raise
    return db


async def initialize_tables(db):
    await db.execute("PRAGMA busy_timeout = 5000")
    await db.execute("PRAGMA journal_mode = WAL")
    await db.execute("""CREATE TABLE IF NOT EXISTS warns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                moderator_id INTEGER,
                reason TEXT,
                timestamp INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                timestamp INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                remind_at INTEGER,
                content TEXT
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                status TEXT,
                created_at INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS xp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                xp INTEGER,
                level INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS giveaways (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                message_id INTEGER,
                ends_at INTEGER,
                prize TEXT,
                active INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                author_id INTEGER,
                content TEXT,
                done INTEGER
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS countdowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                end_at INTEGER,
                title TEXT
            )""")
    await db.execute("""CREATE TABLE IF NOT EXISTS absences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                user_id INTEGER,
                until INTEGER,
                reason TEXT
            )""")
    # Migrate existing databases without replacing user data.
    cur = await db.execute("PRAGMA table_info(giveaways)")
    if "winners" not in {row[1] for row in await cur.fetchall()}:
        await db.execute("ALTER TABLE giveaways ADD COLUMN winners INTEGER NOT NULL DEFAULT 1")
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS giveaway_entries (
            message_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
            PRIMARY KEY (message_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS reaction_roles (
            guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, message_id INTEGER NOT NULL,
            emoji TEXT NOT NULL, role_id INTEGER NOT NULL,
            PRIMARY KEY (guild_id, message_id, emoji)
        );
        CREATE TABLE IF NOT EXISTS raid_overwrites (
            guild_id INTEGER NOT NULL, channel_id INTEGER PRIMARY KEY, send_messages INTEGER
        );
        UPDATE xp SET xp = (SELECT MAX(x2.xp) FROM xp x2
            WHERE x2.guild_id = xp.guild_id AND x2.user_id = xp.user_id),
            level = (SELECT MAX(x2.level) FROM xp x2
            WHERE x2.guild_id = xp.guild_id AND x2.user_id = xp.user_id);
        DELETE FROM xp WHERE id NOT IN (SELECT MAX(id) FROM xp GROUP BY guild_id, user_id);
        DELETE FROM absences WHERE id NOT IN (SELECT MAX(id) FROM absences GROUP BY guild_id, user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS xp_user ON xp (guild_id, user_id);
        CREATE UNIQUE INDEX IF NOT EXISTS absence_user ON absences (guild_id, user_id);
        CREATE INDEX IF NOT EXISTS warns_user ON warns (guild_id, user_id);
        CREATE INDEX IF NOT EXISTS reminders_due ON reminders (remind_at);
        CREATE INDEX IF NOT EXISTS countdowns_due ON countdowns (end_at);
        CREATE INDEX IF NOT EXISTS giveaways_due ON giveaways (active, ends_at);
    """)
    await db.commit()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------")
    await bot.sync_connected_guilds()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.NoPrivateMessage):
        await ctx.send("Dieser Befehl ist nur auf einem Server verfügbar.", ephemeral=True)
    elif isinstance(error, commands.UserInputError):
        await ctx.send(f"Ungültige Eingabe. Prüfe die Optionen von /{ctx.command} oder nutze /help.", ephemeral=True)
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("Dir oder dem Bot fehlen die benötigten Berechtigungen.", ephemeral=True)
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Bitte warte {error.retry_after:.0f} Sekunden.", ephemeral=True)
    else:
        # Do not expose API URLs, credentials or internal exceptions to Discord.
        original = getattr(error, "original", error)
        log.error("Command %s failed (%s)", ctx.command, type(original).__name__)
        await ctx.send("Der Befehl konnte nicht ausgeführt werden. Prüfe die Bot-Berechtigungen.", ephemeral=True)


async def load_cogs(client=None):
    client = client or bot
    for fname in EXTENSIONS:
        await client.load_extension(f"cogs.{fname}")
        log.info("Loaded cog: %s", fname)


async def main():
    if not TOKEN or TOKEN in ("your-bot-token-here", "your_bot_token_here"):
        raise RuntimeError("DISCORD_TOKEN fehlt. Trage einen gültigen Token in .env ein.")
    async with bot:
        await bot.start(TOKEN)


def run():
    """Shared synchronous entry point for local and hosted startup."""
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")


if __name__ == "__main__":
    run()
