import React from "react";
import { Terminal, CheckCircle2, Copy } from "lucide-react";

export default function ReasoningTerminal({ chainOfThought, verdict }) {
  const steps = chainOfThought || [
    "[Step 1: Ingest Telemetry] Multi-agent perception engine awaiting image dispatch.",
    "[Step 2: Category Assessment] Ready to calculate Shannon entropy and gradient tensor.",
    "[Step 3: Format Strategy] Ready to optimize target bitrate vs perceptual quality."
  ];

  const handleCopy = () => {
    navigator.clipboard.writeText(steps.join("\n"));
  };

  return (
    <div className="glass-panel" style={{ padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border-subtle)", paddingBottom: "10px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Terminal size={16} color="var(--accent-indigo)" />
          <span style={{ fontSize: "0.85rem", fontWeight: "600", color: "#f8fafc" }}>
            Agent Chain-of-Thought (CoT) Reasoning Engine
          </span>
        </div>
        <button
          onClick={handleCopy}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            background: "transparent",
            border: "1px solid var(--border-subtle)",
            color: "var(--text-secondary)",
            padding: "4px 8px",
            borderRadius: "6px",
            fontSize: "0.7rem"
          }}
        >
          <Copy size={12} /> Copy CoT
        </button>
      </div>

      {/* Terminal log output */}
      <div style={{
        fontFamily: "var(--font-mono)",
        fontSize: "0.8rem",
        lineHeight: "1.7",
        background: "#05070c",
        padding: "14px",
        borderRadius: "8px",
        border: "1px solid rgba(255,255,255,0.05)",
        maxHeight: "220px",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: "6px"
      }}>
        {steps.map((step, idx) => (
          <div key={idx} style={{ display: "flex", gap: "8px", alignItems: "flex-start" }}>
            <span style={{ color: "#6366f1", flexShrink: 0 }}>&gt;</span>
            <span style={{ color: step.includes("Conclusion") || step.includes("Approved") ? "#34d399" : "#cbd5e1" }}>
              {step}
            </span>
          </div>
        ))}
        <div style={{ display: "flex", gap: "8px", alignItems: "center", color: "#6366f1" }}>
          <span>&gt;</span>
          <span className="terminal-blink" style={{ width: "8px", height: "14px", background: "#6366f1", display: "inline-block" }}></span>
        </div>
      </div>

      {/* Critic Verdict badge */}
      {verdict && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "10px 14px",
          borderRadius: "8px",
          background: "rgba(16,185,129,0.1)",
          border: "1px solid rgba(16,185,129,0.3)"
        }}>
          <CheckCircle2 size={18} color="#34d399" />
          <span style={{ fontSize: "0.8rem", color: "#a7f3d0", fontWeight: "500" }}>
            {verdict}
          </span>
        </div>
      )}
    </div>
  );
}
