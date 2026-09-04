import React from "react";
import { Sparkles, Cpu, Eye, BarChart3, MessageSquare, Terminal, Award } from "lucide-react";

export default function Navbar({ activeTab, setActiveTab }) {
  const tabs = [
    { id: "studio", label: "Agentic Studio", icon: Sparkles },
    { id: "chat", label: "Agent Chat", icon: MessageSquare },
    { id: "market", label: "2026 Market Intelligence", icon: BarChart3 },
    { id: "architecture", label: "Agent Architecture & Career", icon: Award }
  ];

  return (
    <header className="glass-panel" style={{ margin: "16px 24px", padding: "12px 24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "16px" }}>
        
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            width: "40px",
            height: "40px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #6366f1, #06b6d4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 0 15px rgba(99,102,241,0.5)"
          }}>
            <Cpu size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <h1 style={{ fontSize: "1.25rem", fontWeight: "700", letterSpacing: "-0.02em" }} className="gradient-text">
                AgenticVision Studio
              </h1>
              <span style={{
                fontSize: "0.7rem",
                padding: "2px 8px",
                borderRadius: "999px",
                background: "rgba(99,102,241,0.15)",
                color: "#a5b4fc",
                border: "1px solid rgba(99,102,241,0.3)",
                fontWeight: "600"
              }}>
                v2026.1
              </span>
            </div>
            <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", margin: 0 }}>
              Autonomous Multi-Agent Multimodal Vision & Optimization Engine
            </p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: "flex", alignItems: "center", gap: "6px", background: "rgba(0,0,0,0.3)", padding: "4px", borderRadius: "10px", border: "1px solid var(--border-subtle)" }}>
          {tabs.map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "8px 16px",
                  borderRadius: "8px",
                  border: "none",
                  fontSize: "0.85rem",
                  fontWeight: isActive ? "600" : "500",
                  color: isActive ? "#ffffff" : "var(--text-secondary)",
                  background: isActive ? "linear-gradient(135deg, #4f46e5, #6366f1)" : "transparent",
                  boxShadow: isActive ? "0 2px 10px rgba(79,70,229,0.4)" : "none",
                  transition: "all 0.2s ease"
                }}
              >
                <Icon size={16} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Status indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
          <span style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background: "#10b981",
            boxShadow: "0 0 8px #10b981"
          }} />
          <span>Vision Agents: <strong style={{ color: "#34d399" }}>ACTIVE</strong></span>
        </div>

      </div>
    </header>
  );
}
