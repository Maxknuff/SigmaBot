"""Regression tests exercise the real cogs against SQLite without logging in to Discord."""

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import discord
import pytest
from discord.ext import commands, tasks

import bot as core
from cogs.absence import Absence
from cogs.community import Community, emoji_key
from cogs.countdown import Countdown
from cogs.giveaway import Giveaway, JoinButton
from cogs.moderation import Moderation
from cogs.organization import Organization
from cogs.security import Security
from cogs.tickets import CloseButton, close_ticket
from cogs.todo import Todo
from cogs.utils import deliver, positive_seconds
from cogs.xp import XP


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", ":memory:")
    db = await core.init_db()
    result = SimpleNamespace(
        db=db,
        db_lock=asyncio.Lock(),
        user=SimpleNamespace(id=999),
        get_guild=MagicMock(),
        get_cog=MagicMock(return_value=None),
        add_view=MagicMock(),
        wait_until_ready=AsyncMock(),
    )
    with patch.object(tasks.Loop, "start"):
        yield result
    await db.close()


def context():
    return SimpleNamespace(
        guild=SimpleNamespace(id=1), channel=SimpleNamespace(id=2), author=SimpleNamespace(id=3), send=AsyncMock()
    )


def message():
    guild = SimpleNamespace(id=1, owner_id=100, me=SimpleNamespace(top_role=10))
    author = SimpleNamespace(id=3, bot=False, top_role=1, mention="<@3>")
    return SimpleNamespace(
        guild=guild,
        author=author,
        channel=SimpleNamespace(id=2, send=AsyncMock()),
        content="hello",
        mentions=[],
        delete=AsyncMock(),
    )


