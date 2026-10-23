"""Checkpoint: step 2, persona via config. Same code as step 1: edit app/persona/receptionist.md
and VOICE in .env, then restart the server.

Copy over app/agent.py to catch up:  cp checkpoints/step2_persona.py app/agent.py

THE WORKSHOP FILE: one Live API session between a browser and Gemini.

Everything the fenced block calls is a small helper:
build_live_config (config.py), registry.run (tools/registry.py) and the bridge methods (bridge.py).
"""

import asyncio

from google import genai

from app.bridge import BrowserBridge
from app.config import build_live_config, settings

client = genai.Client()  # Reads GEMINI_API_KEY, or the GOOGLE_CLOUD_* Vertex AI settings, from .env


async def run_agent(bridge: BrowserBridge) -> None:
    """Stream the guest's voice to Gemini and Gemini's voice, transcripts and tool calls back."""
    # === LIVE CODING START ===
    async with client.aio.live.connect(model=settings.model, config=build_live_config(settings)) as session:
        async def send_inputs():
            async for item in bridge.inputs():
                await session.send_realtime_input(**item)

        async def receive_replies():
            while True:  # receive() ends after every turn
                async for msg in session.receive():
                    await bridge.play(msg.data)

        async with asyncio.TaskGroup() as tg:
            tg.create_task(send_inputs())
            tg.create_task(receive_replies())
    # === LIVE CODING END ===
