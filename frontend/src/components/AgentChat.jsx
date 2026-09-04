import React, { useState } from "react";
import { Send, Bot, User, Sparkles, Image, CheckCircle, ArrowRight } from "lucide-react";

export default function AgentChat({ activeImage, onPipelineUpdate }) {
  const [messages, setMessages] = useState([
    {
      role: "assistant",
      text: "Hello! I am your Autonomous Multimodal Vision Agent. You can give me instructions like: 'Convert to WebP under 100KB for web banner', 'Upscale 2x and isolate background', or 'Compare lossless compression tradeoffs'. How can I optimize your visuals today?"
    }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const presets = [
    "Convert to WebP under 120KB for high-speed mobile web",
    "Apply 2x AI super-resolution and sharpen micro-edges",
    "Isolate background and generate transparent asset",
    "Optimize for e-commerce catalog with pristine textures"
  ];

  const handleSend = async (textToSend) => {
    const userMsg = textToSend || input;
    if (!userMsg.trim()) return;

    const newMsgs = [...messages, { role: "user", text: userMsg }];
    setMessages(newMsgs);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: userMsg,
          active_image_filename: activeImage?.filename
        })
      });
      const data = await res.json();

      setMessages([
        ...newMsgs,
        {
          role: "assistant",
          text: data.reply_text,
          action: data.action_taken,
          pipelineResult: data.pipeline_result
        }
      ]);

      if (data.pipeline_result && onPipelineUpdate) {
        onPipelineUpdate(data.pipeline_result);
      }
    } catch (err) {
      setMessages([
        ...newMsgs,
        {
          role: "assistant",
          text: "I encountered an issue connecting to the backend agent server. Please ensure FastAPI is running."
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: "0 24px 40px", maxWidth: "1000px", margin: "0 auto", display: "flex", flexDirection: "column", gap: "20px" }}>
      
      {/* Active Image Banner */}
      <div className="glass-panel" style={{ padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <Image size={18} color="var(--accent-cyan)" />
          <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Active Image Context:</span>
          <strong style={{ fontSize: "0.85rem", color: "#f8fafc" }}>
            {activeImage ? `${activeImage.filename} (${activeImage.perception?.width}x${activeImage.perception?.height})` : "None selected (Please upload in Studio for direct execution)"}
          </strong>
        </div>
      </div>

      {/* Chat Messages Log */}
      <div className="glass-panel" style={{ minHeight: "450px", maxHeight: "550px", overflowY: "auto", padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
        {messages.map((m, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: "12px",
              alignItems: "flex-start",
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%"
            }}
          >
            {m.role === "assistant" && (
              <div style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #6366f1, #06b6d4)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0
              }}>
                <Bot size={18} color="#ffffff" />
              </div>
            )}
            
            <div style={{
              padding: "12px 16px",
              borderRadius: "10px",
              background: m.role === "user" ? "linear-gradient(135deg, #4f46e5, #6366f1)" : "rgba(22, 28, 40, 0.85)",
              border: "1px solid " + (m.role === "user" ? "rgba(99,102,241,0.4)" : "var(--border-subtle)"),
              color: "#f8fafc",
              fontSize: "0.88rem",
              lineHeight: "1.6",
              whiteSpace: "pre-line"
            }}>
              {m.text}

              {/* Action pill */}
              {m.action && (
                <div style={{ marginTop: "10px", display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", color: "#34d399" }}>
                  <CheckCircle size={14} /> Action: <strong>{m.action}</strong>
                </div>
              )}
            </div>

            {m.role === "user" && (
              <div style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "#334155",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0
              }}>
                <User size={18} color="#ffffff" />
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", gap: "12px", alignItems: "center", color: "var(--text-muted)", fontSize: "0.85rem" }}>
            <Sparkles size={16} className="animate-spin" color="#6366f1" />
            Agent reasoning through multimodal pipeline...
          </div>
        )}
      </div>

      {/* Quick Prompt Presets */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
        {presets.map((p, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(p)}
            style={{
              padding: "6px 12px",
              borderRadius: "999px",
              background: "rgba(99,102,241,0.1)",
              border: "1px solid rgba(99,102,241,0.25)",
              color: "#a5b4fc",
              fontSize: "0.75rem",
              cursor: "pointer"
            }}
          >
            {p}
          </button>
        ))}
      </div>

      {/* Input Bar */}
      <div style={{ display: "flex", gap: "10px" }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Instruct the Vision Agent (e.g. 'Convert to WebP at 80% quality with 2x upscale')..."
          style={{
            flex: 1,
            padding: "14px 18px",
            borderRadius: "10px",
            background: "rgba(14, 18, 26, 0.9)",
            border: "1px solid var(--border-subtle)",
            color: "#f8fafc",
            fontSize: "0.9rem"
          }}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading}
          style={{
            padding: "0 22px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #4f46e5, #7c3aed)",
            color: "#ffffff",
            border: "none",
            fontWeight: "600",
            display: "flex",
            alignItems: "center",
            gap: "8px"
          }}
        >
          <Send size={16} /> Send
        </button>
      </div>

    </div>
  );
}
