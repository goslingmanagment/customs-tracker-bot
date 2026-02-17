from core.exceptions import StartupConfigError
import bot


def test_run_returns_exit_code_on_startup_error(monkeypatch):
    async def _main():
        raise StartupConfigError(
            code="x",
            title="bad",
            details=["d"],
            hints=["h"],
            exit_code=7,
        )

    monkeypatch.setattr(bot, "main", _main)

    assert bot.run() == 7


def test_run_returns_zero_on_success(monkeypatch):
    async def _main():
        return None

    monkeypatch.setattr(bot, "main", _main)

    assert bot.run() == 0
