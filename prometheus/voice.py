from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("prometheus.voice")

OPENAI_AVAILABLE = False
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    pass

PYTTSX3_AVAILABLE = False
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    pass


class VoiceMode:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self._enabled: bool = False
        self._api_key = api_key
        self._openai_client: Optional[openai.OpenAI] = None
        self._tts_engine = None

        if OPENAI_AVAILABLE and api_key:
            self._openai_client = openai.OpenAI(api_key=api_key)

        if PYTTSX3_AVAILABLE:
            try:
                self._tts_engine = pyttsx3.init()
            except Exception:
                self._tts_engine = None

    def enable(self) -> bool:
        self._enabled = True
        logger.info("Voice mode enabled")
        return True

    def disable(self) -> bool:
        self._enabled = False
        logger.info("Voice mode disabled")
        return True

    def is_enabled(self) -> bool:
        return self._enabled

    def transcribe(self, audio_path: str) -> str:
        if not self._enabled:
            logger.warning("Voice mode is disabled; cannot transcribe")
            return ""

        if not OPENAI_AVAILABLE or self._openai_client is None:
            logger.warning("OpenAI Whisper not available; transcription skipped")
            return ""

        path = Path(audio_path)
        if not path.exists():
            logger.error("Audio file not found: %s", audio_path)
            return ""

        try:
            with open(path, "rb") as audio_file:
                transcript = self._openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return transcript.text
        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return ""

    def speak(self, text: str) -> bool:
        if not self._enabled:
            logger.warning("Voice mode is disabled; cannot speak")
            return False

        if self._tts_engine is not None:
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
                return True
            except Exception as exc:
                logger.error("Local TTS failed: %s", exc)

        if OPENAI_AVAILABLE and self._openai_client is not None:
            try:
                response = self._openai_client.audio.speech.create(
                    model="tts-1",
                    voice="alloy",
                    input=text,
                )
                import tempfile
                import subprocess

                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    f.write(response.content)
                    tmp_path = f.name

                subprocess.run(["afplay", tmp_path], check=True, capture_output=True)
                Path(tmp_path).unlink(missing_ok=True)
                return True
            except Exception as exc:
                logger.error("OpenAI TTS failed: %s", exc)

        logger.warning("No TTS engine available; text-only fallback")
        return False
