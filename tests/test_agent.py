import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


async def test_text_and_normal_replies_are_forwarded():
    with patch("google.genai.Client"):
        agent = importlib.import_module("app.agent")

    sent = asyncio.Event()
    message = SimpleNamespace(
        data=None, server_content=SimpleNamespace(interrupted=True), tool_call=None
    )

    async def inputs():
        yield {"text": "Hello"}
        await asyncio.Event().wait()

    async def send(**item):
        assert item == {"text": "Hello"}
        sent.set()

    class Finished(Exception):
        pass

    async def receive():
        await sent.wait()
        yield message
        raise Finished

    session = SimpleNamespace(send_realtime_input=send, receive=receive)
    connection = AsyncMock()
    connection.__aenter__.return_value = session
    bridge = SimpleNamespace(
        inputs=inputs, play=AsyncMock(), interrupt=AsyncMock(),
        transcript=AsyncMock(), tool_event=AsyncMock(),
    )
    with patch.object(agent.client.aio.live, "connect", return_value=connection):
        with pytest.raises(ExceptionGroup) as caught:
            await asyncio.wait_for(agent.run_agent(bridge), timeout=2)
    assert all(isinstance(error, Finished) for error in caught.value.exceptions)
    bridge.interrupt.assert_awaited_once()
    bridge.transcript.assert_awaited_once_with(message)
