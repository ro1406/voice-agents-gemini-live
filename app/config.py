"""Settings from .env and the Live API session config."""

import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.genai import types

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
TIMEZONE = ZoneInfo("Asia/Dubai")


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("MODEL", "gemini-3.8-live")
    voice: str = os.getenv("VOICE", "Kore")
    persona_file: Path = ROOT / os.getenv("PERSONA_FILE", "app/persona/receptionist.md")
    tool_modules: tuple[str, ...] = tuple(os.getenv("TOOL_MODULES", "app.tools.hotel,app.tools.call").split(","))


settings = Settings()


def today() -> date:
    """Today's date at the hotel (Asia/Dubai)."""
    return datetime.now(TIMEZONE).date()


def system_prompt(persona_file: Path) -> str:
    """The persona, prefixed with today's date so the model can resolve 'next Friday'."""
    return f"Today is {today():%A, %d %B %Y} (Asia/Dubai).\n\n{persona_file.read_text(encoding='utf-8')}"


def build_live_config(settings: Settings, registry=None) -> types.LiveConnectConfig:
    """Everything the Live session needs: voice, persona, transcripts, VAD and tools."""
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=settings.voice)
            )
        ),
        system_instruction=system_prompt(settings.persona_file),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            # 500-800 ms of silence ends a turn; lower values cut guests off mid-sentence.
            automatic_activity_detection=types.AutomaticActivityDetection(silence_duration_ms=700)
        ),
        tools=[types.Tool(function_declarations=registry.declarations)] if registry else None,
        # Audio-only sessions are capped (~15 min, connections ~10 min). To outlast that:
        # context_window_compression=types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
        # session_resumption=types.SessionResumptionConfig(handle=previous_handle),
    )
