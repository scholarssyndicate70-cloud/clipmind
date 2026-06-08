const { useState, useEffect, useRef, useCallback } = React;

// ── Config ────────────────────────────────────────────────────────────────────
const BACKEND = (() => {
  if (window.location.hostname === "localhost") return "http://localhost:8000";
  return "https://clipmind-production-5d52.up.railway.app";
})();

const STYLES = [
  { id: "freefire",  label: "Free Fire",    emoji: "🔥" },
  { id: "warzone",   label: "Warzone",      emoji: "💀" },
  { id: "apex",      label: "Apex",         emoji: "⚡" },
  { id: "valorant",  label: "Valorant",     emoji: "🎯" },
  { id: "fortnite",  label: "Fortnite",     emoji: "🏆" },
  { id: "pubg",      label: "PUBG",         emoji: "🪖" },
  { id: "cinematic", label: "Cinematic",    emoji: "🎬" },
  { id: "social",    label: "Shorts/Reels", emoji: "📱" },
  { id: "vlog",      label: "Vlog",         emoji: "🎙️" },
];

const OPTIONS = [
  { id: "cuts",     label: "Smart Cuts",      icon: "✂️",  default: true  },
  { id: "zooms",    label: "Zoom Punches",     icon: "🔍", default: true  },
  { id: "color",    label: "Color Grade",      icon: "🎨", default: true  },
  { id: "captions", label: "Title Cards",      icon: "📝", default: true  },
  { id: "fades",    label: "Fade In/Out",      icon: "🎬", default: true  },
  { id: "grain",    label: "Film Grain",       icon: "📻", default: false },
  { id: "letterbox",label: "Letterbox",        icon: "🖼️", default: false },
  { id: "music",    label: "Music",            icon: "🎵", default: true  },
];

const RESOLUTIONS = [
  { id: "720p",  label: "720p",   note: "" },
  { id: "1080p", label: "1080p",  note: "Best" },
  { id: "1440p", label: "1440p",  note: "⚡ Slow" },
  { id: "4k",    label: "4K",     note: "⚡ Server+" },
  { id: "8k",    label: "8K",     note: "⚡ Server+" },
  { id: "9:16",  label: "9:16",   note: "Vertical" },
];

const FPS_OPTIONS   = [24, 30, 60, 120];
const QUALITY_OPTIONS = [
  { id: "good",  label: "Good"  },
  { id: "high",  label: "High"  },
  { id: "ultra", label: "Ultra" },
  { id: "max",   label: "Max",  note: "Slow" },
];

const STEPS = [
  "Connecting",
  "Extracting frames",
  "Transcribing audio",
  "AI analysis",
  "Building edit plan",
  "Rendering",
  "Packaging",
  "Done",
];

