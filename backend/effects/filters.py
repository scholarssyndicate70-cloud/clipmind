"""
ClipMind Effects Engine
Pre-validated FFmpeg filter chains.
"""

COLOR_GRADES = {
    "freefire":    "eq=brightness=0.06:contrast=1.30:saturation=1.55:gamma_r=1.12:gamma_b=0.88",
    "warzone":     "eq=brightness=-0.04:contrast=1.42:saturation=0.55:gamma=0.95:gamma_r=0.92",
    "apex":        "eq=brightness=0.02:contrast=1.35:saturation=1.20:gamma=1.02:gamma_b=1.10",
    "valorant":    "eq=brightness=0.05:contrast=1.48:saturation=0.88:gamma=0.97",
    "fortnite":    "eq=brightness=0.10:contrast=1.20:saturation=1.75:gamma_r=1.08:gamma_b=0.92",
    "pubg":        "eq=brightness=-0.01:contrast=1.22:saturation=0.90:gamma=0.98",
    "cinematic":   "eq=brightness=0.02:contrast=1.18:saturation=0.80:gamma=0.97",
    "social":      "eq=brightness=0.07:contrast=1.28:saturation=1.40:gamma_r=1.05",
    "vlog":        "eq=brightness=0.07:contrast=1.12:saturation=1.20:gamma_r=1.10:gamma_b=0.94",
    "educational": "eq=brightness=0.03:contrast=1.06:saturation=1.00",
    "corporate":   "eq=brightness=0.00:contrast=1.10:saturation=0.88:gamma=1.02",
    "documentary": "eq=brightness=0.00:contrast=1.05:saturation=0.95",
}

GRAIN = {
    "warzone":   "noise=alls=18:allf=t",
    "cinematic": "noise=alls=14:allf=t",
    "pubg":      "noise=alls=12:allf=t",
    "vlog":      "noise=alls=8:allf=t",
    "default":   "noise=alls=10:allf=t",
}

SHARPEN = {
    "draft":  None,
    "good":   "unsharp=3:3:0.8:3:3:0.0",
    "high":   "unsharp=5:5:1.2:5:5:0.0",
    "ultra":  "unsharp=5:5:1.5:5:5:0.0",
    "max":    "unsharp=7:7:2.0:5:5:0.0",
}

LETTERBOX = [
    "drawbox=x=0:y=0:w=iw:h=ih*0.08:color=black@1.0:t=fill",
    "drawbox=x=0:y=ih*0.92:w=iw:h=ih*0.08:color=black@1.0:t=fill",
]

# (ffmpeg_preset, crf, target_bitrate_kbps, max_bitrate_kbps)
QUALITY = {
    "draft":  ("ultrafast", 30,  1500,  3000),
    "good":   ("faster",    26,  4000,  8000),
    "high":   ("medium",    22,  8000, 16000),
    "ultra":  ("slow",      18, 16000, 32000),
    "max":    ("slow",      14, 30000, 60000),
}

MUSIC_FILES = {
    "freefire":  "gaming_phonk.mp3",
    "warzone":   "gaming_epic.mp3",
    "apex":      "gaming_epic.mp3",
    "valorant":  "gaming_phonk.mp3",
    "fortnite":  "gaming_upbeat.mp3",
    "pubg":      "gaming_epic.mp3",
    "social":    "gaming_phonk.mp3",
    "cinematic": "gaming_epic.mp3",
    "vlog":      "gaming_lofi.mp3",
    "default":   "gaming_phonk.mp3",
}

YOUTUBE_TRACKS = {
    "freefire":  ("https://youtu.be/I7Q3izYmevc", "yt_phonk1.mp3"),
    "valorant":  ("https://youtu.be/317RHaFF7Xk", "yt_phonk2.mp3"),
    "social":    ("https://youtube.com/shorts/bshtweq1KrI", "yt_phonk3.mp3"),
    "warzone":   ("https://youtu.be/317RHaFF7Xk", "yt_phonk2.mp3"),
    "apex":      ("https://youtube.com/shorts/sJtzgVsmToQ", "yt_phonk4.mp3"),
    "pubg":      ("https://youtu.be/317RHaFF7Xk", "yt_phonk2.mp3"),
    "fortnite":  ("https://youtube.com/shorts/bshtweq1KrI", "yt_phonk3.mp3"),
    "cinematic": ("https://youtube.com/shorts/sJtzgVsmToQ", "yt_phonk4.mp3"),
    "vlog":      ("https://youtube.com/shorts/bshtweq1KrI", "yt_phonk3.mp3"),
}
