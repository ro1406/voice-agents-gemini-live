"""THE WORKSHOP FILE: one Live API session between a browser and Gemini.

Everything the fenced block calls is a small helper:
build_live_config (config.py), registry.run (tools/registry.py) and the bridge methods (bridge.py).
"""

import asyncio

from google import genai

from app.bridge import BrowserBridge
from app.config import build_live_config, settings
from app.tools.registry import ToolRegistry

client = genai.Client()  # Reads GEMINI_API_KEY, or the GOOGLE_CLOUD_* Vertex AI settings, from .env


async def run_agent(bridge: BrowserBridge) -> None:
    """Stream the guest's voice to Gemini and Gemini's voice, transcripts and tool calls back."""
    registry = ToolRegistry(settings.tool_modules, on_event=bridge.tool_event)

    # === LIVE CODING START ===
    # TODO 1: open a session: async with client.aio.live.connect(model=..., config=build_live_config(settings, registry))
    # TODO 2: forward the browser: async for item in bridge.inputs(): await session.send_realtime_input(**item)
    # TODO 3: in a `while True` loop over session.receive(): bridge.play(msg.data), bridge.interrupt(), bridge.transcript(msg)
    # TODO 4: on msg.tool_call: await session.send_tool_response(function_responses=await registry.run(msg.tool_call))
    raise NotImplementedError("Live-code me! See the TODOs in starter/agent.py or checkpoints/.")
    # === LIVE CODING END ===
