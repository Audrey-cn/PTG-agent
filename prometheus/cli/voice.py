"""Process-wide voice recording + TTS API for the TUI gateway."""

from __future__ import annotations

import contextlib
import logging
import os
import sys
import threading
from typing import TYPE_CHECKING, Any

from prometheus.tools.voice_mode import (
    create_audio_recorder,
    is_whisper_hallucination,
    play_audio_file,
    transcribe_recording,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def _debug(msg: str) -> None:
    """Emit a debug breadcrumb when PROMETHEUS_VOICE_DEBUG=1.

    Goes to stderr so the TUI gateway wraps it as a gateway.stderr event,
    which createGatewayEventHandler shows as an Activity line — exactly
    what we need to diagnose "why didn't the loop auto-restart?" in the
    user's real terminal without shipping a separate debug RPC.

    Any OSError / BrokenPipeError is swallowed because this fires from
    background threads (silence callback, TTS daemon, beep) where a
    broken stderr pipe must not kill the whole gateway — the main
    command pipe (stdin+stdout) is what actually matters.
    """
    if os.environ.get("PROMETHEUS_VOICE_DEBUG", "").strip() != "1":
        return
    with contextlib.suppress(BrokenPipeError, OSError):
        print(f"[voice] {msg}", file=sys.stderr, flush=True)


def _beeps_enabled() -> bool:
    """CLI parity: voice.beep_enabled in config.yaml (default True)."""
    try:
        from prometheus.cli.config import load_config

        voice_cfg = load_config().get("voice", {})
        if isinstance(voice_cfg, dict):
            return bool(voice_cfg.get("beep_enabled", True))
    except Exception:
        pass
    return True


def _play_beep(frequency: int, count: int = 1) -> None:
    """Audible cue matching cli.py's record/stop beeps.

    880 Hz single-beep on start (cli.py:_voice_start_recording line 7532),
    660 Hz double-beep on stop (cli.py:_voice_stop_and_transcribe line 7585).
    Best-effort — sounddevice failures are silently swallowed so the
    voice loop never breaks because a speaker was unavailable.
    """
    if not _beeps_enabled():
        return
    try:
        from prometheus.tools.voice_mode import play_beep

        play_beep(frequency=frequency, count=count)
    except Exception as e:
        _debug(f"beep {frequency}Hz failed: {e}")


_recorder = None
_recorder_lock = threading.Lock()


_continuous_lock = threading.Lock()
_continuous_active = False
_continuous_recorder: Any = None


_tts_playing = threading.Event()
_tts_playing.set()
_continuous_on_transcript: Callable[[str], None] | None = None
_continuous_on_status: Callable[[str], None] | None = None
_continuous_on_silent_limit: Callable[[], None] | None = None
_continuous_no_speech_count = 0
_CONTINUOUS_NO_SPEECH_LIMIT = 3


def start_recording() -> None:
    """Begin capturing from the default input device (push-to-talk).

    Idempotent — calling again while a recording is in progress is a no-op.
    """
    global _recorder

    with _recorder_lock:
        if _recorder is not None and getattr(_recorder, "is_recording", False):
            return
        rec = create_audio_recorder()
        rec.start()
        _recorder = rec


def stop_and_transcribe() -> str | None:
    """Stop the active push-to-talk recording, transcribe, return text.

    Returns ``None`` when no recording is active, when the microphone
    captured no speech, or when Whisper returned a known hallucination.
    """
    global _recorder

    with _recorder_lock:
        rec = _recorder
        _recorder = None

    if rec is None:
        return None

    wav_path = rec.stop()
    if not wav_path:
        return None

    try:
        result = transcribe_recording(wav_path)
    except Exception as e:
        logger.warning("voice transcription failed: %s", e)
        return None
    finally:
        try:
            if os.path.isfile(wav_path):
                os.unlink(wav_path)
        except Exception:
            pass

    if not result.get("success"):
        return None
    text = (result.get("transcript") or "").strip()
    if not text or is_whisper_hallucination(text):
        return None

    return text


def start_continuous(
    on_transcript: Callable[[str], None],
    on_status: Callable[[str], None] | None = None,
    on_silent_limit: Callable[[], None] | None = None,
    silence_threshold: int = 200,
    silence_duration: float = 3.0,
) -> None:
    """Start a VAD-driven continuous recording loop.

    The loop calls ``on_transcript(text)`` each time speech is detected and
    transcribed successfully, then auto-restarts. After
    ``_CONTINUOUS_NO_SPEECH_LIMIT`` consecutive silent cycles (no speech
    picked up at all) the loop stops itself and calls ``on_silent_limit``
    so the UI can reflect "voice off". Idempotent — calling while already
    active is a no-op.

    ``on_status`` is called with ``"listening"`` / ``"transcribing"`` /
    ``"idle"`` so the UI can show a live indicator.
    """
    global _continuous_active, _continuous_recorder
    global _continuous_on_transcript, _continuous_on_status, _continuous_on_silent_limit
    global _continuous_no_speech_count

    with _continuous_lock:
        if _continuous_active:
            _debug("start_continuous: already active — no-op")
            return
        _continuous_active = True
        _continuous_on_transcript = on_transcript
        _continuous_on_status = on_status
        _continuous_on_silent_limit = on_silent_limit
        _continuous_no_speech_count = 0

        if _continuous_recorder is None:
            _continuous_recorder = create_audio_recorder()

        _continuous_recorder._silence_threshold = silence_threshold
        _continuous_recorder._silence_duration = silence_duration
        rec = _continuous_recorder

    _debug(f"start_continuous: begin (threshold={silence_threshold}, duration={silence_duration}s)")

    _play_beep(frequency=880, count=1)

    try:
        rec.start(on_silence_stop=_continuous_on_silence)
    except Exception as e:
        logger.error("failed to start continuous recording: %s", e)
        _debug(f"start_continuous: rec.start raised {type(e).__name__}: {e}")
        with _continuous_lock:
            _continuous_active = False
        raise

    if on_status:
        with contextlib.suppress(Exception):
            on_status("listening")


def stop_continuous() -> None:
    """Stop the active continuous loop and release the microphone.

    Idempotent — calling while not active is a no-op. Any in-flight
    transcription completes but its result is discarded (the callback
    checks ``_continuous_active`` before firing).
    """
    global _continuous_active, _continuous_on_transcript
    global _continuous_on_status, _continuous_on_silent_limit
    global _continuous_recorder, _continuous_no_speech_count

    with _continuous_lock:
        if not _continuous_active:
            return
        _continuous_active = False
        rec = _continuous_recorder
        on_status = _continuous_on_status
        _continuous_on_transcript = None
        _continuous_on_status = None
        _continuous_on_silent_limit = None
        _continuous_no_speech_count = 0

    if rec is not None:
        try:
            rec.cancel()
        except Exception as e:
            logger.warning("failed to cancel recorder: %s", e)

    _play_beep(frequency=660, count=2)

    if on_status:
        with contextlib.suppress(Exception):
            on_status("idle")


def is_continuous_active() -> bool:
    """Whether a continuous voice loop is currently running."""
    with _continuous_lock:
        return _continuous_active


def _continuous_on_silence() -> None:
    """AudioRecorder silence callback — runs in a daemon thread.

    Stops the current capture, transcribes, delivers the text via
    ``on_transcript``, and — if the loop is still active — starts the
    next capture. Three consecutive silent cycles end the loop.
    """
    global _continuous_active, _continuous_no_speech_count

    _debug("_continuous_on_silence: fired")

    with _continuous_lock:
        if not _continuous_active:
            _debug("_continuous_on_silence: loop inactive — abort")
            return
        rec = _continuous_recorder
        on_transcript = _continuous_on_transcript
        on_status = _continuous_on_status
        on_silent_limit = _continuous_on_silent_limit

    if rec is None:
        _debug("_continuous_on_silence: no recorder — abort")
        return

    if on_status:
        with contextlib.suppress(Exception):
            on_status("transcribing")

    wav_path = rec.stop()
    peak_rms = getattr(rec, "_peak_rms", -1)
    _debug(f"_continuous_on_silence: rec.stop -> {wav_path!r} (peak_rms={peak_rms})")

    _play_beep(frequency=660, count=2)

    transcript: str | None = None

    if wav_path:
        try:
            result = transcribe_recording(wav_path)
            success = bool(result.get("success"))
            text = (result.get("transcript") or "").strip()
            err = result.get("error")
            _debug(
                f"_continuous_on_silence: transcribe -> success={success} text={text!r} err={err!r}"
            )
            if success and text and not is_whisper_hallucination(text):
                transcript = text
        except Exception as e:
            logger.warning("continuous transcription failed: %s", e)
            _debug(f"_continuous_on_silence: transcribe raised {type(e).__name__}: {e}")
        finally:
            try:
                if os.path.isfile(wav_path):
                    os.unlink(wav_path)
            except Exception:
                pass

    with _continuous_lock:
        if not _continuous_active:
            _debug("_continuous_on_silence: stopped during transcribe — no restart")
            return
        if transcript:
            _continuous_no_speech_count = 0
        else:
            _continuous_no_speech_count += 1
        should_halt = _continuous_no_speech_count >= _CONTINUOUS_NO_SPEECH_LIMIT
        no_speech = _continuous_no_speech_count

    if transcript and on_transcript:
        try:
            on_transcript(transcript)
        except Exception as e:
            logger.warning("on_transcript callback raised: %s", e)

    if should_halt:
        _debug(f"_continuous_on_silence: {no_speech} silent cycles — halting")
        with _continuous_lock:
            _continuous_active = False
            _continuous_no_speech_count = 0
        if on_silent_limit:
            with contextlib.suppress(Exception):
                on_silent_limit()
        with contextlib.suppress(Exception):
            rec.cancel()
        if on_status:
            with contextlib.suppress(Exception):
                on_status("idle")
        return

    if not _tts_playing.is_set():
        _debug("_continuous_on_silence: waiting for TTS to finish")
        _tts_playing.wait(timeout=60)
        import time as _time

        _time.sleep(0.3)

        with _continuous_lock:
            if not _continuous_active:
                _debug("_continuous_on_silence: stopped while waiting for TTS")
                return

    _debug(f"_continuous_on_silence: restarting loop (no_speech={no_speech})")
    _play_beep(frequency=880, count=1)
    try:
        rec.start(on_silence_stop=_continuous_on_silence)
    except Exception as e:
        logger.error("failed to restart continuous recording: %s", e)
        _debug(f"_continuous_on_silence: restart raised {type(e).__name__}: {e}")
        with _continuous_lock:
            _continuous_active = False
        return

    if on_status:
        with contextlib.suppress(Exception):
            on_status("listening")


def speak_text(text: str) -> None:
    """Synthesize ``text`` with the configured TTS provider and play it.

    Mirrors cli.py:_voice_speak_response exactly — same markdown strip
    pipeline, same 4000-char cap, same explicit mp3 output path, same
    MP3-over-OGG playback choice (afplay misbehaves on OGG), same cleanup
    of both extensions. Keeping these in sync means a voice-mode TTS
    session in the TUI sounds identical to one in the classic CLI.

    While playback is in flight the module-level _tts_playing Event is
    cleared so the continuous-recording loop knows to wait before
    re-arming the mic (otherwise the agent's spoken reply feedback-loops
    through the microphone and the agent ends up replying to itself).
    """
    if not text or not text.strip():
        return

    import re
    import tempfile
    import time

    paused_recording = False
    with _continuous_lock:
        if (
            _continuous_active
            and _continuous_recorder is not None
            and getattr(_continuous_recorder, "is_recording", False)
        ):
            try:
                _continuous_recorder.cancel()
                paused_recording = True
            except Exception as e:
                logger.warning("failed to pause recorder for TTS: %s", e)

    _tts_playing.clear()
    _debug(f"speak_text: TTS begin (paused_recording={paused_recording})")

    try:
        from prometheus.tools.tts_tool import text_to_speech_tool

        tts_text = text[:4000] if len(text) > 4000 else text
        tts_text = re.sub(r"```[\s\S]*?```", " ", tts_text)
        tts_text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", tts_text)
        tts_text = re.sub(r"https?://\S+", "", tts_text)
        tts_text = re.sub(r"\*\*(.+?)\*\*", r"\1", tts_text)
        tts_text = re.sub(r"\*(.+?)\*", r"\1", tts_text)
        tts_text = re.sub(r"`(.+?)`", r"\1", tts_text)
        tts_text = re.sub(r"^#+\s*", "", tts_text, flags=re.MULTILINE)
        tts_text = re.sub(r"^\s*[-*]\s+", "", tts_text, flags=re.MULTILINE)
        tts_text = re.sub(r"---+", "", tts_text)
        tts_text = re.sub(r"\n{3,}", "\n\n", tts_text)
        tts_text = tts_text.strip()
        if not tts_text:
            return

        os.makedirs(os.path.join(tempfile.gettempdir(), "prometheus_voice"), exist_ok=True)
        mp3_path = os.path.join(
            tempfile.gettempdir(),
            "prometheus_voice",
            f"tts_{time.strftime('%Y%m%d_%H%M%S')}.mp3",
        )

        _debug(f"speak_text: synthesizing {len(tts_text)} chars -> {mp3_path}")
        text_to_speech_tool(text=tts_text, output_path=mp3_path)

        if os.path.isfile(mp3_path) and os.path.getsize(mp3_path) > 0:
            _debug(f"speak_text: playing {mp3_path} ({os.path.getsize(mp3_path)} bytes)")
            play_audio_file(mp3_path)
            try:
                os.unlink(mp3_path)
                ogg_path = mp3_path.rsplit(".", 1)[0] + ".ogg"
                if os.path.isfile(ogg_path):
                    os.unlink(ogg_path)
            except OSError:
                pass
        else:
            _debug(f"speak_text: TTS tool produced no audio at {mp3_path}")
    except Exception as e:
        logger.warning("Voice TTS playback failed: %s", e)
        _debug(f"speak_text raised {type(e).__name__}: {e}")
    finally:
        _tts_playing.set()
        _debug("speak_text: TTS done")

        if paused_recording:
            time.sleep(0.3)
            with _continuous_lock:
                if _continuous_active and _continuous_recorder is not None:
                    try:
                        _continuous_recorder.start(on_silence_stop=_continuous_on_silence)
                        _debug("speak_text: recording resumed after TTS")
                    except Exception as e:
                        logger.warning("failed to resume recorder after TTS: %s", e)
