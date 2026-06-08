"""
ClipMind AI Analyzer
Uses Groq to generate edit plans. Falls back gracefully if API fails.
"""
import json
import os
import re
from typing import Optional

from groq import AsyncGroq

STYLE_DESC = {
    "freefire":    "Free Fire mobile — fast burst cuts on kills, warm orange grade, speed ramp on headshots",
    "warzone":     "Warzone — tactical cinematic, desaturated military grade, letterbox, film grain, dramatic zoom",
    "apex":        "Apex Legends — futuristic, quick cuts on ability use and kills, movement highlights",
    "valorant":    "VALORANT — clean crisp grade, high contrast, sharp cuts on clutch rounds",
    "fortnite":    "Fortnite — vibrant pop colours, fast build-battle cuts, energetic zoom-ins",
    "pubg":        "PUBG — realistic military tone, desaturated grade, precise long-range shots, squad wipes, tense pacing",
    "cinematic":   "Cinematic — slow reveals, letterbox, film grain, wide shots, professional",
    "social":      "Social/TikTok/Reels — punchy cuts every 1-2s, hook in first 2s, high energy",
    "vlog":        "Vlog/YouTube — warm natural grade, jump cuts on dead air, authentic",
    "educational": "Educational — clear pacing, neutral grade, highlight key moments",
    "corporate":   "Corporate — clean neutral grade, measured pace, authoritative",
    "documentary": "Documentary — naturalistic grade, storytelling-first pacing",
}

GAMING_STYLES = {"freefire", "warzone", "apex", "valorant", "fortnite", "pubg"}


