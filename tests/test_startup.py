"""Verify hosting and local startup use the same bot without contacting Discord."""

import importlib
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest

import bot


def test_importing_hosting_entry_does_not_start_bot(monkeypatch):
    startup = AsyncMock()
    monkeypatch.setattr(bot, "main", startup)
    importlib.import_module("main")
    startup.assert_not_awaited()


def test_hosting_entry_uses_existing_startup(monkeypatch):
    startup = AsyncMock()
    monkeypatch.setattr(bot, "main", startup)
    runpy.run_module("main", run_name="__main__")
    startup.assert_awaited_once()


def test_hosting_entry_handles_keyboard_interrupt(monkeypatch, capsys):
    monkeypatch.setattr(bot, "main", AsyncMock(side_effect=KeyboardInterrupt))
    runpy.run_module("main", run_name="__main__")
    assert "Bot stopped" in capsys.readouterr().out


@pytest.mark.parametrize("entry", ["main.py", "bot.py"])
def test_entry_reaches_token_validation_before_database(entry, tmp_path):
    # Empty token overrides any developer .env; no real Discord request is made.
    environment = dict(os.environ, DISCORD_TOKEN="", DATABASE_PATH=str(tmp_path / "untouched.db"))
    script = Path(__file__).resolve().parents[1] / entry
    result = subprocess.run(
        [sys.executable, "-B", "-u", str(script)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    assert result.returncode == 1
    assert "DISCORD_TOKEN fehlt" in result.stderr
    assert "can't open file" not in result.stderr
    assert not (tmp_path / "untouched.db").exists()
