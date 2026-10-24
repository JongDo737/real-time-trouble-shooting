"""MediaRecorder 업로드 → mono 16 kHz WAV → CPU Whisper. 음성·텍스트를 로그에 남기지 않는다."""
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.concurrency import run_in_threadpool

app = FastAPI(title="Rilshu Speech to Text", docs_url=None, redoc_url=None)
secret = os.environ.get("JWT_SECRET", "")
if len(secret.encode()) < 32:
    raise RuntimeError("JWT_SECRET must match the backend HS256 key (at least 32 bytes)")
bearer = HTTPBearer(auto_error=False)
model = None
model_lock = threading.Lock()
inference_lock = threading.Lock()
MAX_BYTES = 5 * 1024 * 1024


def authenticated(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Authentication required")
    try:
        claims = jwt.decode(credentials.credentials, secret, algorithms=["HS256"],
                            options={"require": ["sub", "role", "exp"]})
        if claims["role"] not in ("USER", "ADMIN") or int(claims["sub"]) <= 0:
            raise ValueError()
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise HTTPException(401, "Invalid or expired token") from None


def get_model():
    global model
    with model_lock:
        if model is None:
            from faster_whisper import WhisperModel
            model = WhisperModel(os.getenv("WHISPER_MODEL", "tiny"), device="cpu", compute_type="int8", download_root="/models")
    return model


def transcribe(data: bytes, language: str) -> str:
    # 한번에 한 건 처리해 CPU와 메모리 사용량을 제한한다.
    if not inference_lock.acquire(timeout=60):
        raise HTTPException(503, "Speech service is busy; try again")
    try:
        with tempfile.TemporaryDirectory(prefix="rilshu-stt-") as folder:
            source, wav = Path(folder) / "recording", Path(folder) / "recording.wav"
            source.write_bytes(data)
            try:
                subprocess.run([
                    "ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-protocol_whitelist", "file,pipe", "-i", str(source),
                    "-t", "35", "-ac", "1", "-ar", "16000", "-vn", str(wav),
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                raise HTTPException(422, "Unsupported or invalid audio") from None
            try:
                segments, _ = get_model().transcribe(str(wav), language=language, beam_size=5, vad_filter=True)
                text = "".join(segment.text for segment in segments).strip()
            except Exception:
                raise HTTPException(503, "Speech recognition unavailable") from None
            if len(text) > 2000:
                raise HTTPException(422, "Recognized text exceeds 2000 characters")
            return text
    finally:
        inference_lock.release()


@app.get("/health")
def health():
    return {"status": "ok", "modelLoaded": model is not None}


@app.post("/stt/")
async def stt(audio: UploadFile = File(...), language: str = Form("en"), user=Depends(authenticated)):
    expected_language = "ko" if user["role"] == "ADMIN" else "en"
    if language != expected_language:
        raise HTTPException(422, "Language must match the authenticated role")
    data = await audio.read(MAX_BYTES + 1)
    await audio.close()
    if not data:
        raise HTTPException(422, "Audio is empty")
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Audio exceeds 5 MiB")
    return {"text": await run_in_threadpool(transcribe, data, language)}