class AIAnalyzer:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        self.client = AsyncGroq(api_key=api_key) if api_key else None
        if not api_key:
            print("⚠️  GROQ_API_KEY not set — using fallback edit plans")

    async def analyze(
        self,
        transcript: str,
        duration: float,
        style: str,
        options: list,
        num_frames: int,
        custom_prompt: str = "",
    ) -> dict:
        if not self.client:
            return self._fallback(duration, style)

        style_desc = STYLE_DESC.get(style, STYLE_DESC["cinematic"])
        mid   = round(duration * 0.45, 2)
        end   = round(max(0.0, duration - 1.0), 2)
        end_t = round(max(0.0, duration - 2.0), 2)

        gaming_block = ""
        if style in GAMING_STYLES:
            gaming_block = f"""
GAMING RULES ({style.upper()}):
- Detect hype moments from transcript: "kill","headshot","clutch","eliminated","squad wipe","lets go","insane","oh my god","down","knocked"
- Place zoom cuts AT those timestamps
- Add speed_ramp cuts at kill moments (speed_in: 0.5, speed_out: 1.25)
- Title cards: "SQUAD WIPE 🔥", "1v4 CLUTCH", "HEADSHOT 💀", "NO SCOPE 😤", "KNOCKED 💥"
- Trim any lobby/loading dead time at start/end
- Max 3 speed_ramp cuts — only best moments
"""

        custom_block = ""
        if custom_prompt and custom_prompt.strip():
            custom_block = f"""
USER INSTRUCTIONS (HIGHEST PRIORITY):
\"\"\"{custom_prompt.strip()}\"\"\"
"""

        prompt = f"""You are a professional video editor AI. Return ONLY valid JSON, no markdown.

VIDEO INFO:
- Duration: {duration:.2f}s
- Style: {style} — {style_desc}
- Frames analysed: {num_frames}
- Options enabled: {', '.join(options) if options else 'all'}
- Transcript: {(transcript or 'No speech detected.')[:2000]}

{gaming_block}{custom_block}

RULES:
1. All timestamps: 0.0 to {duration:.2f}
2. timestamp + duration must not exceed {duration:.2f}
3. Minimum 5 cuts
4. Return ONLY raw JSON — no code blocks, no extra text

REQUIRED JSON:
{{
  "summary": "2-3 sentences on the clip and edit approach.",
  "tags": ["tag1","tag2","tag3","tag4","tag5"],
  "bpm": 140,
  "cuts": [
    {{"type":"fade_in","timestamp":0.0,"duration":0.5,"description":"Fade in from black"}},
    {{"type":"trim","timestamp":0.5,"duration":null,"description":"Trim dead air at start"}},
    {{"type":"speed_ramp","timestamp":{mid},"duration":1.0,"speed_in":0.5,"speed_out":1.25,"description":"Speed ramp on kill"}},
    {{"type":"zoom","timestamp":{mid},"duration":1.5,"description":"Zoom punch on kill moment"}},
    {{"type":"title","timestamp":{end_t},"duration":1.5,"description":"Title card text: SQUAD WIPE 🔥"}},
    {{"type":"fade_out","timestamp":{end},"duration":0.8,"description":"Fade to black"}}
  ],
  "captions": [
    {{"text":"lets go","start":1.2,"end":2.0}},
    {{"text":"no way","start":3.5,"end":4.2}}
  ],
  "color_grade": "One sentence on the color grade applied.",
  "music_suggestions": [
    {{"name":"Style name","genre":"phonk/trap/cinematic","mood":"hype/epic/chill","reason":"Why it fits"}}
  ],
  "effects": [
    {{"effect":"color_grade","description":"Color profile applied"}},
    {{"effect":"zoom","description":"Punch-in on kill"}},
    {{"effect":"speed_ramp","description":"Slow-mo into kill, snap fast"}},
    {{"effect":"captions","description":"TikTok-style captions"}},
    {{"effect":"fade_in_out","description":"Smooth fade"}}
  ],
  "pacing_note": "One sentence on pacing.",
  "export_tip": "Best export tip for this content."
}}"""

        raw = ""
        try:
            resp = await self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a pro video editor AI. Return ONLY valid JSON. No markdown, no code fences."},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.4,
                max_tokens=2000,
            )
            raw    = resp.choices[0].message.content.strip()
            raw    = self._clean_json(raw)
            result = json.loads(raw)
            return self._validate(result, duration, style)

        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e} | raw: {raw[:300]}")
        except Exception as e:
            print(f"Analysis error: {e}")

        return self._fallback(duration, style)

    def _clean_json(self, raw: str) -> str:
        raw = re.sub(r"^```(?:json)?", "", raw, flags=re.MULTILINE)
        raw = re.sub(r"```$",          "", raw, flags=re.MULTILINE)
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        return raw[start:end].strip() if start != -1 and end > start else raw

    def _validate(self, result: dict, duration: float, style: str) -> dict:
        defaults = {
            "summary":           f"Professional {style} edit.",
            "tags":              [style, "gaming", "clip", "edit", "pro"],
            "bpm":               130,
            "cuts":              self._default_cuts(duration),
            "captions":          [],
            "color_grade":       f"{style} color profile applied.",
            "music_suggestions": [{"name": "Hype Phonk", "genre": "phonk", "mood": "hype", "reason": "Gaming energy"}],
            "effects":           [{"effect": "color_grade", "description": f"{style} grade applied"}],
            "pacing_note":       f"Tight pacing for {duration:.1f}s clip.",
            "export_tip":        "Export 1080p 60fps for best results.",
        }
        for k, v in defaults.items():
            if k not in result or result[k] is None:
                result[k] = v

        try:
            result["bpm"] = max(60, min(200, int(result.get("bpm", 130))))
        except (TypeError, ValueError):
            result["bpm"] = 130

        clean_cuts = []
        for cut in result.get("cuts", []):
            ts   = cut.get("timestamp")
            cdur = cut.get("duration")
            try:
                if ts is not None:
                    ts = max(0.0, min(float(ts), duration - 0.1))
                if cdur is not None:
                    cdur = max(0.1, float(cdur))
                    if ts is not None and ts + cdur > duration:
                        cdur = max(0.1, duration - ts)
            except (TypeError, ValueError):
                continue
            cut["timestamp"] = ts
            cut["duration"]  = cdur
            if cut.get("type") == "speed_ramp":
                try:
                    cut["speed_in"]  = max(0.1, min(1.0,  float(cut.get("speed_in",  0.5))))
                    cut["speed_out"] = max(1.0, min(3.0,  float(cut.get("speed_out", 1.25))))
                except (TypeError, ValueError):
                    cut["speed_in"]  = 0.5
                    cut["speed_out"] = 1.25
            clean_cuts.append(cut)
        result["cuts"] = clean_cuts if clean_cuts else self._default_cuts(duration)

        clean_caps = []
        for cap in result.get("captions", []):
            text = (cap.get("text") or "").strip()
            if not text:
                continue
            try:
                s = max(0.0, float(cap.get("start", 0)))
                e = min(duration, float(cap.get("end", s + 1.0)))
                if e - s > 0.1:
                    clean_caps.append({"text": text, "start": s, "end": e})
            except (TypeError, ValueError):
                continue
        result["captions"] = clean_caps

        return result

    def _default_cuts(self, duration: float) -> list:
        cuts = [{"type": "fade_in", "timestamp": 0.0, "duration": 0.5, "description": "Fade in"}]
        if duration > 3:
            mid = round(duration * 0.5, 2)
            cuts.append({"type": "zoom", "timestamp": mid, "duration": 1.5, "description": "Zoom punch"})
        if duration > 4:
            cuts.append({"type": "title", "timestamp": round(duration * 0.7, 2), "duration": 1.5, "description": 'Title card text: "INSANE PLAY"'})
        cuts.append({"type": "fade_out", "timestamp": round(max(0.1, duration - 1.0), 2), "duration": 0.8, "description": "Fade out"})
        return cuts

    def _fallback(self, duration: float, style: str) -> dict:
        return {
            "summary":           f"{style.upper()} clip — professional edit applied.",
            "tags":              [style, "gaming", "highlight", "clip", "pro"],
            "bpm":               140,
            "cuts":              self._default_cuts(duration),
            "captions":          [],
            "color_grade":       f"{style} color grade applied.",
            "music_suggestions": [
                {"name": "Phonk Drift",     "genre": "phonk",     "mood": "hype", "reason": "High energy gaming"},
                {"name": "Orchestral Hype", "genre": "cinematic", "mood": "epic", "reason": "Dramatic moments"},
            ],
            "effects": [
                {"effect": "color_grade", "description": f"{style} color profile"},
                {"effect": "fade_in_out", "description": "Smooth fade in/out"},
                {"effect": "zoom",        "description": "Dynamic zoom punch"},
                {"effect": "speed_ramp",  "description": "Slow-mo into kill, snap fast"},
            ],
            "pacing_note": f"Tight cuts for {duration:.1f}s clip.",
            "export_tip":  "Export 1080p 60fps for best gaming content quality.",
        }
