"""Verify real Context initial replies and followups stay private."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from discord.ext import commands

import bot as core
from cogs.utils import send_chunks


def private_context():
    context = object.__new__(core.PrivateCommandContext)
    context.interaction = SimpleNamespace(
        is_expired=lambda: False,
        response=SimpleNamespace(
            is_done=lambda: False,
            send_message=AsyncMock(return_value=SimpleNamespace(resource=None)),
        ),
        original_response=AsyncMock(),
        followup=SimpleNamespace(send=AsyncMock()),
    )
    return context


async def test_initial_command_response_is_private_even_with_false_override():
    ctx = private_context()
    await ctx.send("confirmation", ephemeral=False)
    assert ctx.interaction.response.send_message.await_args.kwargs["ephemeral"] is True
    ctx.interaction.followup.send.assert_not_awaited()


async def test_deferred_and_subsequent_responses_are_all_private():
    ctx = private_context()
    ctx.interaction.response.is_done = lambda: True
    await ctx.send("first")
    await ctx.send("second", ephemeral=False)
    assert ctx.interaction.followup.send.await_count == 2
    for call in ctx.interaction.followup.send.await_args_list:
        assert call.kwargs["ephemeral"] is True
    ctx.interaction.response.send_message.assert_not_awaited()


async def test_long_lists_keep_every_chunk_private():
    ctx = private_context()
    ctx.interaction.response.is_done = lambda: True
    await send_chunks(ctx, "a" * 4000)
    assert ctx.interaction.followup.send.await_count == 3
    for call in ctx.interaction.followup.send.await_args_list:
        assert call.kwargs["ephemeral"] is True
        assert len(call.kwargs["content"]) <= 1900


@pytest.mark.parametrize("missing", [False, True])
async def test_missing_or_expired_interaction_never_falls_back_to_public_channel(missing):
    ctx = private_context()
    if missing:
        ctx.interaction = None
    else:
        ctx.interaction.is_expired = lambda: True
    with patch.object(commands.Context, "send", new_callable=AsyncMock) as send:
        with pytest.raises(core.PrivateResponseUnavailable):
            await ctx.send("sensitive feedback")
        send.assert_not_awaited()


async def test_expired_response_error_handler_does_not_publish_feedback():
    ctx = SimpleNamespace(send=AsyncMock())
    await core.on_command_error(ctx, core.PrivateResponseUnavailable())
    await core.on_command_error(ctx, commands.CommandInvokeError(core.PrivateResponseUnavailable()))
    ctx.send.assert_not_awaited()


async def test_hybrid_context_creation_selects_private_context():
    client = core.SigmaBot()
    async with client:
        origin = SimpleNamespace()
        with patch.object(commands.Bot, "get_context", new_callable=AsyncMock) as get_context:
            await client.get_context(origin)
            get_context.assert_awaited_once_with(origin, cls=core.PrivateCommandContext)
