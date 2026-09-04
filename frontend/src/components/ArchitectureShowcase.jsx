import React from "react";
import { Award, GitBranch, Cpu, ShieldCheck, FileCheck, Layers, Terminal, Sparkles } from "lucide-react";

export default function ArchitectureShowcase() {
  return (
    <div style={{ padding: "0 24px 50px", display: "flex", flexDirection: "column", gap: "30px", maxWidth: "1100px", margin: "0 auto" }}>
      
      {/* Title */}
      <div style={{ textAlign: "center" }}>
        <h2 style={{ fontSize: "1.6rem", fontWeight: "700" }} className="gradient-text">
          Agentic AI System Architecture & Career Portfolio Guide
        </h2>
        <p style={{ fontSize: "0.9rem", color: "var(--text-secondary)", maxWidth: "700px", margin: "8px auto 0" }}>
          How this project embodies senior-level Agentic AI architecture, multimodal perception, and deterministic tool orchestration.
        </p>
      </div>

      {/* Architecture Flow Diagram */}
      <div className="glass-panel" style={{ padding: "24px" }}>
        <h3 style={{ fontSize: "1.1rem", fontWeight: "600", marginBottom: "16px", display: "flex", alignItems: "center", gap: "8px" }}>
          <GitBranch size={20} color="var(--accent-cyan)" /> End-to-End Multi-Agent Orchestration Flow
        </h3>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px" }}>
          
          <div style={{ background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "10px", border: "1px solid rgba(99,102,241,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#818cf8", fontWeight: "600", fontSize: "0.85rem", marginBottom: "6px" }}>
              <span style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#6366f1", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem" }}>1</span>
              PerceptionAgent
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              Extracts Shannon entropy, gradient magnitude tensors, alpha distribution, and spatial complexity to classify images into categories.
            </p>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "10px", border: "1px solid rgba(6,182,212,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#67e8f9", fontWeight: "600", fontSize: "0.85rem", marginBottom: "6px" }}>
              <span style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#06b6d4", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem" }}>2</span>
              FormatReasoningAgent
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              Synthesizes Chain-of-Thought (CoT) reasoning to select format (WebP/AVIF/PNG), quality bitrates, chroma subsampling, and upscaling factors.
            </p>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "10px", border: "1px solid rgba(168,85,247,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#c084fc", fontWeight: "600", fontSize: "0.85rem", marginBottom: "6px" }}>
              <span style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#a855f7", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem" }}>3</span>
              TransformAgent
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              Executes high-order Lanczos super-resolution, unsharp masking, alpha matting, and multi-format encoding (WebP, PNG, JPEG, SVG).
            </p>
          </div>

          <div style={{ background: "rgba(0,0,0,0.3)", padding: "16px", borderRadius: "10px", border: "1px solid rgba(16,185,129,0.3)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#34d399", fontWeight: "600", fontSize: "0.85rem", marginBottom: "6px" }}>
              <span style={{ width: "20px", height: "20px", borderRadius: "50%", background: "#10b981", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.7rem" }}>4</span>
              VisionCriticAgent
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: "1.5" }}>
              Audits outputs against ground truth using Peak Signal-to-Noise Ratio (PSNR), SSIM structural index, and Core Web Vitals LCP latency models.
            </p>
          </div>

        </div>
      </div>

      {/* Resume & Portfolio Showcase Section */}
      <div className="glass-panel gradient-border" style={{ padding: "24px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "14px" }}>
          <Award size={24} color="#f59e0b" />
          <h3 style={{ fontSize: "1.2rem", fontWeight: "700", color: "#f8fafc" }}>
            Resume & LinkedIn Talking Points (Agentic AI Engineer)
          </h3>
        </div>

        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "16px" }}>
          You can feature this project prominently on your resume, GitHub, and technical interviews using the battle-tested bullet points below:
        </p>

        <div style={{ display: "flex", flexDirection: "column", gap: "12px", background: "rgba(0,0,0,0.4)", padding: "18px", borderRadius: "10px", border: "1px solid var(--border-subtle)", fontFamily: "var(--font-mono)", fontSize: "0.8rem", color: "#e2e8f0" }}>
          <div>
            <strong style={{ color: "#38bdf8" }}>Bullet Point 1 (Multi-Agent Architecture):</strong><br />
            "Architected <strong>AgenticVision Studio</strong>, an autonomous multi-agent vision system that automates multimodal image triage, format strategy reasoning, and perceptual optimization, delivering <strong>40-65% payload reductions</strong> while preserving <strong>&gt;0.96 SSIM fidelity</strong>."
          </div>
          <div>
            <strong style={{ color: "#a855f7" }}>Bullet Point 2 (Multimodal Perception & Tool Calling):</strong><br />
            "Implemented an autonomous <strong>Perception & Strategy Reasoning Agent</strong> utilizing Shannon entropy calculations, gradient edge tensors, and Chain-of-Thought (CoT) heuristics to dynamically select optimal image codecs (WebP, AVIF, PNG) and compression parameters based on target deployment constraints."
          </div>
          <div>
            <strong style={{ color: "#34d399" }}>Bullet Point 3 (Evaluation & Critic Loop):</strong><br />
            "Developed an automated <strong>Vision Critic Agent</strong> computing mathematical PSNR, Structural Similarity (SSIM), and Core Web Vitals LCP latency models across 3G/4G/5G cellular tiers, providing automated verification and artifact risk auditing."
          </div>
          <div>
            <strong style={{ color: "#f59e0b" }}>Bullet Point 4 (Competitive Intelligence Hub):</strong><br />
            "Built a comprehensive 2026 Competitive Market Intelligence engine synthesizing comparative benchmarks across 7 industry-leading converters with algorithmic recommendation routing and conversational tool orchestration."
          </div>
        </div>
      </div>

    </div>
  );
}
