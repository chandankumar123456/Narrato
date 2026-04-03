import { useState, useRef, useCallback } from "react";
import { generatePresentation, pollStatus, downloadUrl, requestPreview, previewImageUrl } from "./api/narrato";

const TONES = ["professional", "casual", "inspiring", "academic"];
const STYLES = ["modern", "corporate", "minimal"];

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("idle"); // idle | processing | done | error
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [previewUrls, setPreviewUrls] = useState([]);
  const [showOptions, setShowOptions] = useState(false);
  const [options, setOptions] = useState({
    slide_count: 10,
    tone: "professional",
    visual_style: "modern",
    image_preference: true,
  });
  const intervalRef = useRef(null);

  const updateOption = useCallback((key, value) => {
    setOptions(prev => ({ ...prev, [key]: value }));
  }, []);

  async function handleGenerate() {
    if (!prompt.trim()) return;
    setStatus("processing");
    setError(null);
    setProgress(0);
    setPreviewUrls([]);

    try {
      const { job_id } = await generatePresentation(prompt, options);
      setJobId(job_id);
      poll(job_id);
    } catch (e) {
      setStatus("error");
      setError("Generation failed. Please try again.");
    }
  }

  function poll(id) {
    if (intervalRef.current) clearInterval(intervalRef.current);
    intervalRef.current = setInterval(async () => {
      try {
        const data = await pollStatus(id);
        setProgress(data.progress || 0);
        if (data.status === "completed") {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setStatus("done");
          setProgress(100);
          if (data.preview_urls && data.preview_urls.length > 0) {
            setPreviewUrls(data.preview_urls);
          } else {
            // Request preview generation
            try { await requestPreview(id); } catch (_) { /* optional */ }
            // Poll a few more times for previews
            pollForPreviews(id);
          }
        } else if (data.status === "failed") {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
          setStatus("error");
          setError(data.error || "Generation failed.");
        }
      } catch (_) { /* network hiccup, keep polling */ }
    }, 2000);
  }

  function pollForPreviews(id) {
    let attempts = 0;
    const previewInterval = setInterval(async () => {
      attempts++;
      try {
        const data = await pollStatus(id);
        if (data.preview_urls && data.preview_urls.length > 0) {
          setPreviewUrls(data.preview_urls);
          clearInterval(previewInterval);
        }
      } catch (_) { /* ignore */ }
      if (attempts > 10) clearInterval(previewInterval);
    }, 3000);
  }

  function handleReset() {
    setStatus("idle");
    setJobId(null);
    setError(null);
    setProgress(0);
    setPreviewUrls([]);
    setPrompt("");
  }

  return (
    <div style={{ maxWidth: 720, margin: "40px auto", padding: "0 20px", fontFamily: "'Segoe UI', system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 32 }}>
        <h1 style={{ fontSize: 48, margin: "20px 0 8px", color: "#6C63FF", letterSpacing: "-1px" }}>
          ✦ Narrato
        </h1>
        <p style={{ fontSize: 18, color: "#666", margin: 0 }}>
          AI-powered storytelling presentation engine
        </p>
      </div>

      {/* Input Section */}
      <div style={{ background: "#f8f9fa", borderRadius: 12, padding: 24, marginBottom: 20, border: "1px solid #e5e5e5" }}>
        <label style={{ fontWeight: 600, fontSize: 14, color: "#333", display: "block", marginBottom: 8 }}>
          Describe your presentation
        </label>
        <textarea
          rows={4}
          style={{
            width: "100%", fontSize: 16, padding: 14, borderRadius: 8,
            border: "1px solid #ddd", resize: "vertical", boxSizing: "border-box",
            fontFamily: "inherit", lineHeight: 1.5,
          }}
          placeholder="e.g. 12-slide pitch deck for an AI healthcare startup targeting hospital CTOs"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          disabled={status === "processing"}
        />

        {/* Options toggle */}
        <button
          onClick={() => setShowOptions(!showOptions)}
          style={{
            marginTop: 8, background: "none", border: "none", color: "#6C63FF",
            cursor: "pointer", fontSize: 14, padding: 0, fontWeight: 500,
          }}
        >
          {showOptions ? "▾ Hide options" : "▸ Show options"}
        </button>

        {/* Options Panel */}
        {showOptions && (
          <div style={{
            marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr",
            gap: 12, padding: 16, background: "#fff", borderRadius: 8, border: "1px solid #eee",
          }}>
            <div>
              <label style={labelStyle}>Slide Count</label>
              <input
                type="range" min={5} max={30} value={options.slide_count}
                onChange={e => updateOption("slide_count", parseInt(e.target.value))}
                style={{ width: "100%" }}
              />
              <span style={{ fontSize: 13, color: "#666" }}>{options.slide_count} slides</span>
            </div>
            <div>
              <label style={labelStyle}>Tone</label>
              <select
                value={options.tone}
                onChange={e => updateOption("tone", e.target.value)}
                style={selectStyle}
              >
                {TONES.map(t => <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Visual Style</label>
              <select
                value={options.visual_style}
                onChange={e => updateOption("visual_style", e.target.value)}
                style={selectStyle}
              >
                {STYLES.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
              </select>
            </div>
            <div>
              <label style={labelStyle}>Include Images</label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 14 }}>
                <input
                  type="checkbox" checked={options.image_preference}
                  onChange={e => updateOption("image_preference", e.target.checked)}
                />
                Fetch relevant images
              </label>
            </div>
          </div>
        )}

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={status === "processing" || !prompt.trim()}
          style={{
            marginTop: 16, padding: "12px 32px", fontSize: 16, cursor: "pointer",
            background: status === "processing" ? "#999" : "#6C63FF",
            color: "#fff", border: "none", borderRadius: 8, fontWeight: 600,
            width: "100%", transition: "background 0.2s",
          }}
        >
          {status === "processing" ? "⏳ Generating..." : "✦ Generate Presentation"}
        </button>
      </div>

      {/* Progress Bar */}
      {status === "processing" && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, color: "#666", marginBottom: 6 }}>
            <span>Building your deck...</span>
            <span>{progress}%</span>
          </div>
          <div style={{ background: "#e5e5e5", borderRadius: 8, height: 8, overflow: "hidden" }}>
            <div style={{
              background: "linear-gradient(90deg, #6C63FF, #A29BFE)",
              height: "100%", borderRadius: 8,
              width: `${Math.max(progress, 5)}%`,
              transition: "width 0.5s ease",
            }} />
          </div>
          <p style={{ fontSize: 13, color: "#999", marginTop: 6 }}>
            This typically takes 20–40 seconds depending on slide count.
          </p>
        </div>
      )}

      {/* Completed: Download + Preview */}
      {status === "done" && (
        <div style={{ marginBottom: 20 }}>
          <div style={{
            display: "flex", gap: 12, alignItems: "center",
            padding: 16, background: "#f0fdf4", borderRadius: 8, border: "1px solid #bbf7d0",
            marginBottom: 16,
          }}>
            <span style={{ fontSize: 24 }}>✅</span>
            <div style={{ flex: 1 }}>
              <strong style={{ color: "#166534" }}>Presentation ready!</strong>
              <p style={{ margin: 0, fontSize: 13, color: "#15803d" }}>Your deck has been generated successfully.</p>
            </div>
            <a href={downloadUrl(jobId)} download style={{ textDecoration: "none" }}>
              <button style={{
                padding: "10px 24px", background: "#6C63FF", color: "#fff",
                border: "none", cursor: "pointer", fontSize: 15, borderRadius: 8, fontWeight: 600,
              }}>
                ⬇ Download .pptx
              </button>
            </a>
          </div>

          {/* Preview Thumbnails */}
          {previewUrls.length > 0 && (
            <div>
              <h3 style={{ fontSize: 16, color: "#333", marginBottom: 12 }}>📑 Slide Preview</h3>
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
                gap: 12,
              }}>
                {previewUrls.map((url, i) => (
                  <div key={i} style={{
                    border: "1px solid #e5e5e5", borderRadius: 8, overflow: "hidden",
                    background: "#fff", boxShadow: "0 1px 3px rgba(0,0,0,0.08)",
                  }}>
                    <img
                      src={previewImageUrl(url)} alt={`Slide ${i + 1}`}
                      style={{ width: "100%", display: "block" }}
                    />
                    <div style={{ padding: "4px 8px", fontSize: 12, color: "#666", textAlign: "center" }}>
                      Slide {i + 1}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button
            onClick={handleReset}
            style={{
              marginTop: 16, padding: "10px 24px", background: "transparent",
              border: "1px solid #ddd", borderRadius: 8, cursor: "pointer",
              fontSize: 14, color: "#666",
            }}
          >
            ← Create another presentation
          </button>
        </div>
      )}

      {/* Error State */}
      {status === "error" && (
        <div style={{
          padding: 16, background: "#fef2f2", borderRadius: 8, border: "1px solid #fecaca",
          marginBottom: 20,
        }}>
          <p style={{ color: "#dc2626", margin: 0, fontWeight: 500 }}>❌ {error}</p>
          <button
            onClick={handleReset}
            style={{
              marginTop: 10, padding: "8px 16px", background: "#dc2626",
              color: "#fff", border: "none", borderRadius: 6, cursor: "pointer", fontSize: 14,
            }}
          >
            Try Again
          </button>
        </div>
      )}
    </div>
  );
}

const labelStyle = { fontWeight: 600, fontSize: 13, color: "#555", display: "block", marginBottom: 4 };
const selectStyle = {
  width: "100%", padding: "8px 10px", borderRadius: 6, border: "1px solid #ddd",
  fontSize: 14, fontFamily: "inherit",
};