"""
ClipMind API v6
SSE streaming backend. All events padded to >1KB to force Vercel buffer flush.
"""
import asyncio
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from ai_analyzer import AIAnalyzer
from pipeline import TMP_DIR, extract_frames, extract_transcript, render_video

# ── Job registry ──────────────────────────────────────────────────────────────

JOBS: dict[str, dict] = {}
JOB_TTL = 3600  # 1 hour

RESOLUTION_MAP = {
    "720p":  (1280,  720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "4k":    (3840, 2160),
    "8k":    (7680, 4320),
    "9:16":  (1080, 1920),
    "1:1":   (1080, 1080),
}


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    """
    Serialise one SSE event, padded to >1KB so Vercel's edge proxy
    flushes immediately instead of buffering the whole response.
    """
    payload = json.dumps(data)
    # Pad with spaces inside the JSON comment field to hit 1200 chars minimum
    pad_len = max(0, 1200 - len(payload) - 8)
    line    = f"data: {payload}{' ' * pad_len}\n\n"
    return line


# ── Cleanup loop ──────────────────────────────────────────────────────────────

async def _cleanup_loop():
    while True:
        await asyncio.sleep(600)
        now     = time.time()
        expired = [jid for jid, j in list(JOBS.items()) if now - j.get("created", now) > JOB_TTL]
        for jid in expired:
            JOBS.pop(jid, None)
            for f in TMP_DIR.glob(f"*{jid}*"):
                try:
                    f.unlink()
                except Exception:
                    pass
        if expired:
            print(f"🗑  Cleaned {len(expired)} expired jobs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(_cleanup_loop())
    yield


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="ClipMind API", version="6.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

analyzer = AIAnalyzer()


# ── Health ────────────────────────────────────────────────────────────────────

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"service": "ClipMind API", "version": "6.0", "status": "ok"}


@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    from pipeline import FFMPEG, FONT
    return {
        "status":  "ok",
        "version": "6.0",
        "ffmpeg":  FFMPEG,
        "font":    FONT or "not found",
        "groq":    bool(os.environ.get("GROQ_API_KEY")),
        "jobs":    len(JOBS),
    }


# ── Job status ────────────────────────────────────────────────────────────────

@app.get("/jobs/{job_id}/status")
async def job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found or expired")
    out = job.get("output")
    return {
        "job_id":       job_id,
        "status":       job.get("status"),
        "has_output":   bool(out and Path(out).exists()),
        "error":        job.get("error"),
        "download_url": f"/download/{job_id}_edited.mp4" if out else None,
    }


# ── Main pipeline (SSE) ───────────────────────────────────────────────────────

async def _pipeline(
    video_path: Path,
    style:         str,
    options:       list,
    job_id:        str,
    resolution:    str,
    fps:           int,
    quality:       str,
    custom_prompt: str,
):
    JOBS[job_id] = {
        "status":   "starting",
        "created":  time.time(),
        "analysis": None,
        "output":   None,
        "error":    None,
        "style":    style,
        "options":  options,
    }

    try:
        # ── Connected (flush Railway/Vercel buffer immediately) ───────────────
        yield _sse({"step": 0, "progress": 2, "status": "📡 Connected — starting pipeline…", "job_id": job_id})

        # ── Step 1: Extract frames + transcript ───────────────────────────────
        JOBS[job_id]["status"] = "extracting"
        yield _sse({"step": 1, "progress": 8, "status": "📹 Extracting frames & transcribing audio…", "job_id": job_id})

        (frames, duration), transcript = await asyncio.gather(
            extract_frames(video_path, fps=0.5),
            extract_transcript(video_path),
        )

        yield _sse({
            "step": 2, "progress": 30,
            "status": f"✅ {len(frames)} frames | {'speech detected' if transcript else 'no speech'}",
            "job_id": job_id,
        })

        # ── Step 2: AI analysis ───────────────────────────────────────────────
        JOBS[job_id]["status"] = "analysing"
        ai_label = "🧠 AI analysing with your instructions…" if custom_prompt else "🧠 AI analysing clip…"
        yield _sse({"step": 3, "progress": 40, "status": ai_label, "job_id": job_id})

        analysis = await analyzer.analyze(
            transcript=transcript or "No speech — gameplay footage.",
            duration=duration,
            style=style,
            options=options,
            num_frames=len(frames),
            custom_prompt=custom_prompt,
        )
        JOBS[job_id]["analysis"] = analysis

        n_cuts        = len(analysis.get("cuts", []))
        n_speed_ramps = len([c for c in analysis.get("cuts", []) if (c.get("type") or "") == "speed_ramp"])
        yield _sse({
            "step": 4, "progress": 55,
            "status": f"📝 Edit plan ready — {n_cuts} cuts, {n_speed_ramps} speed ramp(s)",
            "job_id": job_id,
        })

        # ── Step 3: Render ────────────────────────────────────────────────────
        JOBS[job_id]["status"] = "rendering"
        res_tuple   = RESOLUTION_MAP.get(resolution.lower()) if resolution else None
        fps_val     = int(fps) if fps else None
        output_path = TMP_DIR / f"{job_id}_edited.mp4"

        yield _sse({"step": 5, "progress": 62, "status": f"✂️  Rendering {resolution} {quality}…", "job_id": job_id})

        render_task = asyncio.ensure_future(render_video(
            video_path=video_path,
            analysis=analysis,
            output_path=output_path,
            style=style,
            options=options,
            resolution=res_tuple,
            fps=fps_val,
            quality=quality,
            add_music=True,
        ))

        elapsed = 0
        while not render_task.done():
            await asyncio.sleep(6)
            elapsed += 6
            if not render_task.done():
                prog = min(62 + elapsed * 0.25, 90)
                yield _sse({"step": 5, "progress": int(prog), "status": f"⚙️  Rendering… {elapsed}s elapsed", "job_id": job_id})

        if render_task.exception():
            raise render_task.exception()

        # ── Done ─────────────────────────────────────────────────────────────
        JOBS[job_id]["status"] = "done"
        if output_path.exists():
            JOBS[job_id]["output"] = str(output_path)

        file_mb = round(output_path.stat().st_size / 1024 / 1024, 1) if output_path.exists() else 0

        yield _sse({
            "step": 7, "progress": 100,
            "status": "✅ Your clip is ready!",
            "job_id": job_id,
            "result":        analysis,
            "download_url":  f"/download/{job_id}_edited.mp4",
            "cuts_applied":  n_cuts,
            "file_size_mb":  file_mb,
            "duration_s":    duration,
            "resolution":    resolution or "source",
            "fps":           fps_val or "source",
            "quality":       quality,
            "music_added":   "music" in options,
        })

    except Exception as e:
        import traceback
        print(f"Pipeline error [{job_id}]:\n{traceback.format_exc()}")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"]  = str(e)
        yield _sse({"step": -1, "progress": 0, "status": f"❌ {str(e)[:200]}", "job_id": job_id})


@app.post("/analyze")
async def analyze_video(
    video:         UploadFile = File(...),
    style:         str        = Form("freefire"),
    options:       str        = Form("[]"),
    resolution:    str        = Form("1080p"),
    fps:           int        = Form(60),
    quality:       str        = Form("high"),
    custom_prompt: str        = Form(""),
):
    job_id     = str(uuid.uuid4())[:8]
    safe_name  = (video.filename or "upload.mp4").replace("/", "_").replace("..", "_")
    video_path = TMP_DIR / f"{job_id}_{safe_name}"

    async with aiofiles.open(video_path, "wb") as f:
        while chunk := await video.read(256 * 1024):
            await f.write(chunk)

    try:
        opts = json.loads(options) if options else []
        if not isinstance(opts, list):
            opts = []
    except (json.JSONDecodeError, ValueError):
        opts = []

    return StreamingResponse(
        _pipeline(video_path, style, opts, job_id, resolution, fps, quality,
                  custom_prompt.strip()[:400]),
        media_type="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":        "keep-alive",
        },
    )