// ── Styles ────────────────────────────────────────────────────────────────────
const css = `
  body { overflow-x: hidden; }
  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* Layout */
  .app { display: flex; flex-direction: column; min-height: 100vh; }
  .nav { display: flex; align-items: center; justify-content: space-between; padding: 0 1.5rem; height: 56px; background: var(--bg2); border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 100; }
  .nav-logo { font-size: 1.2rem; font-weight: 700; letter-spacing: 0.12em; color: var(--text); }
  .nav-logo span { color: var(--red); }
  .nav-badges { display: flex; gap: 0.5rem; }
  .badge { padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.08em; }
  .badge-pro { background: var(--red); color: white; }
  .badge-ai  { background: #1e293b; color: #38bdf8; border: 1px solid #38bdf840; }

  .main { display: grid; grid-template-columns: 280px 1fr 300px; gap: 0; height: calc(100vh - 56px); overflow: hidden; }

  /* Left panel */
  .panel-left { background: var(--bg2); border-right: 1px solid var(--border); overflow-y: auto; padding: 1rem 0; }
  .panel-section { padding: 0.75rem 1rem; }
  .panel-section + .panel-section { border-top: 1px solid var(--border); }
  .panel-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.12em; color: var(--muted); text-transform: uppercase; margin-bottom: 0.6rem; }

  /* Style grid */
  .style-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem; }
  .style-btn { display: flex; flex-direction: column; align-items: center; gap: 0.25rem; padding: 0.6rem 0.4rem; background: var(--bg3); border: 1px solid var(--border); border-radius: var(--radius); cursor: pointer; transition: all 0.15s; font-size: 0.7rem; color: var(--muted); }
  .style-btn:hover { border-color: var(--red); color: var(--text); }
  .style-btn.active { background: #1a0a0d; border-color: var(--red); color: var(--text); }
  .style-btn .emoji { font-size: 1.4rem; }

  /* Options */
  .opt-row { display: flex; align-items: center; justify-content: space-between; padding: 0.45rem 0; }
  .opt-name { font-size: 0.78rem; color: var(--text); display: flex; align-items: center; gap: 0.4rem; }
  .opt-icon { font-size: 0.9rem; }
  .toggle { width: 36px; height: 20px; background: var(--bg4); border-radius: 10px; cursor: pointer; position: relative; transition: background 0.2s; border: none; }
  .toggle.on { background: var(--red); }
  .toggle::after { content: ''; position: absolute; width: 14px; height: 14px; background: white; border-radius: 50%; top: 3px; left: 3px; transition: transform 0.2s; }
  .toggle.on::after { transform: translateX(16px); }

  /* Custom prompt */
  .prompt-header { display: flex; align-items: center; justify-content: space-between; cursor: pointer; padding: 0.75rem 1rem; }
  .prompt-header:hover { background: var(--bg3); }
  .prompt-chevron { font-size: 0.7rem; color: var(--muted); transition: transform 0.2s; }
  .prompt-chevron.open { transform: rotate(180deg); }
  .prompt-body { padding: 0 1rem 0.75rem; }
  .prompt-textarea { width: 100%; background: var(--bg3); border: 1px solid var(--border); border-radius: 8px; color: var(--text); font-size: 0.75rem; font-family: var(--font); padding: 0.6rem 0.75rem; resize: vertical; min-height: 72px; max-height: 150px; outline: none; transition: border-color 0.2s; }
  .prompt-textarea:focus { border-color: var(--red); }
  .prompt-meta { display: flex; justify-content: space-between; margin-top: 0.35rem; font-size: 0.67rem; color: var(--muted); }
  .prompt-clear { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 0.67rem; }
  .prompt-clear:hover { color: var(--text); }

  /* Center panel */
  .panel-center { display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }

  /* Upload zone */
  .upload-zone { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 1rem; border: 2px dashed var(--border); margin: 1.5rem; border-radius: 16px; cursor: pointer; transition: all 0.2s; padding: 2rem; }
  .upload-zone:hover, .upload-zone.drag { border-color: var(--red); background: #1a0a0d40; }
  .upload-icon { font-size: 3rem; }
  .upload-title { font-size: 1.1rem; font-weight: 600; color: var(--text); }
  .upload-sub { font-size: 0.78rem; color: var(--muted); text-align: center; line-height: 1.5; }
  .upload-btn { padding: 0.6rem 1.5rem; background: var(--red); color: white; border: none; border-radius: 8px; font-size: 0.85rem; font-weight: 600; cursor: pointer; }

  /* File bar */
  .file-bar { display: flex; align-items: center; gap: 0.75rem; padding: 0.75rem 1.5rem; background: var(--bg2); border-bottom: 1px solid var(--border); }
  .file-thumb { width: 40px; height: 40px; background: var(--bg4); border-radius: 6px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; overflow: hidden; flex-shrink: 0; }
  .file-thumb video { width: 100%; height: 100%; object-fit: cover; }
  .file-info { flex: 1; min-width: 0; }
  .file-name { font-size: 0.82rem; font-weight: 500; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .file-meta { font-size: 0.7rem; color: var(--muted); }
  .file-remove { background: none; border: none; color: var(--muted); cursor: pointer; font-size: 0.8rem; padding: 0.25rem 0.5rem; border-radius: 4px; }
  .file-remove:hover { background: var(--bg4); color: var(--text); }

  /* Progress card */
  .progress-card { margin: 1.5rem; background: var(--bg2); border: 1px solid var(--border); border-radius: 14px; padding: 1.5rem; }
  .progress-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 1rem; }
  .progress-title { font-size: 0.9rem; font-weight: 600; }
  .progress-time { font-size: 0.75rem; color: var(--muted); }
  .progress-ring-wrap { display: flex; justify-content: center; margin-bottom: 1.25rem; }
  .progress-ring { width: 100px; height: 100px; }
  .ring-bg { fill: none; stroke: var(--bg4); stroke-width: 8; }
  .ring-fg { fill: none; stroke-width: 8; stroke-linecap: round; transform: rotate(-90deg); transform-origin: 50% 50%; transition: stroke-dashoffset 0.5s; }
  .progress-pct { font-size: 1.4rem; font-weight: 700; }
  .progress-status { font-size: 0.78rem; color: var(--muted); }
  .steps-list { display: flex; flex-direction: column; gap: 0.35rem; }
  .step-item { display: flex; align-items: center; gap: 0.6rem; font-size: 0.75rem; color: var(--muted); }
  .step-item.done { color: var(--green); }
  .step-item.active { color: var(--text); font-weight: 500; }
  .step-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--bg4); flex-shrink: 0; }
  .step-dot.done { background: var(--green); }
  .step-dot.active { background: var(--red); box-shadow: 0 0 6px var(--red); }

  /* Analyze button */
  .analyze-wrap { padding: 1rem 1.5rem; }
  .analyze-btn { width: 100%; padding: 0.85rem; background: var(--red); color: white; border: none; border-radius: 10px; font-size: 0.95rem; font-weight: 700; cursor: pointer; transition: all 0.15s; letter-spacing: 0.04em; }
  .analyze-btn:hover:not(:disabled) { background: var(--red2); transform: translateY(-1px); }
  .analyze-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
  .analyze-btn.processing { animation: pulse 1.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.7; } }

  /* Right panel */
  .panel-right { background: var(--bg2); border-left: 1px solid var(--border); overflow-y: auto; }
  .results-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 0.75rem; color: var(--muted); padding: 2rem; text-align: center; }
  .results-empty .empty-icon { font-size: 2.5rem; opacity: 0.4; }

  /* Export panel */
  .export-section { padding: 0.75rem; border-bottom: 1px solid var(--border); }
  .export-section-label { font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em; color: var(--muted); text-transform: uppercase; margin-bottom: 0.5rem; }
  .btn-grid { display: grid; gap: 0.35rem; }
  .btn-grid.cols-2 { grid-template-columns: 1fr 1fr; }
  .btn-grid.cols-3 { grid-template-columns: 1fr 1fr 1fr; }
  .sel-btn { padding: 0.45rem 0.3rem; background: var(--bg3); border: 1px solid var(--border); border-radius: 7px; color: var(--muted); font-size: 0.72rem; cursor: pointer; text-align: center; transition: all 0.15s; }
  .sel-btn:hover { border-color: var(--red); color: var(--text); }
  .sel-btn.active { background: #1a0a0d; border-color: var(--red); color: var(--text); }
  .sel-btn .note { display: block; font-size: 0.6rem; color: var(--muted); }
  .sel-btn.active .note { color: var(--red); }

  /* Download */
  .download-section { padding: 0.75rem; }
  .dl-btn { width: 100%; padding: 0.75rem; background: var(--green); color: white; border: none; border-radius: 10px; font-size: 0.88rem; font-weight: 700; cursor: pointer; transition: all 0.15s; }
  .dl-btn:hover { filter: brightness(1.1); }
  .export-btn { width: 100%; padding: 0.6rem; background: var(--bg3); border: 1px solid var(--border); color: var(--text); border-radius: 8px; font-size: 0.78rem; cursor: pointer; margin-top: 0.4rem; transition: all 0.15s; }
  .export-btn:hover { border-color: var(--red); }

  /* Analysis results */
  .result-block { border-bottom: 1px solid var(--border); }
  .result-header { padding: 0.6rem 0.75rem; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.1em; color: var(--muted); text-transform: uppercase; }
  .result-body { padding: 0 0.75rem 0.75rem; }
  .result-summary { font-size: 0.75rem; color: var(--text); line-height: 1.5; }
  .tag-list { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .tag { padding: 0.2rem 0.5rem; background: var(--bg3); border: 1px solid var(--border); border-radius: 20px; font-size: 0.65rem; color: var(--muted); }
  .cut-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; border-bottom: 1px solid var(--border)40; font-size: 0.72rem; }
  .cut-item:last-child { border-bottom: none; }
  .cut-badge { padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.6rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; flex-shrink: 0; }
  .cut-zoom     { background: #1e3a5f; color: #60a5fa; }
  .cut-fade_in  { background: #1a1a1a; color: #888; }
  .cut-fade_out { background: #1a1a1a; color: #888; }
  .cut-fade     { background: #1a1a1a; color: #888; }
  .cut-title    { background: #1a2a1a; color: #4ade80; }
  .cut-trim     { background: #2a1a1a; color: #f87171; }
  .cut-speed_ramp { background: #2a1f0a; color: #fbbf24; }
  .cut-default  { background: var(--bg4); color: var(--muted); }
  .cut-ts       { color: var(--muted); flex-shrink: 0; }
  .cut-desc     { color: var(--text); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .effect-item  { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; font-size: 0.72rem; }
  .effect-badge { padding: 0.15rem 0.4rem; border-radius: 4px; background: #1e1e30; border: 1px solid var(--border); font-size: 0.6rem; color: var(--blue); font-weight: 600; }
  .music-item   { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.4rem 0; border-bottom: 1px solid var(--border)40; font-size: 0.72rem; }
  .music-item:last-child { border-bottom: none; }
  .music-badge  { padding: 0.15rem 0.4rem; border-radius: 4px; background: #0a1a2a; border: 1px solid #1e3a5f; font-size: 0.6rem; color: #60a5fa; flex-shrink: 0; }
  .music-added-badge { padding: 0.15rem 0.4rem; border-radius: 4px; background: #0a2a0a; border: 1px solid #1a4a1a; font-size: 0.6rem; color: #4ade80; display: inline-flex; align-items: center; gap: 0.3rem; }
  .caption-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0; font-size: 0.72rem; }
  .caption-ts   { color: var(--muted); font-size: 0.65rem; flex-shrink: 0; }
  .caption-text { color: var(--text); font-weight: 500; }
  .file-size-chip { display: inline-flex; align-items: center; gap: 0.3rem; padding: 0.2rem 0.5rem; background: var(--bg3); border: 1px solid var(--border); border-radius: 20px; font-size: 0.68rem; color: var(--muted); margin-top: 0.4rem; }
`;

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / 1024 / 1024).toFixed(1) + " MB";
}
function fmtTs(s) { return s?.toFixed(2) + "s"; }

