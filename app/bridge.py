"""BrowserBridge: the browser WebSocket as seen by the agent.

Browser -> server: binary frames are 16 kHz PCM16 mic audio, text frames are {"type": "text", "text": ...}.
Server -> browser: binary frames are 24 kHz PCM16 audio, text frames are JSON events for the UI.
"""

import json
from collections.abc import AsyncIterator

from fastapi import WebSocket, WebSocketDisconnect
from google.genai import types

from app.store import store


class BrowserBridge:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws

    async def inputs(self) -> AsyncIterator[dict]:
        """Yield kwargs for session.send_realtime_input: mic audio or typed text."""
        while True:
            message = await self.ws.receive()
            if message["type"] == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))
            if message.get("bytes"):
                yield {"audio": types.Blob(data=message["bytes"], mime_type="audio/pcm;rate=16000")}
            elif message.get("text"):
                yield {"text": json.loads(message["text"])["text"]}

    async def play(self, audio: bytes | None) -> None:
        """Send agent audio to the speakers."""
        if audio:
            await self.ws.send_bytes(audio)

    async def interrupt(self) -> None:
        """The guest started talking: drop any queued agent audio right now."""
        await self.send({"type": "interrupt"})

    async def transcript(self, msg: types.LiveServerMessage) -> None:
        """Forward guest/agent transcription snippets and end-of-turn markers."""
        content = msg.server_content
        if not content:
            return
        if content.input_transcription and content.input_transcription.text:
            await self.send({"type": "transcript", "role": "guest", "text": content.input_transcription.text})
        if content.output_transcription and content.output_transcription.text:
            await self.send({"type": "transcript", "role": "agent", "text": content.output_transcription.text})
        if content.turn_complete:
            await self.send({"type": "turn_complete"})

    async def tool_event(self, event: dict) -> None:
        """Show a tool call on the Front Desk panel, refresh bookings, and hang up after end_call."""
        await self.send({"type": "tool", **event})
        if event["phase"] == "end":
            await self.send({"type": "bookings", "bookings": store.all("bookings")})
            if event["name"] == "end_call":
                await self.send({"type": "hangup"})

    async def send(self, event: dict) -> None:
        await self.ws.send_text(json.dumps(event, ensure_ascii=False, default=str))
