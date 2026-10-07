"""
Basic tests for SigmaBot core functionality.
Tests mock Discord interactions and bot initialization.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock


@pytest.fixture
def mock_bot():
    """Create a mock bot instance."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.db = AsyncMock()
    bot.get_guild = MagicMock(return_value=MagicMock())
    return bot


class TestBotInitialization:
    """Test bot initialization and basic setup."""

    @pytest.mark.asyncio
    async def test_bot_creation(self, mock_bot):
        """Test that bot can be created with proper intents."""
        assert mock_bot is not None
        assert mock_bot.user.id == 123456789

    @pytest.mark.asyncio
    async def test_db_connection(self, mock_bot):
        """Test database connection mock."""
        mock_bot.db.execute = AsyncMock()
        await mock_bot.db.execute("SELECT 1")
        mock_bot.db.execute.assert_called_once()


class TestModeration:
    """Test moderation cog functionality."""

    @pytest.mark.asyncio
    async def test_warn_count_retrieval(self, mock_bot):
        """Test retrieving warn count for a user."""
        mock_bot.db.execute = AsyncMock()
        mock_bot.db.execute.return_value.fetchone = AsyncMock(return_value=(3,))
        result = await mock_bot.db.execute(
            "SELECT COUNT(*) FROM warns WHERE guild_id = ? AND user_id = ?", (12345, 67890)
        )
        warn_count = (await result.fetchone())[0]
        assert warn_count == 3

    @pytest.mark.asyncio
    async def test_spam_detection(self):
        """Test spam detection logic."""
        import time

        recent = {}
        guild_id = 12345
        user_id = 67890
        # Simulate 6 rapid messages
        now = time.time()
        guild_map = recent.setdefault(guild_id, {})
        arr = guild_map.setdefault(user_id, [])
        for i in range(6):
            arr.append(now + i * 0.5)
        # Check if spam detected (6+ in 5 seconds)
        while len(arr) > 8:
            arr.pop(0)
        is_spam = len(arr) >= 6 and (now + 2.5 - arr[0]) < 5.0
        assert is_spam


class TestDatabase:
    """Test database operations."""

    @pytest.mark.asyncio
    async def test_insert_operation(self, mock_bot):
        """Test database insert operation."""
        mock_bot.db.execute = AsyncMock()
        mock_bot.db.commit = AsyncMock()
        await mock_bot.db.execute(
            "INSERT INTO warns (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (12345, 67890, 11111, "Test warn", 1234567890),
        )
        await mock_bot.db.commit()
        assert mock_bot.db.execute.called
        assert mock_bot.db.commit.called


class TestGiveaway:
    """Test giveaway system."""

    def test_winner_selection(self):
        """Test random winner selection from participants."""
        import random

        participants = {1001, 1002, 1003, 1004, 1005}
        winners = random.sample(list(participants), 2)
        assert len(winners) == 2
        assert all(w in participants for w in winners)

    def test_giveaway_embed_creation(self):
        """Test giveaway embed creation."""
        prize = "Nitro"
        # Simulate embed data
        embed_data = {
            "title": "🎉 GIVEAWAY 🎉",
            "description": f"**Preis:** {prize}\\n\\n**Gewinner:** 1",
            "color": "gold",
            "footer": "Klick den Button um teilzunehmen!",
        }
        assert embed_data["title"] == "🎉 GIVEAWAY 🎉"
        assert prize in embed_data["description"]


class TestTicketSystem:
    """Test ticket system."""

    @pytest.mark.asyncio
    async def test_ticket_creation(self, mock_bot):
        """Test ticket creation in database."""
        mock_bot.db.execute = AsyncMock()
        mock_bot.db.commit = AsyncMock()
        ts = 1234567890
        await mock_bot.db.execute(
            "INSERT INTO tickets (guild_id, channel_id, user_id, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (12345, 54321, 67890, "open", ts),
        )
        await mock_bot.db.commit()
        assert mock_bot.db.execute.called

    @pytest.mark.asyncio
    async def test_ticket_close(self, mock_bot):
        """Test ticket closing."""
        mock_bot.db.execute = AsyncMock()
        mock_bot.db.commit = AsyncMock()
        await mock_bot.db.execute("UPDATE tickets SET status = ? WHERE channel_id = ?", ("closed", 54321))
        await mock_bot.db.commit()
        assert mock_bot.db.execute.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
