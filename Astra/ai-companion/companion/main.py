"""FastAPI entry point for the offline ASTRA Companion service (:8200)."""
from __future__ import annotations

import importlib.util
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .dialogue import CONTENT, DialogueManager, is_arabic
from .guards import InputRejected, validate_input

logging.basicConfig(level=os.getenv("ASTRA_LOG_LEVEL", "INFO"))
logger = logging.getLogger("astra.companion")
app = FastAPI(title="ASTRA Companion", version="1.0.0")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://127.0.0.1:5174", "http://127.0.0.1:4173", "http://127.0.0.1:4174",
                   "http://localhost:5173", "http://localhost:5174", "http://localhost:4173", "http://localhost:4174"],
    allow_credentials=False, allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"])
dialogue = DialogueManager()
transcripts: dict[str, list[dict[str, Any]]] = {}


class StatusSummary(BaseModel):
    schema_name: str | None = Field(default=None, alias="schema")
    astronaut_id: str | None = None
    indicator: str
    status: Literal["normal", "attention", "urgent"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list, max_length=20)
    baseline_ref: str | None = None
    recommended_action: str | None = None
    decision_level: int | None = Field(default=None, ge=1, le=3)
    computed_ts: str | None = None

    model_config = {"populate_by_name": True, "extra": "ignore"}


class MessageRequest(BaseModel):
    astronaut_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2_100)
    status_summary: list[StatusSummary] = Field(default_factory=list, max_length=50)
    mode: Literal["connected", "autonomous"] = "autonomous"
    intent: Literal["daily_checkin", "breathing", "weekly_wellbeing", "radiation_followup", "shelter_prompt"] | None = None
    dizziness_reported: bool = False
    tone: Literal["warm", "neutral", "brief"] = "warm"


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2_000)
    voice: str = Field(default="default", min_length=1, max_length=64)
    speaking_rate: float = Field(default=1.0, ge=0.7, le=1.5)


@app.middleware("http")
async def log_latency(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["X-Response-Time-Ms"] = str(round(elapsed * 1000, 2))
    logger.info("request method=%s path=%s status=%s latency_ms=%.2f",
                request.method, request.url.path, response.status_code, elapsed * 1000)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "offline", "llm": "disabled"}


