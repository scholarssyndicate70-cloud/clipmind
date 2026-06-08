"""
ClipMind FFmpeg Pipeline
Handles all video processing. Each step is isolated — if one fails, others still run.
"""
import asyncio
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import imageio_ffmpeg

from effects.filters import (
    COLOR_GRADES, GRAIN, SHARPEN, LETTERBOX, QUALITY,
    MUSIC_FILES, YOUTUBE_TRACKS,
)

TMP_DIR = Path("/tmp/clipmind")
TMP_DIR.mkdir(exist_ok=True)


# ── FFmpeg binary ─────────────────────────────────────────────────────────────

def get_ffmpeg() -> str:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=3)
        if r.returncode == 0:
            return "ffmpeg"
    except Exception:
        pass
    return imageio_ffmpeg.get_ffmpeg_exe()


FFMPEG = get_ffmpeg()


# ── Font discovery ────────────────────────────────────────────────────────────

def find_font() -> Optional[str]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    try:
        r = subprocess.run(
            ["fc-match", "--format=%{file}", "sans:bold"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


FONT = find_font()


# ── Async subprocess helper ───────────────────────────────────────────────────

async def run_cmd(cmd: List[str]) -> Tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return (
        out.decode("utf-8", errors="ignore"),
        err.decode("utf-8", errors="ignore"),
        proc.returncode,
    )


# ── Video probe ───────────────────────────────────────────────────────────────

_probe_cache: dict = {}


async def probe_video(path: Path) -> Tuple[float, int, int, bool]:
    """Returns (duration_s, width, height, has_audio)"""
    key = str(path)
    if key in _probe_cache:
        return _probe_cache[key]

    _, stderr, _ = await run_cmd([FFMPEG, "-i", str(path), "-f", "null", "-"])

    dm = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", stderr)
    sm = re.search(r"(\d{3,5})x(\d{3,5})", stderr)

    duration = (
        int(dm.group(1)) * 3600 + int(dm.group(2)) * 60 + float(dm.group(3))
    ) if dm else 30.0

    w, h = (int(sm.group(1)), int(sm.group(2))) if sm else (1920, 1080)
    has_audio = "Audio:" in stderr

    result = (duration, w, h, has_audio)
    _probe_cache[key] = result
    return result


# ── Frame extraction ──────────────────────────────────────────────────────────

async def extract_frames(video_path: Path, fps: float = 0.5) -> Tuple[List[Path], float]:
    duration, _, _, _ = await probe_video(video_path)
    frames_dir = TMP_DIR / f"{video_path.stem}_frames"
    frames_dir.mkdir(exist_ok=True)

    await run_cmd([
        FFMPEG, "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "5",
        str(frames_dir / "frame_%04d.jpg"),
        "-y", "-loglevel", "error",
    ])

    frames = sorted(frames_dir.glob("*.jpg"))
    try:
        shutil.rmtree(frames_dir, ignore_errors=True)
    except Exception:
        pass

    return frames, duration


# ── Transcription ─────────────────────────────────────────────────────────────

async def extract_transcript(video_path: Path) -> str:
    audio_path = TMP_DIR / f"{video_path.stem}_audio.wav"
    try:
        await run_cmd([
            FFMPEG, "-i", str(video_path),
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            str(audio_path), "-y", "-loglevel", "error",
        ])

        if not audio_path.exists() or audio_path.stat().st_size < 1000:
            return ""

        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            return ""

        from groq import AsyncGroq
        client = AsyncGroq(api_key=api_key)
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        result = await asyncio.wait_for(
            client.audio.transcriptions.create(
                file=(audio_path.name, audio_bytes),
                model="whisper-large-v3-turbo",
                response_format="text",
            ),
            timeout=30.0,
        )
        return result or ""

    except asyncio.TimeoutError:
        print("⚠️  Transcription timed out")
    except Exception as e:
        print(f"⚠️  Transcription error: {e}")
    finally:
        try:
            if audio_path.exists():
                audio_path.unlink()
        except Exception:
            pass
    return ""


# ── Music ─────────────────────────────────────────────────────────────────────

async def get_music(style: str) -> Optional[Path]:
    """Priority: yt-dlp cache → yt-dlp download → bundled files → None"""
    music_dir = Path(__file__).parent / "music"

    # 1. yt-dlp (try download if not cached)
    if style in YOUTUBE_TRACKS:
        yt_url, cache_name = YOUTUBE_TRACKS[style]
        yt_cache = TMP_DIR / cache_name

        if yt_cache.exists() and yt_cache.stat().st_size > 50_000:
            print(f"🎵 yt-dlp cache hit: {cache_name}")
            return yt_cache

        ytdlp = shutil.which("yt-dlp")
        if ytdlp:
            print(f"🎵 yt-dlp downloading: {yt_url}")
            try:
                out_template = str(yt_cache.with_suffix(""))
                _, err, code = await asyncio.wait_for(
                    run_cmd([
                        "yt-dlp",
                        "--extract-audio",
                        "--audio-format", "mp3",
                        "--audio-quality", "128K",
                        "--no-playlist",
                        "--no-warnings",
                        "-o", out_template,
                        yt_url,
                    ]),
                    timeout=90.0,
                )
                alt = TMP_DIR / (cache_name.replace(".mp3", "") + ".mp3")
                if not yt_cache.exists() and alt.exists():
                    alt.rename(yt_cache)

                if yt_cache.exists() and yt_cache.stat().st_size > 50_000:
                    print(f"🎵 yt-dlp success: {yt_cache.stat().st_size // 1024}KB")
                    return yt_cache
                else:
                    print(f"⚠️  yt-dlp bad output (code={code}): {err[-200:]}")
            except asyncio.TimeoutError:
                print("⚠️  yt-dlp timed out")
            except Exception as e:
                print(f"⚠️  yt-dlp error: {e}")

    # 2. Bundled files
    fname   = MUSIC_FILES.get(style, MUSIC_FILES["default"])
    bundled = music_dir / fname
    if bundled.exists() and bundled.stat().st_size > 10_000:
        print(f"🎵 Bundled music: {fname} ({bundled.stat().st_size // 1024}KB)")
        return bundled

    print(f"⚠️  No music available for style={style}")
    return None


async def mix_music(
    video_path: Path,
    music_path: Path,
    output_path: Path,
    duration: float,
    has_audio: bool,
) -> Optional[Path]:
    """Mix music into video. Handles both silent and audio-bearing videos."""
    print(f"🎵 Mixing: {music_path.name}")

    if has_audio:
        af = (
            "[0:a]volume=1.0[game];"
            f"[1:a]volume=0.40,aloop=loop=-1:size=2000000000,"
            f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[music];"
            "[game][music]amix=inputs=2:duration=first:dropout_transition=3[aout]"
        )
    else:
        af = (
            f"[1:a]volume=0.55,aloop=loop=-1:size=2000000000,"
            f"atrim=0:{duration:.3f},asetpts=PTS-STARTPTS[aout]"
        )

    _, stderr, code = await run_cmd([
        FFMPEG,
        "-i", str(video_path),
        "-stream_loop", "-1",
        "-i", str(music_path),
        "-filter_complex", af,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-y", str(output_path),
    ])

    if output_path.exists() and output_path.stat().st_size > 5000:
        print(f"✅ Music mixed: {output_path.stat().st_size // 1024}KB")
        return output_path

    print(f"⚠️  Music mix failed (code={code}): {stderr[-300:]}")
    return None


# ── Speed ramp renderer ───────────────────────────────────────────────────────

async def apply_speed_ramps(
    video_path: Path,
    speed_cuts: list,
    output_path: Path,
    duration: float,
    has_audio: bool,
) -> Optional[Path]:
    """
    Apply speed ramp cuts using FFmpeg filter_complex.
    Each speed_ramp cut defines a window where video slows (speed_in < 1.0)
    then snaps fast (speed_out > 1.0) just after the window.

    Strategy:
      - Split the clip into segments at each ramp boundary
      - Apply setpts to each segment independently
      - Concat all segments back together

    Returns the output path on success, None on failure.
    """
    if not speed_cuts:
        return None

    # Sort by timestamp
    ramps = sorted(speed_cuts, key=lambda c: float(c.get("timestamp", 0)))

    # Build segment list: (start, end, pts_factor)
    # pts_factor > 1.0 = slow down, < 1.0 = speed up
    segments: List[Tuple[float, float, float, float]] = []
    # (seg_start, seg_end, video_pts_factor, audio_tempo)

    cursor = 0.0
    for ramp in ramps:
        try:
            ts      = max(0.0, float(ramp.get("timestamp", 0)))
            rdur    = max(0.1, float(ramp.get("duration", 1.0)))
            s_in    = max(0.1, min(1.0, float(ramp.get("speed_in",  0.5))))
            s_out   = max(1.0, min(3.0, float(ramp.get("speed_out", 1.25))))
        except (TypeError, ValueError):
            continue

        ramp_end   = min(ts + rdur, duration)
        snap_end   = min(ramp_end + 1.0, duration)

        if ts <= cursor:
            continue

        # Normal segment before ramp
        if cursor < ts:
            segments.append((cursor, ts, 1.0, 1.0))

        # Slow-mo segment (speed_in = 0.5 → pts_factor = 1/0.5 = 2.0 → plays 2× slower)
        segments.append((ts, ramp_end, 1.0 / s_in, 1.0 / s_in))

        # Snap-fast segment (speed_out = 1.25 → pts_factor = 1/1.25 = 0.8)
        if ramp_end < snap_end:
            segments.append((ramp_end, snap_end, 1.0 / s_out, 1.0 / s_out))

        cursor = snap_end

    # Trailing normal segment
    if cursor < duration - 0.1:
        segments.append((cursor, duration, 1.0, 1.0))

    if not segments:
        return None

    # Build filter_complex
    # Each segment: trim → setpts for video, atrim → asetpts → atempo for audio
    n          = len(segments)
    fc_parts   = []
    v_labels   = []
    a_labels   = []

    for i, (seg_start, seg_end, v_pts, a_tempo) in enumerate(segments):
        seg_dur = seg_end - seg_start

        # Video branch
        v_trim  = f"[0:v]trim=start={seg_start:.4f}:end={seg_end:.4f},setpts={v_pts:.6f}*(PTS-STARTPTS)[v{i}]"
        fc_parts.append(v_trim)
        v_labels.append(f"[v{i}]")

        # Audio branch (only if video has audio track)
        if has_audio:
            # atempo is clamped to [0.5, 2.0] per filter instance
            # For values outside this range we chain multiple atempo filters
            a_tempo_chain = _build_atempo_chain(a_tempo)
            a_trim = (
                f"[0:a]atrim=start={seg_start:.4f}:end={seg_end:.4f},"
                f"asetpts=PTS-STARTPTS,{a_tempo_chain}[a{i}]"
            )
            fc_parts.append(a_trim)
            a_labels.append(f"[a{i}]")

    # Concat video
    v_concat_in = "".join(v_labels)
    fc_parts.append(f"{v_concat_in}concat=n={n}:v=1:a=0[vout]")

    if has_audio and a_labels:
        a_concat_in = "".join(a_labels)
        fc_parts.append(f"{a_concat_in}concat=n={n}:v=0:a=1[aout]")

    filter_complex = ";".join(fc_parts)

    cmd = [
        FFMPEG, "-i", str(video_path),
        "-filter_complex", filter_complex,
        "-map", "[vout]",
    ]
    if has_audio and a_labels:
        cmd += ["-map", "[aout]"]

    cmd += [
        "-c:v", "libx264", "-preset", "faster", "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-y", str(output_path),
    ]

    _, stderr, code = await run_cmd(cmd)

    if output_path.exists() and output_path.stat().st_size > 5000:
        print(f"✅ Speed ramp applied: {len(ramps)} ramps, {output_path.stat().st_size // 1024}KB")
        return output_path

    print(f"⚠️  Speed ramp failed (code={code}): {stderr[-300:]}")
    return None


def _build_atempo_chain(tempo: float) -> str:
    """
    Build an atempo filter chain. atempo only accepts values in [0.5, 2.0].
    For tempos outside that range, chain multiple atempo filters.
    """
    tempo = max(0.1, tempo)
    filters = []

    if tempo < 0.5:
        # e.g. 0.25 → atempo=0.5,atempo=0.5
        while tempo < 0.5:
            filters.append("atempo=0.5")
            tempo /= 0.5
        if abs(tempo - 1.0) > 0.01:
            filters.append(f"atempo={tempo:.4f}")
    elif tempo > 2.0:
        # e.g. 3.0 → atempo=2.0,atempo=1.5
        while tempo > 2.0:
            filters.append("atempo=2.0")
            tempo /= 2.0
        if abs(tempo - 1.0) > 0.01:
            filters.append(f"atempo={tempo:.4f}")
    else:
        filters.append(f"atempo={tempo:.4f}")

    return ",".join(filters)


# ── Text helpers ──────────────────────────────────────────────────────────────

def _safe_text(text: str, max_len: int = 32) -> str:
    """Strip characters that break FFmpeg drawtext."""
    text = re.sub(r"['\\[\]{}:=@#]", "", text)
    return text.strip()[:max_len]


def _extract_title_text(description: str) -> Optional[str]:
    """Extract title text from cut description."""
    for pattern in [r'"([^"]{2,35})"', r"'([^']{2,35})'", r"text\s+([A-Z][^,.\n]{2,30})"]:
        m = re.search(pattern, description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    words = description.split()
    caps  = [w.rstrip(".,!?") for w in words if w.isupper() and len(w) > 2]
    return " ".join(caps[:5]) if caps else None


# ── Filter chain builder ──────────────────────────────────────────────────────

def build_filter_chain(
    analysis: dict,
    style: str,
    options: list,
    quality: str,
    src_w: int, src_h: int,
    tw: int, th: int,
    duration: float,
) -> str:
    """
    Build the complete FFmpeg -vf filter chain.
    Speed ramps are handled separately via filter_complex before this runs.
    """
    filters: List[str] = []
    cuts  = analysis.get("cuts", [])
    font  = FONT

    # ── 1. Fade in / out timestamps ───────────────────────────────────────────
    fade_in_dur  = 0.5
    fade_out_ts  = None
    fade_out_dur = 0.8

    for cut in cuts:
        ctype = (cut.get("type") or "").lower()
        ts    = cut.get("timestamp")
        cdur  = cut.get("duration")
        try:
            ts   = float(ts)   if ts   is not None else None
            cdur = float(cdur) if cdur is not None else None
        except (TypeError, ValueError):
            ts = cdur = None

        if "fade_in" in ctype or ("fade" in ctype and "in" in ctype and "out" not in ctype):
            fade_in_dur = min(float(cdur or 0.5), 1.5)
        elif ctype in ("fade", "fade_out") or (ts and "fade to black" in (cut.get("description") or "").lower()):
            if ts is not None:
                fade_out_ts  = max(0.1, min(ts, duration - 0.3))
                fade_out_dur = min(float(cdur or 0.8), duration - fade_out_ts)

    if "fades" in options:
        filters.append(f"fade=t=in:st=0:d={fade_in_dur:.2f}")

    # ── 2. Zoom punch ─────────────────────────────────────────────────────────
    if "zooms" in options:
        zoom_cuts = []
        for cut in cuts:
            ctype = (cut.get("type") or "").lower()
            desc  = (cut.get("description") or "").lower()
            ts    = cut.get("timestamp")
            cdur  = cut.get("duration")
            try:
                ts   = float(ts)   if ts   is not None else None
                cdur = float(cdur) if cdur is not None else None
            except (TypeError, ValueError):
                ts = cdur = None
            if ("zoom" in ctype or "punch" in ctype or "zoom" in desc) and ts is not None:
                z_ts  = max(0.1, min(ts, duration - 0.5))
                z_dur = min(float(cdur or 1.5), duration - z_ts, 2.5)
                if z_dur > 0.3:
                    zoom_cuts.append((z_ts, z_dur))

        if zoom_cuts:
            z_ts, z_dur = zoom_cuts[0]
            z_end = z_ts + z_dur
            cw = int(src_w * 0.78) & ~1
            ch = int(src_h * 0.78) & ~1
            cx = (src_w - cw) // 2
            cy = (src_h - ch) // 2
            filters.append(
                f"crop="
                f"w=if(between(t\\,{z_ts:.3f}\\,{z_end:.3f})\\,{cw}\\,iw):"
                f"h=if(between(t\\,{z_ts:.3f}\\,{z_end:.3f})\\,{ch}\\,ih):"
                f"x=if(between(t\\,{z_ts:.3f}\\,{z_end:.3f})\\,{cx}\\,0):"
                f"y=if(between(t\\,{z_ts:.3f}\\,{z_end:.3f})\\,{cy}\\,0)"
            )
            filters.append(f"scale={src_w}:{src_h}")

    # ── 3. Color grade ────────────────────────────────────────────────────────
    if "color" in options:
        grade = COLOR_GRADES.get(style, COLOR_GRADES["cinematic"])
        filters.append(grade)

    # ── 4. Film grain ─────────────────────────────────────────────────────────
    if "grain" in options or style in ("warzone", "cinematic", "pubg"):
        grain = GRAIN.get(style, GRAIN["default"])
        filters.append(grain)

    # ── 5. Letterbox ─────────────────────────────────────────────────────────
    if "letterbox" in options or style in ("warzone", "cinematic"):
        filters.extend(LETTERBOX)

    # ── 6. Title cards ────────────────────────────────────────────────────────
    if "captions" in options and font:
        for cut in cuts:
            ctype = (cut.get("type") or "").lower()
            ts    = cut.get("timestamp")
            cdur  = cut.get("duration")
            desc  = cut.get("description") or ""
            if ctype != "title" or ts is None:
                continue
            try:
                ts   = float(ts)
                cdur = float(cdur or 1.5)
            except (TypeError, ValueError):
                continue

            title_text = _extract_title_text(desc)
            if not title_text:
                continue

            t_ts  = max(0.0, min(ts, duration - 0.3))
            t_end = min(t_ts + cdur, duration)
            safe  = _safe_text(title_text, 30)
            if safe:
                filters.append(
                    f"drawtext=text='{safe}'"
                    f":fontfile='{font}'"
                    f":fontsize=80:fontcolor=white"
                    f":borderw=5:bordercolor=black@0.95"
                    f":x=(w-text_w)/2:y=h*0.72"
                    f":enable='between(t,{t_ts:.3f},{t_end:.3f})'"
                )

    # ── 7. TikTok captions from transcript ───────────────────────────────────
    if "captions" in options and font:
        for cap in (analysis.get("captions") or [])[:10]:
            text = (cap.get("text") or "").strip()
            if not text:
                continue
            try:
                cs = max(0.0, float(cap.get("start", 0)))
                ce = min(duration, float(cap.get("end", cs + 1.0)))
            except (TypeError, ValueError):
                continue
            if ce - cs < 0.2:
                continue
            safe = _safe_text(text.upper(), 26)
            if safe:
                filters.append(
                    f"drawtext=text='{safe}'"
                    f":fontfile='{font}'"
                    f":fontsize=62:fontcolor=white"
                    f":borderw=4:bordercolor=black@0.95"
                    f":box=1:boxcolor=black@0.35:boxborderw=8"
                    f":x=(w-text_w)/2:y=h*0.84"
                    f":enable='between(t,{cs:.3f},{ce:.3f})'"
                )

    # ── 8. Scale to target resolution ────────────────────────────────────────
    filters.append(f"scale={tw}:{th}:flags=lanczos:force_original_aspect_ratio=increase")
    filters.append(f"crop={tw}:{th}")

    # ── 9. Sharpening post-scale ─────────────────────────────────────────────
    sharpen = SHARPEN.get(quality)
    if sharpen:
        filters.append(sharpen)

    # ── 10. Fade out ─────────────────────────────────────────────────────────
    if "fades" in options:
        fo_ts  = fade_out_ts if fade_out_ts is not None else max(0.1, duration - 1.0)
        fo_dur = min(fade_out_dur, duration - fo_ts)
        if fo_dur > 0.1:
            filters.append(f"fade=t=out:st={fo_ts:.3f}:d={fo_dur:.3f}")

    return ",".join(filters) if filters else "null"


# ── Main render ───────────────────────────────────────────────────────────────

async def render_video(
    video_path: Path,
    analysis: dict,
    output_path: Path,
    style: str,
    options: list,
    resolution: Optional[Tuple[int, int]],
    fps: Optional[int],
    quality: str,
    add_music: bool,
) -> Path:
    """
    Main render function. Always produces an output file.
    Falls through multiple strategies if one fails.

    Order:
      1. Apply speed ramps (if any) → intermediate_ramp.mp4
      2. Apply full filter chain (color, zoom, captions, letterbox, etc.)
      3. Mix in music
    """
    output_path = TMP_DIR / output_path.name
    duration, src_w, src_h, has_audio = await probe_video(video_path)

    tw, th = resolution if resolution else (src_w, src_h)
    tw = tw & ~1
    th = th & ~1

    # Safety cap — Railway free tier. Cap at 1080p to avoid OOM-kill.
    MAX_W, MAX_H = 1920, 1080
    if tw * th > MAX_W * MAX_H:
        ratio = min(MAX_W / tw, MAX_H / th)
        tw    = int(tw * ratio) & ~1
        th    = int(th * ratio) & ~1
        print(f"⚠️  Resolution capped to {tw}x{th}")

    q_preset, q_crf, q_bitrate, q_maxrate = QUALITY.get(quality.lower(), QUALITY["high"])
    print(f"🎬 Render: {src_w}x{src_h} → {tw}x{th} | {quality} | preset={q_preset} crf={q_crf}")

    # ── Step 1: Speed ramps ───────────────────────────────────────────────────
    cuts = analysis.get("cuts", [])
    speed_cuts = [
        c for c in cuts
        if (c.get("type") or "").lower() == "speed_ramp"
    ]

    working_path = video_path  # will be swapped if speed ramp succeeds

    if speed_cuts and "cuts" in options:
        ramp_out = TMP_DIR / f"{output_path.stem}_ramp.mp4"
        print(f"⚡ Applying {len(speed_cuts)} speed ramp(s)…")
        ramp_result = await apply_speed_ramps(
            video_path=video_path,
            speed_cuts=speed_cuts,
            output_path=ramp_out,
            duration=duration,
            has_audio=has_audio,
        )
        if ramp_result:
            working_path = ramp_result
            # Re-probe after ramp (duration changes with speed adjustments)
            duration, src_w, src_h, has_audio = await probe_video(working_path)
            _probe_cache[str(working_path)] = (duration, src_w, src_h, has_audio)
        else:
            print("⚠️  Speed ramp failed — continuing without it")

    # ── Step 2: Parse trim ────────────────────────────────────────────────────
    trim_start = None
    trim_dur   = None
    for cut in cuts:
        if (cut.get("type") or "").lower() == "trim":
            try:
                ts         = float(cut.get("timestamp", 0))
                trim_start = max(0.0, min(ts, duration - 1.0))
                trim_dur   = duration - trim_start
            except (TypeError, ValueError):
                pass
            break

    # ── Step 3: Full filter chain ─────────────────────────────────────────────
    vf = build_filter_chain(
        analysis=analysis,
        style=style,
        options=options,
        quality=quality,
        src_w=src_w, src_h=src_h,
        tw=tw, th=th,
        duration=duration,
    )
    print(f"🎬 Filter chain ({len(vf)} chars): {vf[:180]}…")

    intermediate = TMP_DIR / f"{output_path.stem}_raw.mp4"

    cmd = [FFMPEG]
    if trim_start is not None:
        cmd += ["-ss", f"{trim_start:.3f}"]
    cmd += ["-i", str(working_path)]
    if trim_start is not None and trim_dur is not None:
        cmd += ["-t", f"{trim_dur:.3f}"]
    if fps:
        cmd += ["-r", str(fps)]
    cmd += [
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", str(q_crf),
        "-preset", q_preset,
        "-b:v", f"{q_bitrate}k",
        "-maxrate", f"{q_maxrate}k",
        "-bufsize", f"{q_maxrate * 2}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-y", str(intermediate),
    ]

    _, stderr, code = await run_cmd(cmd)
    print(f"FFmpeg code={code} stderr tail: {stderr[-400:]}")

    if not intermediate.exists() or intermediate.stat().st_size < 5000:
        print("⚠️  Primary render failed — running color-only fallback")
        intermediate = await _color_only_fallback(
            working_path, style, tw, th, q_crf, q_preset, q_bitrate, fps
        )

    # Clean up ramp intermediate if it was created
    if working_path != video_path and working_path.exists():
        try:
            working_path.unlink()
        except Exception:
            pass

    if not intermediate or not intermediate.exists():
        print("⚠️  All renders failed — stream copy")
        await run_cmd([
            FFMPEG, "-i", str(video_path),
            "-c", "copy", "-movflags", "+faststart",
            "-y", str(output_path),
        ])
        return output_path

    print(f"✅ Render: {intermediate.stat().st_size // 1024}KB")

    # ── Step 4: Mix music ─────────────────────────────────────────────────────
    if add_music and "music" in options:
        try:
            music = await asyncio.wait_for(get_music(style), timeout=90.0)
            if music:
                mixed = await mix_music(intermediate, music, output_path, duration, has_audio)
                if mixed:
                    try:
                        intermediate.unlink()
                    except Exception:
                        pass
                    return mixed
        except asyncio.TimeoutError:
            print("⚠️  Music timed out")
        except Exception as e:
            print(f"⚠️  Music error: {e}")

    shutil.move(str(intermediate), str(output_path))
    return output_path


async def _color_only_fallback(
    video_path: Path,
    style: str,
    tw: int, th: int,
    crf: int, preset: str, bitrate: int,
    fps: Optional[int],
) -> Optional[Path]:
    """Fallback: color grade + scale only. Maximum compatibility."""
    grade = COLOR_GRADES.get(style, "eq=contrast=1.1:saturation=1.0")
    vf    = f"{grade},scale={tw}:{th}:flags=lanczos:force_original_aspect_ratio=increase,crop={tw}:{th}"
    out   = TMP_DIR / f"fallback_{video_path.stem}.mp4"

    cmd = [FFMPEG, "-i", str(video_path)]
    if fps:
        cmd += ["-r", str(fps)]
    cmd += [
        "-vf", vf,
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-b:v", f"{bitrate}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-y", str(out),
    ]
    _, stderr, code = await run_cmd(cmd)
    print(f"Fallback code={code}: {stderr[-200:]}")
    return out if out.exists() and out.stat().st_size > 5000 else None
