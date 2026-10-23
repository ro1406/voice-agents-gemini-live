"""Pre-flight check on venue Wi-Fi: a real Live session must call check_availability.

    uv run python scripts/smoke_test.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent import client  # noqa: E402
from app.config import build_live_config, settings  # noqa: E402
from app.tools.registry import ToolRegistry  # noqa: E402

QUESTION = "Hi, do you have a double room for two people next Friday for one night?"
log = logging.getLogger("smoke_test")


async def first_tool_call() -> list[str]:
    """Ask the question by text and return the names in the first tool call."""
    registry = ToolRegistry(settings.tool_modules)
    async with client.aio.live.connect(model=settings.model, config=build_live_config(settings, registry)) as session:
        await session.send_realtime_input(text=QUESTION)
        while True:
            async for msg in session.receive():
                if msg.tool_call:
                    for fc in msg.tool_call.function_calls:
                        log.info("Tool call: %s(%s)", fc.name, fc.args)
                    return [fc.name for fc in msg.tool_call.function_calls]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    log.info("Model %s, asking: %s", settings.model, QUESTION)
    try:
        names = asyncio.run(asyncio.wait_for(first_tool_call(), timeout=45))
    except TimeoutError:
        log.error("FAIL: no tool call within 45 s")
        return 1
    if "check_availability" not in names:
        log.error("FAIL: expected check_availability, got %s", names)
        return 1
    log.info("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