def _notify_medical(astronaut_id: str, notice: dict[str, Any]) -> bool:
    hub = os.getenv("ASTRA_HUB_URL", "http://127.0.0.1:8000").rstrip("/")
    payload = {"astronaut_id": astronaut_id, **notice}
    request = urllib.request.Request(
        f"{hub}/internal/companion-notify", data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            return response.status < 300
    except (urllib.error.URLError, OSError):
        logger.warning("companion note could not reach the hub")
        return False


@app.post("/companion/message")
def companion_message(body: MessageRequest) -> dict[str, Any]:
    try:
        status_payload = [s.model_dump(by_alias=True, exclude_none=True) for s in body.status_summary]
        result = dialogue.message(body.astronaut_id, body.text, status_payload,
                                  mode=body.mode, intent=body.intent,
                                  dizziness_reported=body.dizziness_reported)
        notice = result.pop("notify", None)
        if isinstance(notice, dict) and _notify_medical(body.astronaut_id, notice):
            shared = " شاركت ملاحظة قصيرة مع الفريق الطبي للطيران." if is_arabic(body.text) \
                else " I shared a short note with the flight medical team."
            result["reply_text"] = str(result.get("reply_text", "")).rstrip() + shared
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        actions = []
        for index, item in enumerate(result.get("actions", [])):
            action_type = str(item.get("type", ""))
            kind = ("breathing" if action_type in {"breathing", "offer_breathing"} else
                    "checkin" if action_type in {"submit_checkin", "post_exposure_checkin", "weekly_wellbeing_questions"} else
                    "shelter" if action_type == "approved_protocol_required" else "none")
            actions.append({"id": f"{action_type or 'action'}-{index}", "kind": kind,
                            "label": {"breathing": "Start breathing exercise", "checkin": "Open check-in",
                                      "shelter": "Open radiation guidance"}.get(kind, "Continue"),
                            "payload": item.get("technique")})
        history = transcripts.setdefault(body.astronaut_id, [])
        history.extend([
            {"id": str(uuid.uuid4()), "role": "astronaut", "text": body.text, "createdAt": now},
            {"id": str(uuid.uuid4()), "role": "companion", "text": result.get("reply_text", ""),
             "createdAt": now, "actions": actions},
        ])
        return result
    except InputRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/companion/transcript/{astronaut_id}")
def companion_transcript(astronaut_id: str) -> list[dict[str, Any]]:
    return list(transcripts.get(astronaut_id, []))


@app.get("/companion/breathing")
def breathing_list(dizziness_reported: bool = False) -> dict[str, Any]:
    techniques = CONTENT["breathing"]
    if dizziness_reported:
        techniques = [x for x in techniques if x["id"] == "gentle-grounding"]
    return {"techniques": techniques}


@app.get("/companion/breathing/{technique_id}")
def breathing_detail(technique_id: str) -> dict[str, Any]:
    for technique in CONTENT["breathing"]:
        if technique["id"] == technique_id:
            return technique
    raise HTTPException(status_code=404, detail="Unknown breathing technique")


@app.get("/companion/checkin/next")
def checkin_next() -> dict[str, Any]:
    return dialogue.checkin_next()


_stt_model: Any = None
_stt_model_path: str | None = None


def _stt_ready() -> tuple[bool, str]:
    model_path = os.getenv("VOSK_MODEL_PATH", "")
    if not model_path or not Path(model_path).is_dir():
        return False, "No local Vosk model is configured"
    if importlib.util.find_spec("vosk") is None:
        return False, "The vosk package is not installed"
    return True, "Local speech recognition is ready"


def _load_stt_model(model_path: str) -> Any:
    global _stt_model, _stt_model_path
    if _stt_model is None or _stt_model_path != model_path:
        import vosk
        _stt_model = vosk.Model(model_path)
        _stt_model_path = model_path
    return _stt_model


@app.get("/companion/stt/status")
def companion_stt_status() -> dict[str, Any]:
    ready, detail = _stt_ready()
    return {"available": ready, "detail": detail}


@app.post("/companion/stt")
async def companion_stt(request: Request) -> dict[str, str]:
    """Transcribe WAV from request bytes using Vosk and a local model only."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type not in {"audio/wav", "audio/x-wav", "application/octet-stream"}:
        raise HTTPException(status_code=415, detail="Send audio/wav bytes")
    ready, detail = _stt_ready()
    if not ready:
        raise HTTPException(status_code=503, detail=detail)
    audio = await request.body()
    if not audio or len(audio) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio is empty or exceeds the local size limit")
    try:
        import vosk
        with wave.open(io.BytesIO(audio), "rb") as wf:
            if wf.getnchannels() not in (1, 2) or wf.getsampwidth() != 2:
                raise ValueError("WAV must be 16-bit mono or stereo PCM")
            model = _load_stt_model(os.getenv("VOSK_MODEL_PATH", ""))
            recognizer = vosk.KaldiRecognizer(model, wf.getframerate())
            while True:
                chunk = wf.readframes(8_000)
                if not chunk:
                    break
                recognizer.AcceptWaveform(chunk)
            result = json.loads(recognizer.FinalResult())
            return {"text": validate_input(result.get("text", ""))}
    except InputRejected:
        return {"text": ""}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("local STT failed: %s", type(exc).__name__)
        raise HTTPException(status_code=422, detail="Local speech recognition could not process this WAV") from exc


@app.get("/companion/tts/status")
def companion_tts_status() -> dict[str, Any]:
    voices_dir = Path(os.getenv("PIPER_VOICES_DIR", ""))
    voice = os.getenv("PIPER_DEFAULT_VOICE", "")
    binary = shutil.which(os.getenv("PIPER_BIN", "piper"))
    ready = bool(voice and binary and voices_dir.is_dir() and (voices_dir / f"{voice}.onnx").is_file())
    return {"available": ready,
            "detail": "Local speech synthesis is ready" if ready else
                      "No local Piper voice is installed; spoken replies fall back to the browser or stay on screen."}


@app.post("/companion/tts")
def companion_tts(body: TTSRequest) -> Response:
    """Generate speech via local Piper; temporary output is removed immediately."""
    try:
        text = validate_input(body.text)
    except InputRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    voices_dir = Path(os.getenv("PIPER_VOICES_DIR", ""))
    voice = body.voice
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", voice):
        raise HTTPException(status_code=400, detail="Invalid local voice identifier")
    voice_name = os.getenv("PIPER_DEFAULT_VOICE", "") if voice == "default" else voice
    if not voice_name:
        raise HTTPException(status_code=503, detail="Local Piper voice is not configured")
    voice_path = (voices_dir / f"{voice_name}.onnx").resolve()
    if not voices_dir.is_dir() or not voice_path.is_file() or voices_dir.resolve() not in voice_path.parents:
        raise HTTPException(status_code=503, detail="Requested local Piper voice is unavailable")
    binary = os.getenv("PIPER_BIN", "piper")
    try:
        with tempfile.TemporaryDirectory(prefix="astra-tts-") as tmp:
            output_path = Path(tmp) / "speech.wav"
            subprocess.run([binary, "--model", str(voice_path), "--length_scale", str(1.0 / body.speaking_rate), "--output_file", str(output_path)],
                           input=text.encode("utf-8"), stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, check=True, timeout=30)
            audio = output_path.read_bytes()
        return Response(content=audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Local Piper executable is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Local speech synthesis exceeded its time limit") from exc
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("local TTS failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Local speech synthesis failed") from exc
