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


'''
LiveServerMessage:

- msg.data: A slice of the agent's voice (24 kHz PCM) -> bridge.play()

- server_content.output_transcription: Caption of what the agent is saying -> bridge.transcript()

- server_content.input_transcription: Caption of what Gemini heard the guest say -> bridge.transcript()

- server_content.interrupted: "The guest cut in, I stopped" -> bridge.interrupt()

- server_content.turn_complete: "I've finished my turn" -> closes the caption bubble

- tool_call: "Please run this function for me" -> registry.run()
'''



async def run_agent(bridge: BrowserBridge) -> None:
    """Stream the guest's voice to Gemini and Gemini's voice, transcripts and tool calls back.
    
    Talk to Gemini:
    - send_realtime_input(audio=… / text=…): Live streaming, as it happens
    - send_tool_response(): Answering a tool call    
    """
    registry = ToolRegistry(settings.tool_modules, on_event=bridge.tool_event)

    # === LIVE CODING START ===
    # Connect to the Live API
    pass

        async def send_inputs():
            #Send human audio to Gemini
            pass


        async def answer(tool_call):
            #Call the tool, then send the response to Gemini
            pass

        async def receive_replies():
            #In a loop - receive messages from Gemini and take actions
            pass


        #Start the parallel tasks to listen to user and respond
        pass
    # === LIVE CODING END ===
