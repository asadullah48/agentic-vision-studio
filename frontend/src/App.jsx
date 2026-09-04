import React, { useState, useEffect } from "react";
import Navbar from "./components/Navbar";
import StudioView from "./components/StudioView";
import AgentChat from "./components/AgentChat";
import MarketIntelView from "./components/MarketIntelView";
import ArchitectureShowcase from "./components/ArchitectureShowcase";

export default function App() {
  const [activeTab, setActiveTab] = useState("studio");
  const [activeImage, setActiveImage] = useState(null);
  const [pipelineResult, setPipelineResult] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Handle image upload
  const handleUploadComplete = async (file) => {
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      
      const newImg = {
        filename: data.filename,
        uploadUrl: data.upload_path,
        perception: data.perception
      };
      setActiveImage(newImg);

      // Automatically execute pipeline in auto mode
      handleRunPipeline({
        filename: data.filename,
        intent: "auto",
        targetFormat: "AUTO",
        upscale: 1,
        removeBg: false,
        sharpen: true
      });
    } catch (err) {
      console.error("Upload error", err);
    }
  };

  // Run pipeline
  const handleRunPipeline = async (params) => {
    setIsProcessing(true);
    try {
      const formData = new FormData();
      formData.append("filename", params.filename);
      formData.append("intent", params.intent || "auto");
      if (params.targetFormat) formData.append("target_format", params.targetFormat);
      if (params.quality) formData.append("quality", params.quality);
      formData.append("upscale", params.upscale || 1);
      formData.append("remove_bg", params.removeBg ? "true" : "false");
      formData.append("sharpen", params.sharpen ? "true" : "false");
      formData.append("normalize_contrast", params.normalizeContrast ? "true" : "false");

      const res = await fetch("/api/pipeline", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      setPipelineResult(data);
    } catch (err) {
      console.error("Pipeline execution error", err);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      
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

        {activeTab === "market" && (
          <MarketIntelView />
        )}

        {activeTab === "architecture" && (
          <ArchitectureShowcase />
        )}
      </main>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid var(--border-subtle)", padding: "16px 24px", textAlign: "center", fontSize: "0.75rem", color: "var(--text-muted)" }}>
        AgenticVision Studio | Autonomous Multi-Agent Multimodal Vision & Optimization Engine | Python 3.14 + React 18 + Vite
      </footer>
    </div>
  );
}
