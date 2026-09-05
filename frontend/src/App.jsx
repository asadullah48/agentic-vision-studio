import React, { useState, useEffect, useCallback } from "react";
import Navbar from "./components/Navbar";
import StudioView from "./components/StudioView";
import AgentChat from "./components/AgentChat";
import MarketIntelView from "./components/MarketIntelView";
import ArchitectureShowcase from "./components/ArchitectureShowcase";

/**
 * The API is stateless: the server never holds an uploaded image between
 * requests. The browser therefore keeps the File object and sends it with each
 * call, and the converted result arrives inline as a data URI.
 *
 * That is what lets the same build run against a serverless deployment, where
 * a follow-up request is not guaranteed to reach the instance that handled the
 * upload.
 */
async function postForm(path, formData) {
  const response = await fetch(path, { method: "POST", body: formData });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) {
        detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
      }
    } catch {
      /* Response had no JSON body; keep the status-based message. */
    }
    throw new Error(detail);
  }
  return response.json();
}

export default function App() {
  const [activeTab, setActiveTab] = useState("studio");
  const [activeImage, setActiveImage] = useState(null);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState(null);

  // Object URLs are held by the browser until explicitly released.
  useEffect(() => {
    return () => {
      if (activeImage?.previewUrl) URL.revokeObjectURL(activeImage.previewUrl);
    };
  }, [activeImage]);

  const runPipeline = useCallback(async (file, params = {}) => {
    if (!file) return;
    setIsProcessing(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("intent", params.intent || "auto");
      if (params.targetFormat && params.targetFormat !== "AUTO") {
        form.append("target_format", params.targetFormat);
      }
      if (params.quality) form.append("quality", String(params.quality));
      if (params.targetSizeKb) form.append("target_size_kb", String(params.targetSizeKb));
      form.append("upscale", String(params.upscale || 1));
      form.append("remove_bg", params.removeBg ? "true" : "false");
      form.append("sharpen", params.sharpen ? "true" : "false");
      form.append("normalize_contrast", params.normalizeContrast ? "true" : "false");

      setPipelineResult(await postForm("/api/pipeline", form));
    } catch (err) {
      setError(err.message);
      setPipelineResult(null);
    } finally {
      setIsProcessing(false);
    }
  }, []);

  const handleUploadComplete = useCallback(
    async (file) => {
      if (!file) return;
      setError(null);
      setPipelineResult(null);
      setIsProcessing(true);

      // Show the image and its measurements immediately, before the user has
      // picked any settings, then convert with the agent's own defaults.
      const previewUrl = URL.createObjectURL(file);
      try {
        const form = new FormData();
        form.append("file", file);
        const perception = await postForm("/api/analyze", form);

        setActiveImage({ file, filename: file.name, previewUrl, perception });
        await runPipeline(file, { intent: "auto" });
      } catch (err) {
        URL.revokeObjectURL(previewUrl);
        setActiveImage(null);
        setError(err.message);
        setIsProcessing(false);
      }
    },
    [runPipeline]
  );

  const handleRunPipeline = useCallback(
    (params) => runPipeline(activeImage?.file, params),
    [activeImage, runPipeline]
  );

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {error && (
        <div
          role="alert"
          style={{
            margin: "12px 24px 0",
            padding: "12px 16px",
            borderRadius: 8,
            border: "1px solid rgba(248, 113, 113, 0.4)",
            background: "rgba(248, 113, 113, 0.12)",
            color: "#fca5a5",
            fontSize: "0.85rem",
            display: "flex",
            justifyContent: "space-between",
            gap: 16,
          }}
        >
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            aria-label="Dismiss error"
            style={{ background: "none", border: "none", color: "inherit", cursor: "pointer" }}
          >
            ✕
          </button>
        </div>
      )}

      <main style={{ flex: 1 }}>
        {activeTab === "studio" && (
          <StudioView
            activeImage={activeImage}
            onUploadComplete={handleUploadComplete}
            pipelineResult={pipelineResult}
            isProcessing={isProcessing}
            onRunPipeline={handleRunPipeline}
          />
        )}

        {activeTab === "chat" && (
          <AgentChat
            activeImage={activeImage}
            onPipelineUpdate={(res) => setPipelineResult(res)}
          />
        )}

        {activeTab === "market" && <MarketIntelView />}

        {activeTab === "architecture" && <ArchitectureShowcase />}
      </main>

      <footer
        style={{
          borderTop: "1px solid var(--border-subtle)",
          padding: "16px 24px",
          textAlign: "center",
          fontSize: "0.75rem",
          color: "var(--text-muted)",
        }}
      >
        AgenticVision Studio — a multi-agent image optimisation pipeline that measures, plans,
        encodes and audits its own output · FastAPI + React
      </footer>
    </div>
  );
}
