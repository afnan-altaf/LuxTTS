import io
import logging
import os
import tempfile
import wave
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from zipvoice.luxvoice import LuxTTS

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"
SAMPLE_RATE = 48_000
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    app_instance.state.lux_tts = _load_model()
    yield


app = FastAPI(title="JamberTech Official LuxTTS Studio", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _load_model() -> LuxTTS:
    model_id = os.getenv("LUXTTS_MODEL", "YatharthS/LuxTTS")
    device = os.getenv("LUXTTS_DEVICE", "cuda")
    threads = int(os.getenv("LUXTTS_THREADS", "4"))
    try:
        return LuxTTS(model_id, device=device, threads=threads)
    except Exception as exc:
        logger.exception("Failed to load LuxTTS model.")
        raise RuntimeError("Failed to load LuxTTS model. Check configuration and logs.") from exc


def _to_wav_bytes(samples: np.ndarray, sample_rate: int) -> bytes:
    samples = np.asarray(samples)
    if samples.size == 0:
        raise ValueError("Generated audio is empty.")

    if samples.ndim == 1:
        channels = 1
        interleaved = samples
    elif samples.ndim == 2:
        if samples.shape[0] > samples.shape[1]:
            samples = samples.T
        channels = samples.shape[0]
        interleaved = samples.T.reshape(-1)
    else:
        raise ValueError("Generated audio has an unsupported shape.")

    interleaved = np.clip(interleaved, -1.0, 1.0)
    pcm = (interleaved * 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return buffer.getvalue()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/generate")
async def generate_audio(
    text: str = Form(...),
    prompt_audio: UploadFile = File(...),
    rms: float = Form(0.01),
    prompt_duration: float = Form(5.0),
    num_steps: int = Form(4),
    guidance_scale: float = Form(3.0),
    t_shift: float = Form(0.9),
    speed: float = Form(1.0),
    return_smooth: bool = Form(False),
) -> Response:
    text = text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required.")
    if num_steps < 1:
        raise HTTPException(status_code=400, detail="num_steps must be at least 1.")
    if prompt_duration <= 0:
        raise HTTPException(status_code=400, detail="prompt_duration must be positive.")
    if speed <= 0:
        raise HTTPException(status_code=400, detail="speed must be positive.")

    audio_bytes = await prompt_audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Prompt audio is required.")

    lux_tts = getattr(app.state, "lux_tts", None)
    if lux_tts is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "LuxTTS model is not loaded. Ensure LUXTTS_MODEL and LUXTTS_DEVICE are "
                "configured correctly, then restart the server."
            ),
        )

    suffix = Path(prompt_audio.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        suffix = ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name

    try:
        encode_dict = lux_tts.encode_prompt(
            temp_path,
            duration=prompt_duration,
            rms=rms,
        )
        final_wav = lux_tts.generate_speech(
            text,
            encode_dict,
            num_steps=num_steps,
            guidance_scale=guidance_scale,
            t_shift=t_shift,
            speed=speed,
            return_smooth=return_smooth,
        )
        wav_bytes = _to_wav_bytes(final_wav.squeeze().detach().cpu().numpy(), SAMPLE_RATE)
    except Exception as exc:
        logger.exception("Speech generation failed.")
        raise HTTPException(
            status_code=500,
            detail="Speech generation failed. Check server logs for details.",
        ) from exc
    finally:
        os.unlink(temp_path)

    headers = {"Content-Disposition": "inline; filename=jambertech-luxtts.wav"}
    return Response(content=wav_bytes, media_type="audio/wav", headers=headers)


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("LUXTTS_HOST", "127.0.0.1")
    port = int(os.getenv("LUXTTS_PORT", "8000"))
    reload = os.getenv("LUXTTS_RELOAD", "false").lower() == "true"
    uvicorn.run("zipvoice.web.app:app", host=host, port=port, reload=reload)
