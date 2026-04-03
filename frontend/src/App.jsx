import { useState } from "react";
import { generatePresentation, pollStatus, downloadUrl } from "./api/narrato";

export default function App() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("idle"); // idle | processing | done | error
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);

  async function handleGenerate() {
    if (!prompt.trim()) return;
    setStatus("processing");
    setError(null);

    try {
      const { job_id } = await generatePresentation(prompt);
      setJobId(job_id);
      await poll(job_id);
    } catch (e) {
      setStatus("error");
      setError("Generation failed. Please try again.");
    }
  }

  async function poll(id) {
    const interval = setInterval(async () => {
      const data = await pollStatus(id);
      if (data.status === "completed") {
        clearInterval(interval);
        setStatus("done");
      } else if (data.status === "failed") {
        clearInterval(interval);
        setStatus("error");
        setError(data.error);
      }
    }, 2000);
  }

  return (
    <div style={{ maxWidth: 640, margin: "80px auto", fontFamily: "sans-serif" }}>
      <h1>Narrato</h1>
      <p>Describe your presentation and we'll build it.</p>

      <textarea
        rows={4} style={{ width: "100%", fontSize: 16, padding: 12 }}
        placeholder="e.g. 12-slide pitch deck for an AI healthcare startup targeting hospital CTOs"
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
      />

      <button
        onClick={handleGenerate}
        disabled={status === "processing"}
        style={{ marginTop: 12, padding: "10px 24px", fontSize: 16, cursor: "pointer" }}
      >
        {status === "processing" ? "Generating..." : "Generate Presentation"}
      </button>

      {status === "processing" && <p>⏳ Building your deck... this takes ~30 seconds</p>}

      {status === "done" && (
        <a href={downloadUrl(jobId)} download>
          <button style={{ marginTop: 16, padding: "10px 24px", background: "#6C63FF", color: "#fff", border: "none", cursor: "pointer", fontSize: 16 }}>
            ⬇ Download .pptx
          </button>
        </a>
      )}

      {status === "error" && <p style={{ color: "red" }}>❌ {error}</p>}
    </div>
  );
}