async def test_all_extensions_load_and_close_without_login(monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", ":memory:")
    client = core.SigmaBot()
    async with client:
        with patch.object(client.tree, "sync", new_callable=AsyncMock) as sync:
            await client.setup_hook()
            sync.assert_awaited_once()
        await asyncio.sleep(0)
        assert len(client.extensions) == 11
        assert len(client.commands) == 24
        for name, attr in [
            ("Organization", "reminder_loop"),
            ("Countdown", "loop"),
            ("Giveaway", "check_giveaways"),
            ("Moderation", "escalation_loop"),
        ]:
            loop = getattr(client.get_cog(name), attr)
            assert not loop.failed()
            assert loop.current_loop == 0  # Waiting for Discord readiness.
        connection = client.db
    assert client.db is None
    with pytest.raises(ValueError):
        await connection.execute("SELECT 1")


async def test_existing_database_migrates_idempotently(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    db = await aiosqlite.connect(path)
    await db.executescript("""
        CREATE TABLE giveaways (id INTEGER PRIMARY KEY, guild_id INTEGER, channel_id INTEGER,
            message_id INTEGER, ends_at INTEGER, prize TEXT, active INTEGER);
        INSERT INTO giveaways VALUES (1, 1, 2, 4, 0, 'Old prize', 1);
        CREATE TABLE xp (id INTEGER PRIMARY KEY, guild_id INTEGER, user_id INTEGER, xp INTEGER, level INTEGER);
        INSERT INTO xp VALUES (1, 1, 3, 90, 1), (2, 1, 3, 80, 1);
        CREATE TABLE absences (id INTEGER PRIMARY KEY, guild_id INTEGER, user_id INTEGER, until INTEGER, reason TEXT);
        INSERT INTO absences VALUES (1, 1, 3, 10, 'old'), (2, 1, 3, 20, 'new');
    """)
    await db.close()
    monkeypatch.setattr(core, "DB_PATH", str(path))
    for _ in range(2):
        db = await core.init_db()
        try:
            assert await (await db.execute("SELECT prize, winners FROM giveaways")).fetchone() == ("Old prize", 1)
            assert await (await db.execute("SELECT xp FROM xp")).fetchall() == [(90,)]
            assert await (await db.execute("SELECT reason FROM absences")).fetchall() == [("new",)]
        finally:
            await db.close()


@pytest.mark.parametrize("seconds", [-1, 0, 31536001])
def test_invalid_duration(seconds):
    with pytest.raises(commands.BadArgument):
        positive_seconds(seconds)


async def test_missing_token_fails_before_database(monkeypatch):
    monkeypatch.setattr(core, "TOKEN", None)
    with patch.object(core, "init_db", new_callable=AsyncMock) as init:
        with pytest.raises(RuntimeError, match="DISCORD_TOKEN"):
            await core.main()
        init.assert_not_awaited()


async def test_dm_commands_rejected():
    with pytest.raises(commands.NoPrivateMessage):
        await core.guild_only(SimpleNamespace(guild=None))


async def test_away_replaces_previous_status(client):
    cog, ctx = Absence(client), context()
    await cog.away.callback(cog, ctx, 60, reason="old")
    await cog.away.callback(cog, ctx, 120, reason="new")
    assert await (await client.db.execute("SELECT reason FROM absences")).fetchall() == [("new",)]


async def test_todo_cannot_complete_other_channel(client):
    await client.db.execute("INSERT INTO todos (id, guild_id, channel_id, done) VALUES (1, 1, 88, 0)")
    cog = Todo(client)
    await cog.todo_done.callback(cog, context(), 1)
    assert await (await client.db.execute("SELECT done FROM todos")).fetchone() == (0,)


async def test_xp_concurrent_messages_do_not_duplicate_or_farm(client):
    cog = XP(client)
    msg = message()
    await asyncio.gather(*(cog.on_message(msg) for _ in range(10)))
    rows = await (await client.db.execute("SELECT xp, level FROM xp")).fetchall()
    assert len(rows) == 1
    assert 5 <= rows[0][0] <= 12
    assert rows[0][1] == 1


async def test_spam_window_and_cooldown(client):
    cog, msg = Moderation(client), message()
    cog._escalate_user = AsyncMock()
    with patch("cogs.moderation.time.time", return_value=100):
        for _ in range(20):
            await cog.on_message(msg)
    assert await (await client.db.execute("SELECT COUNT(*) FROM warns")).fetchone() == (1,)
    with patch("cogs.moderation.time.time", return_value=140):
        await cog.on_message(msg)
    assert await (await client.db.execute("SELECT COUNT(*) FROM warns")).fetchone() == (1,)


async def test_slow_messages_not_spam(client):
    cog, msg = Moderation(client), message()
    with patch("cogs.moderation.time.time", side_effect=[100, 110, 120, 130, 140, 150]):
        for _ in range(6):
            await cog.on_message(msg)
    assert await (await client.db.execute("SELECT COUNT(*) FROM warns")).fetchone() == (0,)


async def test_ticket_close_rejects_non_ticket_and_unauthorized_user(client):
    channel = SimpleNamespace(
        id=2,
        guild=SimpleNamespace(id=1),
        delete=AsyncMock(),
        permissions_for=lambda actor: SimpleNamespace(manage_channels=False),
    )
    with pytest.raises(commands.BadArgument):
        await close_ticket(client, channel, SimpleNamespace(id=3))
    await client.db.execute("INSERT INTO tickets (guild_id, channel_id, user_id, status) VALUES (1, 2, 3, 'open')")
    with pytest.raises(commands.MissingPermissions):
        await close_ticket(client, channel, SimpleNamespace(id=4))
    channel.delete.assert_not_awaited()
    await close_ticket(client, channel, SimpleNamespace(id=3))
    channel.delete.assert_awaited_once()
    assert await (await client.db.execute("SELECT status FROM tickets")).fetchone() == ("closed",)


async def test_failed_ticket_delete_keeps_ticket_open(client):
    channel = SimpleNamespace(
        id=2,
        guild=SimpleNamespace(id=1),
        delete=AsyncMock(side_effect=http_error(403)),
        permissions_for=lambda actor: SimpleNamespace(manage_channels=True),
    )
    await client.db.execute("INSERT INTO tickets (guild_id, channel_id, user_id, status) VALUES (1, 2, 3, 'open')")
    with pytest.raises(discord.HTTPException):
        await close_ticket(client, channel, SimpleNamespace(id=3))
    assert await (await client.db.execute("SELECT status FROM tickets")).fetchone() == ("open",)


async def test_views_are_persistent(client):
    assert JoinButton(client, 1).is_persistent()
    assert CloseButton(client, 2).is_persistent()


async def test_giveaway_button_records_once_and_rejects_expired(client):
    await client.db.execute(
        "INSERT INTO giveaways (id, guild_id, message_id, ends_at, active) VALUES (1, 1, 4, ?, 1)",
        (int(time.time()) + 100,),
    )
    interaction = SimpleNamespace(
        user=SimpleNamespace(id=3),
        guild_id=1,
        response=SimpleNamespace(defer=AsyncMock()),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    view = JoinButton(client, 1)
    await view.children[0].callback(interaction)
    await view.children[0].callback(interaction)
    assert await (await client.db.execute("SELECT * FROM giveaway_entries")).fetchall() == [(4, 3)]
    await client.db.execute("UPDATE giveaways SET ends_at = 0")
    interaction.user.id = 5
    await view.children[0].callback(interaction)
    assert await (await client.db.execute("SELECT COUNT(*) FROM giveaway_entries")).fetchone() == (1,)


async def test_giveaway_start_attaches_button(client):
    ctx = context()
    msg = SimpleNamespace(id=4, edit=AsyncMock())
    ctx.send.return_value = msg
    cog = Giveaway(client)
    await cog.giveaway.callback(cog, ctx, 60, 2, prize="Prize")
    view = msg.edit.await_args.kwargs["view"]
    assert view.is_persistent()
    assert await (await client.db.execute("SELECT winners FROM giveaways")).fetchone() == (2,)


async def test_giveaway_restores_view_and_reroll_after_restart(client):
    await client.db.execute(
        "INSERT INTO giveaways (id, guild_id, channel_id, message_id, active) VALUES (1, 1, 2, 4, 1)",
    )
    await client.db.execute("INSERT INTO giveaway_entries VALUES (4, 3)")
    cog = Giveaway(client)
    await cog.cog_load()
    client.add_view.assert_called_once()
    await client.db.execute("UPDATE giveaways SET active = 0")
    ctx = context()
    await cog.reroll.callback(cog, ctx, 4, 2)
    assert "<@3>" in ctx.send.await_args.args[0]


async def test_giveaway_multiple_winners_and_legacy_embed(client):
    await client.db.execute(
        "INSERT INTO giveaways (id, guild_id, channel_id, message_id, ends_at, prize, active, winners) "
        "VALUES (1, 1, 2, 4, 0, 'Prize', 1, 1)",
    )
    for uid in (3, 5, 6):
        await client.db.execute("INSERT INTO giveaway_entries VALUES (4, ?)", (uid,))
    msg = SimpleNamespace(id=4, reactions=[], embeds=[SimpleNamespace(description="**Gewinner:** 2")], edit=AsyncMock())
    channel = SimpleNamespace(fetch_message=AsyncMock(return_value=msg), send=AsyncMock())
    client.get_guild.return_value = SimpleNamespace(get_channel_or_thread=lambda cid: channel)
    cog = Giveaway(client)
    await cog.check_giveaways()
    description = channel.send.await_args.kwargs["embed"].description
    assert description.count("<@") == 2
    assert await (await client.db.execute("SELECT active FROM giveaways")).fetchone() == (0,)


async def test_reaction_roles_work_without_message_cache(client):
    await client.db.execute("INSERT INTO reaction_roles VALUES (1, 2, 4, '✅', 5)")
    role = MagicMock()
    role.is_default.return_value = False
    role.managed = False
    role.permissions.administrator = False
    role.__lt__.return_value = True
    member = SimpleNamespace(bot=False, add_roles=AsyncMock(), remove_roles=AsyncMock())
    guild = SimpleNamespace(
        get_role=lambda rid: role, get_member=lambda uid: member, owner_id=100, me=SimpleNamespace(id=999, top_role=10)
    )
    client.get_guild.return_value = guild
    cog = Community(client)
    payload = SimpleNamespace(guild_id=1, channel_id=2, message_id=4, user_id=3, emoji=discord.PartialEmoji(name="✅"))
    await cog.on_raw_reaction_add(payload)
    await cog.on_raw_reaction_remove(payload)
    member.add_roles.assert_awaited_once_with(role, reason="Reaktionsrolle")
    member.remove_roles.assert_awaited_once_with(role, reason="Reaktionsrolle entfernt")
    role.permissions.administrator = True
    await cog.on_raw_reaction_add(payload)
    assert member.add_roles.await_count == 1


def test_custom_emoji_uses_id_not_name():
    assert emoji_key("<:before:123456789012345678>") == emoji_key("<:renamed:123456789012345678>")


def http_error(status):
    cls = discord.NotFound if status == 404 else discord.HTTPException
    return cls(SimpleNamespace(status=status, reason="test"), "test")


@pytest.mark.parametrize("kind", ["reminder", "countdown"])
async def test_scheduled_job_retries_failure_then_delivers(client, kind):
    channel = SimpleNamespace(send=AsyncMock(side_effect=http_error(403)))
    client.get_guild.return_value = SimpleNamespace(get_channel_or_thread=lambda cid: channel)
    if kind == "reminder":
        await client.db.execute(
            "INSERT INTO reminders (guild_id, channel_id, user_id, remind_at, content) " "VALUES (1, 2, 3, 0, 'hello')"
        )
        cog, table, loop = Organization(client), "reminders", "reminder_loop"
    else:
        await client.db.execute(
            "INSERT INTO countdowns (guild_id, channel_id, end_at, title) " "VALUES (1, 2, 0, 'hello')"
        )
        cog, table, loop = Countdown(client), "countdowns", "loop"
    await getattr(cog, loop)()
    assert await (await client.db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone() == (1,)
    channel.send.side_effect = None
    await getattr(cog, loop)()
    assert await (await client.db.execute(f"SELECT COUNT(*) FROM {table}")).fetchone() == (0,)


async def test_missing_destination_does_not_leave_stale_job(client):
    client.get_guild.return_value = SimpleNamespace(
        get_channel_or_thread=lambda cid: None, fetch_channel=AsyncMock(side_effect=http_error(404))
    )
    assert await deliver(client, 1, 2, "hello")


@pytest.mark.parametrize(
    "url, suspicious",
    [
        ("https://example.com/login", False),
        ("https://example.com/free-gift", False),
        ("https://discord.com/login", False),
        ("https://discord.gift/abc", False),
        ("https://discord-nitro.example/claim", True),
        ("https://discord.com.evil.example/verify", True),
    ],
)
def test_url_heuristic_avoids_generic_false_positives(url, suspicious):
    assert Security(None)._heuristic_url_check(url) is suspicious


async def test_url_delete_failure_and_multiple_urls_warn_once(client):
    cog, msg = Security(client), message()
    msg.content = "https://discord-nitro.example/claim https://discord-nitro.example/gift"
    msg.delete.side_effect = http_error(403)
    cog.is_suspicious_url = AsyncMock(return_value=True)
    await cog.on_message(msg)
    assert await (await client.db.execute("SELECT COUNT(*) FROM warns")).fetchone() == (1,)
    assert "als verdächtig erkannt" in msg.channel.send.await_args.args[0]


async def test_invalid_ip_is_not_sent_to_api(client):
    with pytest.raises(commands.BadArgument):
        await Security(client)._check_ip_with_ipquality("not-an-ip")


async def test_invalid_url_rejected_without_api_key(client, monkeypatch):
    monkeypatch.delenv("URL_SCAN_API_KEY", raising=False)
    with pytest.raises(commands.BadArgument):
        await Security(client)._check_url_with_ipquality("file:///secret")


async def test_manual_mute_uses_timeout(client):
    cog = Moderation(client)
    ctx = context()
    ctx.guild.owner_id = 100
    ctx.guild.me = SimpleNamespace(top_role=10)
    ctx.author.top_role = 5
    target = SimpleNamespace(id=4, top_role=1, mention="<@4>", timeout=AsyncMock())
    await cog.mute.callback(cog, ctx, target, reason="test")
    assert target.timeout.await_args.args[0].days == 28


async def test_moderation_rejects_higher_ranked_member(client):
    cog = Moderation(client)
    ctx = context()
    ctx.guild.owner_id = 100
    ctx.guild.me = SimpleNamespace(top_role=10)
    ctx.author.top_role = 5
    target = SimpleNamespace(id=4, top_role=6, ban=AsyncMock())
    with pytest.raises(commands.BadArgument):
        await cog.ban.callback(cog, ctx, target)
    target.ban.assert_not_awaited()


async def test_unlock_preserves_unrelated_channel_overwrites(client):
    await client.db.execute("INSERT INTO raid_overwrites VALUES (1, 2, 0)")
    overwrite = discord.PermissionOverwrite(send_messages=False, attach_files=True, embed_links=False)
    channel = SimpleNamespace(id=2, overwrites_for=lambda role: overwrite, set_permissions=AsyncMock())
    ctx = context()
    ctx.guild.default_role = SimpleNamespace(id=1)
    ctx.guild.get_channel = lambda cid: channel
    cog = Moderation(client)
    await cog.unlock.callback(cog, ctx)
    restored = channel.set_permissions.await_args.kwargs["overwrite"]
    assert restored.send_messages is False
    assert restored.attach_files is True
    assert restored.embed_links is False
    assert await (await client.db.execute("SELECT COUNT(*) FROM raid_overwrites")).fetchone() == (0,)


async def test_security_scans_links_added_by_edit(client):
    cog = Security(client)
    cog.on_message = AsyncMock()
    before, after = message(), message()
    after.content = "https://discord-nitro.example/claim"
    await cog.on_message_edit(before, after)
    cog.on_message.assert_awaited_once_with(after)


async def test_extension_failure_aborts_start_and_closes_database(monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", ":memory:")
    client = core.SigmaBot()
    connection = None
    try:
        with pytest.raises(RuntimeError, match="broken extension"):
            async with client:
                with patch.object(client, "load_extension", side_effect=RuntimeError("broken extension")):
                    try:
                        await client.setup_hook()
                    finally:
                        connection = client.db
    finally:
        await client.close()
    assert client.db is None
    with pytest.raises(ValueError):
        await connection.execute("SELECT 1")


async def test_raid_uses_rolling_thirty_second_window(client):
    cog = Moderation(client)
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = 2
    channel.send = AsyncMock()
    channel.set_permissions = AsyncMock()
    channel.overwrites_for.return_value = discord.PermissionOverwrite(send_messages=True, attach_files=False)
    guild = SimpleNamespace(id=1, channels=[channel], text_channels=[channel], default_role=SimpleNamespace(id=1))
    member = SimpleNamespace(guild=guild)
    with patch("cogs.moderation.time.time", side_effect=[100, 120, 140, 160, 180]):
        for _ in range(5):
            await cog.on_member_join(member)
    channel.set_permissions.assert_not_awaited()
    with patch("cogs.moderation.time.time", side_effect=[200, 201, 202, 203, 204]):
        for _ in range(5):
            await cog.on_member_join(member)
    channel.set_permissions.assert_awaited_once()
    saved = await (await client.db.execute("SELECT send_messages FROM raid_overwrites")).fetchone()
    assert saved == (1,)
    assert channel.set_permissions.await_args.kwargs["overwrite"].attach_files is False


async def test_xp_never_downgrades_existing_level(client):
    await client.db.execute("INSERT INTO xp (guild_id, user_id, xp, level) VALUES (1, 3, 500, 8)")
    await XP(client).on_message(message())
    assert await (await client.db.execute("SELECT level FROM xp")).fetchone() == (8,)
