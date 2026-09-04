import React, { useState } from "react";
import { UploadCloud, Wand2, Sliders, Play, RefreshCw, Check, Image as ImageIcon } from "lucide-react";
import BeforeAfterSlider from "./BeforeAfterSlider";
import PerceptionHUD from "./PerceptionHUD";
import ReasoningTerminal from "./ReasoningTerminal";

export default function StudioView({ onUploadComplete, activeImage, pipelineResult, isProcessing, onRunPipeline }) {
  const [mode, setMode] = useState("auto"); // "auto" or "custom"
  const [intent, setIntent] = useState("auto");
  const [targetFormat, setTargetFormat] = useState("WEBP");
  const [quality, setQuality] = useState(82);
  const [upscale, setUpscale] = useState(1);
  const [removeBg, setRemoveBg] = useState(false);
  const [sharpen, setSharpen] = useState(true);
  const [normalizeContrast, setNormalizeContrast] = useState(false);

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    onUploadComplete(file);
  };

  const handleExecute = () => {
    if (!activeImage) return;
    onRunPipeline({
      filename: activeImage.filename,
      intent: mode === "auto" ? intent : "custom",
      targetFormat: mode === "custom" ? targetFormat : "AUTO",
      quality: mode === "custom" ? quality : null,
      upscale,
      removeBg,
      sharpen,
      normalizeContrast
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px", padding: "0 24px 40px" }}>
      
      {/* Top Banner / Upload Zone */}
      {!activeImage && (
        <div
          className="glass-panel gradient-border"
          style={{
            padding: "50px 30px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "16px",
            borderStyle: "dashed",
            borderColor: "rgba(99,102,241,0.4)"
          }}
        >
          <div style={{
            width: "64px",
            height: "64px",
            borderRadius: "16px",
            background: "rgba(99,102,241,0.15)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 25px rgba(99,102,241,0.3)"
          }}>
            <UploadCloud size={32} color="#818cf8" />
          </div>
          <div>
            <h2 style={{ fontSize: "1.4rem", fontWeight: "700", marginBottom: "6px" }}>
              Upload Image for Autonomous Vision Pipeline
            </h2>
            <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", maxWidth: "550px", margin: "0 auto" }}>
              Supports JPG, PNG, WebP, TIFF, BMP, and GIF. The Multi-Agent engine automatically conducts entropy triage, format strategy reasoning, and perceptual quality audits.
            </p>
          </div>
          <label style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 28px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
            color: "#ffffff",
            fontWeight: "600",
            fontSize: "0.95rem",
            cursor: "pointer",
            boxShadow: "0 4px 15px rgba(79,70,229,0.4)"
          }}>
            <ImageIcon size={18} /> Select Image from Device
            <input type="file" accept="image/*" onChange={handleFileChange} style={{ display: "none" }} />
          </label>
        </div>
      )}

      {/* Main Studio Working Area */}
      {activeImage && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "24px", alignItems: "start" }}>
          
          {/* Left Column: Visual Diff & Metrics */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            
            <BeforeAfterSlider
              originalUrl={activeImage.uploadUrl}
              convertedUrl={pipelineResult ? `/static/outputs/${pipelineResult.transformation.output_filename}` : activeImage.uploadUrl}
              originalInfo={{
                format: activeImage.perception?.original_format,
                sizeKb: activeImage.perception?.file_size_kb
              }}
              convertedInfo={{
                filename: pipelineResult?.transformation?.output_filename,
                format: pipelineResult?.transformation?.output_format,
                sizeKb: pipelineResult?.transformation?.output_size_kb
              }}
            />

            <PerceptionHUD
              perception={activeImage.perception}
              audit={pipelineResult?.audit}
            />

            <ReasoningTerminal
              chainOfThought={pipelineResult?.strategy?.chain_of_thought}
              verdict={pipelineResult?.audit?.critic_verdict}
            />

          </div>

          {/* Right Column: Agent Configuration Controls */}
          <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "20px" }}>
            
            {/* Mode Switcher */}
            <div>
              <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600", display: "block", marginBottom: "8px" }}>
                Operation Mode
              </label>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px", background: "rgba(0,0,0,0.3)", padding: "4px", borderRadius: "8px" }}>
                <button
                  onClick={() => setMode("auto")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    padding: "8px",
                    borderRadius: "6px",
                    border: "none",
                    fontSize: "0.8rem",
                    fontWeight: mode === "auto" ? "600" : "400",
                    background: mode === "auto" ? "#6366f1" : "transparent",
                    color: "#ffffff"
                  }}
                >
                  <Wand2 size={14} /> Agent Auto-Pilot
                </button>
                <button
                  onClick={() => setMode("custom")}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "6px",
                    padding: "8px",
                    borderRadius: "6px",
                    border: "none",
                    fontSize: "0.8rem",
                    fontWeight: mode === "custom" ? "600" : "400",
                    background: mode === "custom" ? "#6366f1" : "transparent",
                    color: "#ffffff"
                  }}
                >
                  <Sliders size={14} /> Custom Controls
                </button>
              </div>
            </div>

            {/* Auto-Pilot Intent Selector */}
            {mode === "auto" && (
              <div>
                <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600", display: "block", marginBottom: "8px" }}>
                  Optimization Intent
                </label>
                <select
                  value={intent}
                  onChange={(e) => setIntent(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px",
                    borderRadius: "8px",
                    background: "rgba(0,0,0,0.4)",
                    border: "1px solid var(--border-subtle)",
                    color: "#f8fafc",
                    fontSize: "0.85rem"
                  }}
                >
                  <option value="auto">Auto-Detect from Image Entropy</option>
                  <option value="web_speed">Web Performance (Core Web Vitals LCP)</option>
                  <option value="e_commerce">E-Commerce (High-DPI Texture Retention)</option>
                  <option value="ultra_compact_mobile">Ultra-Compact Mobile (Max Compression)</option>
                  <option value="print_ready">Print & Graphic Archival (Lossless)</option>
                </select>
                <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "6px" }}>
                  The Reasoner Agent will autonomously pick format, quality, and chroma parameters based on this intent.
                </p>
              </div>
            )}

            {/* Custom Mode Format & Quality */}
            {mode === "custom" && (
              <>
                <div>
                  <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600", display: "block", marginBottom: "8px" }}>
                    Target Format
                  </label>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px" }}>
                    {["WEBP", "PNG", "JPEG", "AVIF", "SVG", "TIFF"].map((fmt) => (
                      <button
                        key={fmt}
                        onClick={() => setTargetFormat(fmt)}
                        style={{
                          padding: "8px",
                          borderRadius: "6px",
                          border: targetFormat === fmt ? "1px solid #6366f1" : "1px solid var(--border-subtle)",
                          background: targetFormat === fmt ? "rgba(99,102,241,0.25)" : "rgba(0,0,0,0.3)",
                          color: targetFormat === fmt ? "#a5b4fc" : "var(--text-secondary)",
                          fontSize: "0.8rem",
                          fontWeight: "600"
                        }}
                      >
                        {fmt}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                    <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600" }}>
                      Quality Threshold
                    </label>
                    <span style={{ fontSize: "0.8rem", color: "#6366f1", fontWeight: "700" }}>{quality}%</span>
                  </div>
                  <input
                    type="range"
                    min="20"
                    max="100"
                    value={quality}
                    onChange={(e) => setQuality(parseInt(e.target.value))}
                    style={{ width: "100%", accentColor: "#6366f1" }}
                  />
                </div>
              </>
            )}

            {/* Companion AI Enhancements */}
            <div>
              <label style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", fontWeight: "600", display: "block", marginBottom: "10px" }}>
                AI Companion Features
              </label>
              <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                
                {/* Super-Resolution Upscale */}
                <div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "4px" }}>
                    AI Super-Resolution Upscaling
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "6px" }}>
                    {[1, 2, 4].map((f) => (
                      <button
                        key={f}
                        onClick={() => setUpscale(f)}
                        style={{
                          padding: "6px",
                          borderRadius: "6px",
                          border: upscale === f ? "1px solid #06b6d4" : "1px solid var(--border-subtle)",
                          background: upscale === f ? "rgba(6,182,212,0.25)" : "rgba(0,0,0,0.3)",
                          color: upscale === f ? "#67e8f9" : "var(--text-secondary)",
                          fontSize: "0.75rem",
                          fontWeight: "600"
                        }}
                      >
                        {f === 1 ? "1x (Native)" : `${f}x Lanczos`}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Background Isolation Toggle */}
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.8rem", color: "#cbd5e1", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={removeBg}
                    onChange={(e) => setRemoveBg(e.target.checked)}
                    style={{ accentColor: "#6366f1" }}
                  />
                  <span>AI Background Isolation & Alpha Matte</span>
                </label>

                {/* Perceptual Sharpening Toggle */}
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.8rem", color: "#cbd5e1", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={sharpen}
                    onChange={(e) => setSharpen(e.target.checked)}
                    style={{ accentColor: "#6366f1" }}
                  />
                  <span>Perceptual Edge Sharpening</span>
                </label>

                {/* Dynamic Range Autocontrast */}
                <label style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.8rem", color: "#cbd5e1", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={normalizeContrast}
                    onChange={(e) => setNormalizeContrast(e.target.checked)}
                    style={{ accentColor: "#6366f1" }}
                  />
                  <span>Dynamic Range Autocontrast</span>
                </label>

              </div>
            </div>

            {/* Execute Button */}
            <button
              onClick={handleExecute}
              disabled={isProcessing}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "14px",
                borderRadius: "10px",
                background: isProcessing ? "#374151" : "linear-gradient(135deg, #4f46e5, #7c3aed)",
                color: "#ffffff",
                border: "none",
                fontWeight: "700",
                fontSize: "0.95rem",
                boxShadow: "0 4px 18px rgba(79,70,229,0.5)",
                marginTop: "10px"
              }}
            >
              {isProcessing ? (
                <>
                  <RefreshCw size={18} className="animate-spin" />
                  Agents Orchestrating...
                </>
              ) : (
                <>
                  <Play size={18} />
                  Execute Multi-Agent Pipeline
                </>
              )}
            </button>

            {/* Change image */}
            <label style={{
              display: "block",
              textAlign: "center",
              fontSize: "0.75rem",
              color: "var(--text-muted)",
              cursor: "pointer",
              textDecoration: "underline"
            }}>
              Upload Different Image
              <input type="file" accept="image/*" onChange={handleFileChange} style={{ display: "none" }} />
            </label>

          </div>

        </div>
      )}

    </div>
  );
}