// ── Components ─────────────────────────────────────────────────────────────── 

function Toggle({ on, onChange }) {
  return <button className={`toggle ${on ? "on" : ""}`} onClick={() => onChange(!on)} />;
}

function ProgressRing({ pct }) {
  const r  = 42;
  const c  = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  const color = pct === 100 ? "#22c55e" : pct > 60 ? "#e03c4a" : "#3b82f6";
  return (
    <svg className="progress-ring" viewBox="0 0 100 100">
      <circle className="ring-bg" cx="50" cy="50" r={r} />
      <circle className="ring-fg" cx="50" cy="50" r={r}
        stroke={color}
        strokeDasharray={c}
        strokeDashoffset={offset} />
      <text x="50" y="50" textAnchor="middle" dominantBaseline="central"
        fill="var(--text)" fontSize="18" fontWeight="700">{pct}%</text>
    </svg>
  );
}

function CutBadge({ type }) {
  const cls = `cut-badge cut-${type || "default"}`;
  return <span className={cls}>{(type || "cut").replace("_", " ")}</span>;
}

function ResultsPanel({ analysis, dlUrl, fileMb, musicAdded, onExport }) {
  if (!analysis) return (
    <div className="results-empty">
      <div className="empty-icon">🎬</div>
      <div style={{ fontSize: "0.8rem", fontWeight: 600 }}>Results appear here</div>
      <div style={{ fontSize: "0.72rem" }}>Upload & process a clip</div>
    </div>
  );
  const cuts     = analysis.cuts || [];
  const effects  = analysis.effects || [];
  const captions = analysis.captions || [];
  const music    = analysis.music_suggestions || [];
  return (
    <div>
      {dlUrl && (
        <div className="download-section">
          {fileMb > 0 && <div className="file-size-chip">📦 {fileMb} MB</div>}
          <a href={`${BACKEND}${dlUrl}`} download>
            <button className="dl-btn" style={{ marginTop: "0.5rem" }}>⬇ Download Clip</button>
          </a>
          <button className="export-btn" onClick={onExport}>🔄 Re-export with new settings</button>
        </div>
      )}
      <div className="result-block">
        <div className="result-header">Summary</div>
        <div className="result-body">
          <div className="result-summary">{analysis.summary}</div>
          {analysis.tags?.length > 0 && (
            <div className="tag-list" style={{ marginTop: "0.5rem" }}>
              {analysis.tags.map((t, i) => <span key={i} className="tag">#{t}</span>)}
            </div>
          )}
        </div>
      </div>
      <div className="result-block">
        <div className="result-header">Cuts ({cuts.length})</div>
        <div className="result-body">
          {cuts.map((c, i) => (
            <div key={i} className="cut-item">
              <CutBadge type={c.type} />
              <span className="cut-ts">{fmtTs(c.timestamp)}</span>
              <span className="cut-desc">{c.description}</span>
            </div>
          ))}
        </div>
      </div>
      {effects.length > 0 && (
        <div className="result-block">
          <div className="result-header">Effects Applied</div>
          <div className="result-body">
            {effects.map((e, i) => (
              <div key={i} className="effect-item">
                <span className="effect-badge">{e.effect?.replace(/_/g," ")}</span>
                <span style={{ fontSize: "0.72rem", color: "var(--text)" }}>{e.description}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {captions.length > 0 && (
        <div className="result-block">
          <div className="result-header">Captions</div>
          <div className="result-body">
            {captions.map((c, i) => (
              <div key={i} className="caption-item">
                <span className="caption-ts">{fmtTs(c.start)}–{fmtTs(c.end)}</span>
                <span className="caption-text">{c.text}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="result-block">
        <div className="result-header">Music Picks</div>
        <div className="result-body">
          {musicAdded && (
            <div style={{ marginBottom: "0.5rem" }}>
              <span className="music-added-badge">✅ ADDED — Background music mixed in</span>
            </div>
          )}
          {music.map((m, i) => (
            <div key={i} className="music-item">
              <span className="music-badge">{m.genre}</span>
              <div>
                <div style={{ color: "var(--text)", fontWeight: 500 }}>{m.name}</div>
                <div style={{ color: "var(--muted)", fontSize: "0.68rem" }}>{m.reason}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
      {analysis.color_grade && (
        <div className="result-block">
          <div className="result-header">Color Grade</div>
          <div className="result-body">
            <div className="result-summary">{analysis.color_grade}</div>
          </div>
        </div>
      )}
      {analysis.pacing_note && (
        <div className="result-block">
          <div className="result-header">Pacing</div>
          <div className="result-body">
            <div className="result-summary">{analysis.pacing_note}</div>
            {analysis.export_tip && (
              <div style={{ marginTop: "0.4rem", fontSize: "0.7rem", color: "var(--yellow)" }}>
                💡 {analysis.export_tip}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
function App() {
  // File state
  const [file, setFile]         = useState(null);
  const [drag, setDrag]         = useState(false);
  const fileRef                 = useRef();

  // Settings
  const [style, setStyle]       = useState("freefire");
  const [opts, setOpts]         = useState(() => new Set(OPTIONS.filter(o => o.default).map(o => o.id)));
  const [resolution, setRes]    = useState("1080p");
  const [fps, setFps]           = useState(60);
  const [quality, setQuality]   = useState("high");
  const [prompt, setPrompt]     = useState("");
  const [promptOpen, setPromptOpen] = useState(false);

  // Pipeline state
  const [processing, setProcessing] = useState(false);
  const [progress, setProgress]     = useState(0);
  const [progStatus, setProgStatus] = useState("");
  const [step, setStep]             = useState(0);
  const [elapsed, setElapsed]       = useState(0);
  const timerRef                    = useRef(null);
  const sseRef                      = useRef(null);

  // Results
  const [analysis, setAnalysis] = useState(null);
  const [dlUrl, setDlUrl]       = useState(null);
  const [jobId, setJobId]       = useState(null);
  const [fileMb, setFileMb]     = useState(0);
  const [musicAdded, setMusicAdded] = useState(false);

  // Reconnect banner
  const [reconnecting, setReconnecting] = useState(false);

  // Server warm-up on mount — wakes Railway from sleep before user uploads
  const [serverReady, setServerReady] = useState(false);
  const [serverError, setServerError] = useState(false);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${BACKEND}/health`, { method: "GET", signal: AbortSignal.timeout(15000) });
        if (!cancelled) setServerReady(r.ok);
      } catch (_) {
        if (!cancelled) setServerError(true);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  // Timer
  useEffect(() => {
    if (processing) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);
    } else {
      clearInterval(timerRef.current);
    }
    return () => clearInterval(timerRef.current);
  }, [processing]);

  const fmtTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  // Drop handlers
  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files[0];
    if (f && f.type.startsWith("video/")) loadFile(f);
  }, []);

  function loadFile(f) {
    setFile(f);
    setAnalysis(null);
    setDlUrl(null);
    setJobId(null);
    setProgress(0);
    setStep(0);
    setElapsed(0);
    setPrompt("");
  }

  function toggleOpt(id) {
    setOpts(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function startProcess() {
    if (!file || processing) return;

    setProcessing(true);
    setProgress(0);
    setStep(0);
    setElapsed(0);
    setAnalysis(null);
    setDlUrl(null);
    setProgStatus("Connecting to server…");

    const form = new FormData();
    form.append("video",          file);
    form.append("style",          style);
    form.append("options",        JSON.stringify([...opts]));
    form.append("resolution",     resolution);
    form.append("fps",            fps);
    form.append("quality",        quality);
    form.append("custom_prompt",  prompt.trim().slice(0, 400));

    // POST video + stream SSE response back (EventSource can't do POST)
    try {
      const res = await fetch(`${BACKEND}/analyze`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`Server error ${res.status} — check Railway logs`);

      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let   buf    = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          try {
            const raw  = line.slice(5).trim();
            if (!raw)  continue;
            const data = JSON.parse(raw);
            if (data.job_id)              setJobId(data.job_id);
            if (data.progress !== undefined) setProgress(data.progress);
            if (data.status)              setProgStatus(data.status);
            if (data.step !== undefined)  setStep(Math.max(0, data.step));
            if (data.result) {
              setAnalysis(data.result);
              setDlUrl(data.download_url);
              setFileMb(data.file_size_mb || 0);
              setMusicAdded(!!data.music_added);
              setProcessing(false);
            }
            if (data.step === -1) setProcessing(false);
          } catch (_) {}
        }
      }
    } catch (err) {
      setProgStatus(`❌ ${err.message}`);
      setProcessing(false);
    }
  }

  async function handleExport() {
    if (!jobId) return;
    setProcessing(true);
    setProgress(10);
    setProgStatus("Re-encoding with new settings…");

    const form = new FormData();
    form.append("resolution", resolution);
    form.append("fps",        fps);
    form.append("quality",    quality);

    try {
      const res    = await fetch(`${BACKEND}/export/${jobId}`, { method: "POST", body: form });
      const reader = res.body.getReader();
      const dec    = new TextDecoder();
      let   buf    = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (data.progress !== undefined) setProgress(data.progress);
            if (data.status)   setProgStatus(data.status);
            if (data.download_url) {
              setDlUrl(data.download_url);
              setFileMb(data.file_size_mb || 0);
              setProcessing(false);
            }
            if (data.step === -1) setProcessing(false);
          } catch (_) {}
        }
      }
    } catch (err) {
      setProgStatus(`❌ ${err.message}`);
      setProcessing(false);
    }
  }

  const canProcess = !!file && !processing;

  return (
    <div className="app">
      <style>{css}</style>
      <nav className="nav">
        <div className="nav-logo">CLIP<span>MIND</span></div>
        <div className="nav-badges">
          <span className="badge badge-pro">PRO</span>
          <span className="badge badge-ai">GROQ AI</span>
          {serverError
            ? <span className="badge" style={{background:"#3a0a0a",color:"#f87171",border:"1px solid #7f1d1d"}}>⚠️ Server offline</span>
            : serverReady
              ? <span className="badge" style={{background:"#0a2a0a",color:"#4ade80",border:"1px solid #166534"}}>🟢 Ready</span>
              : <span className="badge" style={{background:"#1a1a2a",color:"#94a3b8"}}>⏳ Connecting…</span>
          }
        </div>
      </nav>
      <div className="main">

        {/* ── Left: Style + Options ── */}
        <div className="panel-left">
          <div className="panel-section">
            <div className="panel-label">Game / Style</div>
            <div className="style-grid">
              {STYLES.map(s => (
                <button key={s.id}
                  className={`style-btn ${style === s.id ? "active" : ""}`}
                  onClick={() => setStyle(s.id)}>
                  <span className="emoji">{s.emoji}</span>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <div className="panel-section">
            <div className="panel-label">Edit Options</div>
            {OPTIONS.map(o => (
              <div key={o.id} className="opt-row">
                <span className="opt-name">
                  <span className="opt-icon">{o.icon}</span>
                  {o.label}
                </span>
                <Toggle on={opts.has(o.id)} onChange={() => toggleOpt(o.id)} />
              </div>
            ))}
          </div>

          {/* Custom prompt */}
          <div className="panel-section" style={{ padding: 0 }}>
            <div className="prompt-header" onClick={() => setPromptOpen(o => !o)}>
              <span style={{ fontSize: "0.78rem", fontWeight: 600 }}>✨ Custom AI Prompt</span>
              <span className={`prompt-chevron ${promptOpen ? "open" : ""}`}>▼</span>
            </div>
            {promptOpen && (
              <div className="prompt-body">
                <textarea
                  className="prompt-textarea"
                  placeholder="e.g. Focus on the kill at 0:12, slow-mo before the headshot, title card saying 1v4 CLUTCH…"
                  value={prompt}
                  onChange={e => setPrompt(e.target.value.slice(0, 400))}
                />
                <div className="prompt-meta">
                  <span style={{ color: prompt.length > 360 ? "var(--red)" : undefined }}>
                    {prompt.length} / 400
                  </span>
                  <button className="prompt-clear" onClick={() => setPrompt("")}>Clear</button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Center: Upload + Progress ── */}
        <div className="panel-center">
          {!file ? (
            <div
              className={`upload-zone ${drag ? "drag" : ""}`}
              onClick={() => fileRef.current?.click()}
              onDragOver={e => { e.preventDefault(); setDrag(true); }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}>
              <div className="upload-icon">🎬</div>
              <div className="upload-title">Drop your gaming clip here</div>
              <div className="upload-sub">
                MP4, MOV, AVI, MKV, WebM supported<br />
                Max 500MB recommended
              </div>
              <button className="upload-btn">Choose File</button>
              <input ref={fileRef} type="file" accept="video/*" style={{ display: "none" }}
                onChange={e => e.target.files[0] && loadFile(e.target.files[0])} />
            </div>
          ) : (
            <>
              <div className="file-bar">
                <div className="file-thumb">🎮</div>
                <div className="file-info">
                  <div className="file-name">{file.name}</div>
                  <div className="file-meta">{fmt(file.size)}</div>
                </div>
                <button className="file-remove"
                  onClick={() => { setFile(null); setAnalysis(null); setDlUrl(null); }}>
                  ✕ Remove
                </button>
              </div>

              {processing || progress > 0 ? (
                <div className="progress-card">
                  <div className="progress-header">
                    <span className="progress-title">Processing</span>
                    <span className="progress-time">{fmtTime(elapsed)}</span>
                  </div>
                  <div className="progress-ring-wrap">
                    <ProgressRing pct={progress} />
                  </div>
                  <div style={{ textAlign: "center", marginBottom: "1rem" }}>
                    <div className="progress-pct" style={{ display: "none" }}></div>
                    <div className="progress-status">{progStatus}</div>
                  </div>
                  <div className="steps-list">
                    {STEPS.map((s, i) => (
                      <div key={i} className={`step-item ${i < step ? "done" : i === step ? "active" : ""}`}>
                        <div className={`step-dot ${i < step ? "done" : i === step ? "active" : ""}`} />
                        {s}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ padding: "1.5rem", flex: 1 }}>
                  {analysis && dlUrl ? (
                    <div style={{ textAlign: "center", padding: "2rem" }}>
                      <div style={{ fontSize: "2.5rem", marginBottom: "0.75rem" }}>✅</div>
                      <div style={{ fontSize: "1rem", fontWeight: 700, marginBottom: "0.5rem" }}>
                        Clip Ready!
                      </div>
                      <div style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                        Download from the right panel
                      </div>
                    </div>
                  ) : (
                    <div style={{ textAlign: "center", padding: "2rem", color: "var(--muted)", fontSize: "0.82rem" }}>
                      Configure settings on the left, then hit Process
                    </div>
                  )}
                </div>
              )}

              <div className="analyze-wrap">
                <button
                  className={`analyze-btn ${processing ? "processing" : ""}`}
                  onClick={startProcess}
                  disabled={!canProcess}>
                  {processing ? "⚙️  Processing…" : "🚀  Process Clip"}
                </button>
              </div>
            </>
          )}
        </div>

        {/* ── Right: Export + Results ── */}
        <div className="panel-right">
          <div className="export-section">
            <div className="export-section-label">Resolution</div>
            <div className="btn-grid cols-2">
              {RESOLUTIONS.map(r => (
                <button key={r.id}
                  className={`sel-btn ${resolution === r.id ? "active" : ""}`}
                  onClick={() => setRes(r.id)}
                  title={r.warning || ""}>
                  {r.label}
                  {r.note && <span className="note">{r.note}</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="export-section">
            <div className="export-section-label">Frame Rate</div>
            <div className="btn-grid cols-2">
              {FPS_OPTIONS.map(f => (
                <button key={f}
                  className={`sel-btn ${fps === f ? "active" : ""}`}
                  onClick={() => setFps(f)}>
                  {f} fps
                  {f === 120 && <span className="note">H.264 5.2</span>}
                </button>
              ))}
            </div>
          </div>
          <div className="export-section">
            <div className="export-section-label">Quality</div>
            <div className="btn-grid cols-2">
              {QUALITY_OPTIONS.map(q => (
                <button key={q.id}
                  className={`sel-btn ${quality === q.id ? "active" : ""}`}
                  onClick={() => setQuality(q.id)}>
                  {q.label}
                  {q.note && <span className="note">{q.note}</span>}
                </button>
              ))}
            </div>
          </div>
          <ResultsPanel
            analysis={analysis}
            dlUrl={dlUrl}
            fileMb={fileMb}
            musicAdded={musicAdded}
            onExport={handleExport}
          />
        </div>

      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
