"""Generate starter/agent.py from app/agent.py with the live-coding block replaced by TODOs.

    uv run python scripts/make_starter.py
"""

import logging
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "app" / "agent.py"
TARGET = ROOT / "starter" / "agent.py"
FENCE = re.compile(r"(    # === LIVE CODING START ===\n).*?(    # === LIVE CODING END ===\n)", re.DOTALL)

TODOS = """\
    # TODO 1: open a session: async with client.aio.live.connect(model=..., config=build_live_config(settings, registry))
    # TODO 2: forward the browser: async for item in bridge.inputs(): await session.send_realtime_input(**item)
    # TODO 3: in a `while True` loop over session.receive(): bridge.play(msg.data), bridge.interrupt(), bridge.transcript(msg)
    # TODO 4: on msg.tool_call: await session.send_tool_response(function_responses=await registry.run(msg.tool_call))
    raise NotImplementedError("Live-code me! See the TODOs in starter/agent.py or checkpoints/.")
"""


def make_starter(source: str) -> str:
    """Return the source with the fenced block swapped for the TODO stub."""
    starter, count = FENCE.subn(lambda m: m[1] + TODOS + m[2], source)
    if count != 1:
        raise ValueError("Expected exactly one LIVE CODING fence in app/agent.py")
    return starter


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    TARGET.parent.mkdir(exist_ok=True)
    TARGET.write_text(make_starter(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    logging.info("Wrote %s", TARGET.relative_to(ROOT))