# ── Re-export with new settings ───────────────────────────────────────────────

@app.post("/export/{job_id}")
async def export_video(
    job_id:     str,
    resolution: str = Form("1080p"),
    fps:        int = Form(60),
    quality:    str = Form("high"),
):
    job = JOBS.get(job_id)
    if not job or not job.get("analysis"):
        raise HTTPException(404, "Job not found or analysis missing — please re-upload")

    originals = [
        p for p in (
            list(TMP_DIR.glob(f"{job_id}_*.mp4")) +
            list(TMP_DIR.glob(f"{job_id}_*.mov")) +
            list(TMP_DIR.glob(f"{job_id}_*.webm"))
        )
        if "_edited" not in p.name and "_raw" not in p.name
           and "_ramp" not in p.name and "_render" not in p.name
    ]
    if not originals:
        raise HTTPException(404, "Original video expired — please re-upload")

    video_path = originals[0]
    output     = TMP_DIR / f"{job_id}_edited.mp4"
    res_tuple  = RESOLUTION_MAP.get(resolution.lower())

    async def _export():
        yield _sse({"step": 5, "progress": 10, "status": f"🔄 Re-encoding {resolution} {fps}fps…"})
        try:
            await render_video(
                video_path=video_path,
                analysis=job["analysis"],
                output_path=output,
                style=job.get("style", "cinematic"),
                options=job.get("options", []),
                resolution=res_tuple,
                fps=fps,
                quality=quality,
                add_music=False,
            )
            mb = round(output.stat().st_size / 1024 / 1024, 1) if output.exists() else 0
            yield _sse({
                "step": 7, "progress": 100,
                "status": "✅ Export ready!",
                "download_url": f"/download/{job_id}_edited.mp4",
                "file_size_mb": mb,
            })
        except Exception as e:
            yield _sse({"step": -1, "progress": 0, "status": f"❌ Export failed: {str(e)[:150]}"})

    return StreamingResponse(
        _export(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Download ──────────────────────────────────────────────────────────────────

@app.get("/download/{filename}")
async def download(filename: str):
    safe = Path(filename).name
    path = TMP_DIR / safe
    try:
        path.resolve().relative_to(TMP_DIR.resolve())
    except ValueError:
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, "File not found — server may have restarted, please re-process")
    return FileResponse(
        str(path), media_type="video/mp4", filename=safe,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


# ── Manual cleanup ────────────────────────────────────────────────────────────

@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    JOBS.pop(job_id, None)
    removed = 0
    for f in TMP_DIR.glob(f"*{job_id}*"):
        try:
            f.unlink()
            removed += 1
        except Exception:
            pass
    return {"status": "cleaned", "job_id": job_id, "files_removed": removed}
