"""Exercise Discord slash registration and hybrid runtime checks without Discord credentials."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
    "name,permission",
    [
        ("ban", "ban_members"),
        ("kick", "kick_members"),
        ("warn", "manage_messages"),
        ("reactionrole", "manage_roles"),
        ("close", "manage_channels"),
        ("giveaway", "manage_guild"),
        ("checkip", "administrator"),
    ],
)
async def test_slash_permission_checks_remain_enforced(slash_bot, name, permission):
    command = slash_bot.tree.get_command(name)
    assert getattr(command.default_permissions, permission)
    ctx = SimpleNamespace(
        guild=SimpleNamespace(id=1), permissions=discord.Permissions.none(), bot_permissions=discord.Permissions.all()
    )
    interaction = SimpleNamespace(client=slash_bot, _baton=ctx)
    with pytest.raises(commands.MissingPermissions):
        await command._check_can_run(interaction)
    setattr(ctx.permissions, permission, True)
    assert await command._check_can_run(interaction)


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
