from types import SimpleNamespace

import pytest

from handlers.middleware import UpdateLogMiddleware


@pytest.mark.asyncio
async def test_update_log_middleware_calls_handler_and_logs(monkeypatch):
    logged = []

    class _Logger:
        def info(self, event, **kwargs):
            logged.append((event, kwargs))

    monkeypatch.setattr("handlers.middleware.logger", _Logger())

    middleware = UpdateLogMiddleware()

    message = SimpleNamespace(
        message_id=100,
        text="hello",
        caption=None,
        chat=SimpleNamespace(id=-100),
        message_thread_id=777,
        from_user=SimpleNamespace(id=1, username="user"),
        reply_to_message=None,
        photo=[],
        is_topic_message=True,
    )
    event = SimpleNamespace(
        update_id=1,
        message=message,
        edited_message=None,
        callback_query=None,
    )

    async def _handler(_event, _data):
        return "ok"

    result = await middleware(_handler, event, {})

    assert result == "ok"
    assert logged
    assert logged[0][0] == "telegram_update_received"
    assert logged[0][1]["message_id"] == 100
