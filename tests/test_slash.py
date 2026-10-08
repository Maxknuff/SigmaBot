"""Exercise Discord slash registration and hybrid runtime checks without Discord credentials."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, PropertyMock, patch

import discord
import pytest
from discord.ext import commands

import bot as core
from cogs.utils import snowflake


@pytest.fixture
async def slash_bot(monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", ":memory:")
    client = core.SigmaBot()
    async with client:
        with patch.object(client.tree, "sync", new_callable=AsyncMock) as sync:
            await client.setup_hook()
            sync.assert_awaited_once_with()
        yield client


async def test_all_existing_commands_have_valid_guild_slash_schemas(slash_bot):
    expected = {
        "help",
        "warn",
        "warns",
        "mute",
        "unmute",
        "kick",
        "ban",
        "unlock",
        "reactionrole",
        "remind",
        "checkip",
        "scanurl",
        "serverstats",
        "ticket",
        "ticketinfo",
        "close",
        "level",
        "giveaway",
        "reroll",
        "todo_add",
        "todo_list",
        "todo_done",
        "countdown",
        "away",
    }
    assert {c.name for c in slash_bot.tree.get_commands()} == expected
    for command in slash_bot.tree.get_commands():
        data = command.to_dict(slash_bot.tree)
        assert data["dm_permission"] is False
        assert data["contexts"] == [0]
        assert 1 <= len(data["description"]) <= 100
        for option in data["options"]:
            assert option["description"] != "…"
            assert 1 <= len(option["description"]) <= 100
        assert isinstance(slash_bot.get_command(command.name), commands.HybridCommand)


async def test_snowflake_options_are_strings_and_member_options_are_discord_users(slash_bot):
    for name in ("reroll", "reactionrole"):
        param = next(p for p in slash_bot.tree.get_command(name).parameters if p.name == "message_id")
        assert param.type is discord.AppCommandOptionType.string
    assert slash_bot.tree.get_command("ban").parameters[0].type is discord.AppCommandOptionType.user
    assert slash_bot.tree.get_command("reactionrole").parameters[2].type is discord.AppCommandOptionType.role
    assert slash_bot.tree.get_command("ticketinfo").parameters[0].type is discord.AppCommandOptionType.channel


@pytest.mark.parametrize(
    "name",
    [
        "help",
        "warn",
        "warns",
        "mute",
        "unmute",
        "kick",
        "ban",
        "unlock",
        "reactionrole",
        "remind",
        "checkip",
        "scanurl",
        "serverstats",
        "ticketinfo",
        "close",
        "level",
        "giveaway",
        "reroll",
        "todo_add",
        "todo_list",
        "todo_done",
        "countdown",
        "away",
    ],
)
async def test_all_commands_except_ticket_require_real_administrator(slash_bot, name):
    command = slash_bot.tree.get_command(name)
    assert command.default_permissions == discord.Permissions(administrator=True)
    # Moderation permissions or a role called Administrator are insufficient.
    moderator = discord.Permissions.all()
    moderator.administrator = False
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        command=slash_bot.get_command(name),
        author=SimpleNamespace(guild_permissions=moderator),
        permissions=moderator,
        bot_permissions=discord.Permissions.all(),
    )
    interaction = SimpleNamespace(client=slash_bot, _baton=ctx)
    with pytest.raises(commands.MissingPermissions) as error:
        await command._check_can_run(interaction)
    assert error.value.missing_permissions == ["administrator"]
    ctx.author.guild_permissions = discord.Permissions.all()
    ctx.permissions = discord.Permissions.all()
    assert await command._check_can_run(interaction)


async def test_ticket_is_available_to_ordinary_members(slash_bot):
    command = slash_bot.tree.get_command("ticket")
    assert command.default_permissions is None
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        command=slash_bot.get_command("ticket"),
        author=SimpleNamespace(guild_permissions=discord.Permissions.none()),
        permissions=discord.Permissions.none(),
        bot_permissions=discord.Permissions.all(),
    )
    assert await command._check_can_run(SimpleNamespace(client=slash_bot, _baton=ctx))


async def test_discord_permission_override_cannot_bypass_admin_check(slash_bot):
    command = slash_bot.tree.get_command("help")
    command.default_permissions = None
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=1),
        command=slash_bot.get_command("help"),
        author=SimpleNamespace(guild_permissions=discord.Permissions.none()),
        permissions=discord.Permissions.all(),
        bot_permissions=discord.Permissions.all(),
    )
    with pytest.raises(commands.MissingPermissions):
        await command._check_can_run(SimpleNamespace(client=slash_bot, _baton=ctx))


async def test_guild_sync_keeps_admin_policy_and_public_ticket(slash_bot):
    guild = discord.Object(id=123)
    with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
        sync.return_value = slash_bot.tree.get_commands()
        await slash_bot.sync_guild_commands(guild)
    for command in slash_bot.tree.get_commands(guild=guild):
        permissions = command.to_dict(slash_bot.tree)["default_member_permissions"]
        assert permissions == (None if command.name == "ticket" else 8)


async def test_slash_commands_reject_private_messages(slash_bot):
    ctx = SimpleNamespace(guild=None)
    interaction = SimpleNamespace(client=slash_bot, _baton=ctx)
    with pytest.raises(commands.NoPrivateMessage):
        await slash_bot.tree.get_command("help")._check_can_run(interaction)


async def test_text_messages_no_longer_invoke_commands(slash_bot):
    with patch.object(slash_bot, "process_commands", new_callable=AsyncMock) as process:
        await slash_bot.on_message(SimpleNamespace(content="!ban someone"))
        await slash_bot.on_message(SimpleNamespace(content="/ban someone"))
        process.assert_not_awaited()
    assert await slash_bot.get_prefix(SimpleNamespace(content="!help")) == []
    assert "on_message" in slash_bot.extra_events  # Cog listeners are still registered.


async def test_slash_commands_defer_before_slow_work(slash_bot):
    ctx = SimpleNamespace(
        interaction=SimpleNamespace(response=SimpleNamespace(is_done=lambda: False)), defer=AsyncMock()
    )
    await slash_bot._before_invoke(ctx)
    ctx.defer.assert_awaited_once()
    ctx.interaction.response.is_done = lambda: True
    await slash_bot._before_invoke(ctx)
    assert ctx.defer.await_count == 1


async def test_help_lists_slash_commands(slash_bot):
    ctx = SimpleNamespace(bot=slash_bot, send=AsyncMock())
    await slash_bot.get_command("help").callback(ctx)
    output = "".join(call.args[0] for call in ctx.send.await_args_list)
    assert "/giveaway" in output
    assert "/help" in output
    assert "!help" not in output


@pytest.mark.parametrize("value", ["1234567890123456789", "18446744073709551615"])
def test_snowflakes_are_parsed_without_rounding(value):
    assert str(snowflake(value)) == value


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.23", "18446744073709551616"])
def test_invalid_snowflakes_are_rejected(value):
    with pytest.raises(commands.BadArgument):
        snowflake(value)


async def test_slash_errors_are_private():
    ctx = SimpleNamespace(command="ban", send=AsyncMock())
    await core.on_command_error(ctx, commands.MissingPermissions(["ban_members"]))
    assert ctx.send.await_args.kwargs["ephemeral"] is True


async def test_failed_slash_sync_aborts_start_and_closes_database(monkeypatch):
    monkeypatch.setattr(core, "DB_PATH", ":memory:")
    client = core.SigmaBot()
    with pytest.raises(RuntimeError, match="sync failed"):
        async with client:
            with patch.object(client.tree, "sync", side_effect=RuntimeError("sync failed")):
                await client.setup_hook()
    assert client.db is None


async def test_direct_guild_sync_copies_all_commands_and_only_runs_once(slash_bot):
    guild = discord.Object(id=123456789012345678)
    with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
        sync.return_value = slash_bot.tree.get_commands()
        await slash_bot.sync_guild_commands(guild)
        await slash_bot.sync_guild_commands(guild)
        sync.assert_awaited_once_with(guild=guild)
    assert {c.name for c in slash_bot.tree.get_commands(guild=guild)} == {c.name for c in slash_bot.tree.get_commands()}


async def test_concurrent_ready_events_do_not_duplicate_guild_sync(slash_bot):
    import asyncio

    guild = discord.Object(id=123456789012345678)
    with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
        sync.return_value = slash_bot.tree.get_commands()
        await asyncio.gather(*(slash_bot.sync_guild_commands(guild) for _ in range(4)))
        sync.assert_awaited_once_with(guild=guild)


async def test_failed_guild_sync_logs_problem_and_can_retry(slash_bot, caplog):
    guild = discord.Object(id=123456789012345678)
    response = SimpleNamespace(status=403, reason="Forbidden")
    with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
        sync.side_effect = discord.Forbidden(response, {"code": 50001, "message": "Missing Access"})
        await slash_bot.sync_guild_commands(guild)
        assert guild.id not in slash_bot._synced_guilds
        assert "applications.commands" in caplog.text
        sync.side_effect = None
        sync.return_value = slash_bot.tree.get_commands()
        await slash_bot.sync_guild_commands(guild)
        assert guild.id in slash_bot._synced_guilds


async def test_transient_guild_failure_does_not_block_other_servers(slash_bot):
    first, second = discord.Object(id=123), discord.Object(id=456)
    response = SimpleNamespace(status=500, reason="Error")
    with patch.object(type(slash_bot), "guilds", new_callable=PropertyMock) as guilds:
        guilds.return_value = [first, second]
        with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
            sync.side_effect = [discord.HTTPException(response, "temporary"), slash_bot.tree.get_commands()]
            await slash_bot.sync_connected_guilds()
    assert first.id not in slash_bot._synced_guilds
    assert second.id in slash_bot._synced_guilds


async def test_join_and_remove_support_rejoining_server(slash_bot):
    guild = discord.Object(id=123)
    with patch.object(slash_bot.tree, "sync", new_callable=AsyncMock) as sync:
        sync.return_value = slash_bot.tree.get_commands()
        await slash_bot.on_guild_join(guild)
        await slash_bot.on_guild_remove(guild)
        assert guild.id not in slash_bot._synced_guilds
        assert slash_bot.tree.get_commands(guild=guild) == []
        await slash_bot.on_guild_join(guild)
        assert sync.await_count == 2


def test_installation_link_uses_current_app_and_both_scopes():
    from urllib.parse import parse_qs, urlparse

    client = core.SigmaBot()
    client._connection.application_id = 123456789012345678
    query = parse_qs(urlparse(client.installation_url()).query)
    assert query["client_id"] == ["123456789012345678"]
    assert set(query["scope"][0].split()) == {"bot", "applications.commands"}


async def test_ready_handler_runs_server_registration():
    with patch.object(core, "bot") as client:
        client.user = SimpleNamespace(id=123)
        client.sync_connected_guilds = AsyncMock()
        await core.on_ready()
        client.sync_connected_guilds.assert_awaited_once_with()
