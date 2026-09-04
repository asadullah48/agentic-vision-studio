import React, { useState, useEffect } from "react";
import { BarChart3, HelpCircle, Compass, Star, ExternalLink, Check, Shield, Zap, Sparkles } from "lucide-react";

export default function MarketIntelView() {
  const [subTab, setSubTab] = useState("matrix"); // "matrix", "quiz", "faqs"
  const [tools, setTools] = useState([]);
  const [faqs, setFaqs] = useState([]);
  const [loading, setLoading] = useState(true);

  // Quiz state
  const [quizAnswers, setQuizAnswers] = useState({
    primary_use_case: "web",
    needs_batch: false,
    needs_raw: false,
    needs_ocr: false,
    budget_preference: "free",
    priority: "speed"
  });
  const [recommendation, setRecommendation] = useState(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/market-intelligence/tools").then(r => r.json()),
      fetch("/api/market-intelligence/faqs").then(r => r.json())
    ]).then(([toolsData, faqsData]) => {
      setTools(toolsData);
      setFaqs(faqsData);
      setLoading(false);
    }).catch(err => {
      console.error("Error loading market intelligence", err);
      setLoading(false);
    });
  }, []);

  const handleQuizSubmit = async () => {
    try {
      const res = await fetch("/api/market-intelligence/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(quizAnswers)
      });
      const data = await res.json();
      setRecommendation(data);
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div style={{ padding: "0 24px 40px", display: "flex", flexDirection: "column", gap: "24px" }}>
      
      {/* Sub-navigation */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "12px" }}>
        <div>
          <h2 style={{ fontSize: "1.3rem", fontWeight: "700" }} className="gradient-text">
            2026 AI Image Converters Competitive Benchmark
          </h2>
          <p style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            Exhaustive evaluation of the Top 7 AI Image Converters, Recommendation Engine, and Technical Knowledge Base.
          </p>
        </div>

        <div style={{ display: "flex", gap: "6px", background: "rgba(0,0,0,0.3)", padding: "4px", borderRadius: "8px" }}>
          {[
            { id: "matrix", label: "Top 7 Leaderboard", icon: BarChart3 },
            { id: "quiz", label: "Tool Finder Quiz", icon: Compass },
            { id: "faqs", label: "Technical FAQs", icon: HelpCircle }
          ].map((t) => {
            const Icon = t.icon;
            const active = subTab === t.id;
            return (
              <button
                key={t.id}
                onClick={() => setSubTab(t.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "6px",
                  padding: "8px 14px",
                  borderRadius: "6px",
                  border: "none",
                  fontSize: "0.8rem",
                  fontWeight: active ? "600" : "500",
                  background: active ? "#6366f1" : "transparent",
                  color: "#ffffff"
                }}
              >
                <Icon size={14} /> {t.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 1. Comparison Matrix Table */}
      {subTab === "matrix" && (
        <div className="glass-panel" style={{ padding: "20px", overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border-subtle)", color: "var(--text-muted)" }}>
                <th style={{ padding: "12px" }}>Rank & Tool</th>
                <th style={{ padding: "12px" }}>Category</th>
                <th style={{ padding: "12px" }}>Supported Formats</th>
                <th style={{ padding: "12px" }}>AI Capabilities</th>
                <th style={{ padding: "12px" }}>Ratings</th>
                <th style={{ padding: "12px" }}>Pricing & Security</th>
              </tr>
            </thead>
            <tbody>
              {tools.map((t) => (
                <tr key={t.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                  <td style={{ padding: "14px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{
                        width: "24px",
                        height: "24px",
                        borderRadius: "50%",
                        background: t.rank === 1 ? "#f59e0b" : "rgba(255,255,255,0.1)",
                        color: t.rank === 1 ? "#000" : "#fff",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: "0.75rem",
                        fontWeight: "700"
                      }}>
                        #{t.rank}
                      </span>
                      <strong style={{ color: "#f8fafc", fontSize: "0.9rem" }}>{t.name}</strong>
                    </div>
                    <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: "4px", maxWidth: "260px" }}>
                      {t.overview}
                    </p>
                  </td>
                  <td style={{ padding: "14px 12px", verticalAlign: "top", color: "var(--accent-cyan)", fontWeight: "500" }}>
                    {t.category}
                  </td>
                  <td style={{ padding: "14px 12px", verticalAlign: "top", color: "#cbd5e1" }}>
                    <strong>{t.supported_formats_count}</strong>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "4px" }}>
                      Batch: {t.max_batch_support ? "Yes" : "Single"} | RAW: {t.raw_support ? "Yes" : "No"}
                    </div>
                  </td>
                  <td style={{ padding: "14px 12px", verticalAlign: "top" }}>
                    <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                      {t.ai_features.map((f, idx) => (
                        <span key={idx} style={{
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background: "rgba(99,102,241,0.15)",
                          color: "#a5b4fc",
                          fontSize: "0.72rem",
                          width: "fit-content"
                        }}>
                          {f}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td style={{ padding: "14px 12px", verticalAlign: "top" }}>
                    <div style={{ fontSize: "0.75rem", display: "flex", flexDirection: "column", gap: "2px" }}>
                      <span>Quality: <strong style={{ color: "#34d399" }}>{t.ratings.quality}/10</strong></span>
                      <span>Speed: <strong style={{ color: "#38bdf8" }}>{t.ratings.speed}/10</strong></span>
                      <span>Ease: <strong style={{ color: "#f59e0b" }}>{t.ratings.ease}/10</strong></span>
                    </div>
                  </td>
                  <td style={{ padding: "14px 12px", verticalAlign: "top" }}>
                    <div style={{ fontSize: "0.75rem", color: "#e2e8f0" }}>{t.cost_tier}</div>
                    <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "4px" }}>
                      {t.privacy_retention}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* 2. Interactive Tool Recommender Quiz */}
      {subTab === "quiz" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
          
          <div className="glass-panel" style={{ padding: "24px", display: "flex", flexDirection: "column", gap: "16px" }}>
            <h3 style={{ fontSize: "1.1rem", fontWeight: "600", display: "flex", alignItems: "center", gap: "8px" }}>
              <Compass size={20} color="var(--accent-cyan)" /> Diagnose Your Ideal Converter
            </h3>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                1. What is your primary use case?
              </label>
              <select
                value={quizAnswers.primary_use_case}
                onChange={(e) => setQuizAnswers({ ...quizAnswers, primary_use_case: e.target.value })}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", background: "rgba(0,0,0,0.4)", border: "1px solid var(--border-subtle)", color: "#fff" }}
              >
                <option value="web">Web Performance & SEO (WebP / Fast LCP)</option>
                <option value="ecommerce">E-Commerce Products & Cutouts</option>
                <option value="photography">Professional Photography & Camera RAW</option>
                <option value="documents">Document Archival & Text Scans (OCR)</option>
                <option value="quick">Quick Everyday Conversions</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "8px" }}>
                2. Do you need high-volume batch processing?
              </label>
              <div style={{ display: "flex", gap: "12px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="batch"
                    checked={quizAnswers.needs_batch}
                    onChange={() => setQuizAnswers({ ...quizAnswers, needs_batch: true })}
                  /> Yes, dozens at once
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", cursor: "pointer" }}>
                  <input
                    type="radio"
                    name="batch"
                    checked={!quizAnswers.needs_batch}
                    onChange={() => setQuizAnswers({ ...quizAnswers, needs_batch: false })}
                  /> No, single/few files
                </label>
              </div>
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "8px" }}>
                3. Special Requirements (Check all that apply):
              </label>
              <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={quizAnswers.needs_raw}
                    onChange={(e) => setQuizAnswers({ ...quizAnswers, needs_raw: e.target.checked })}
                  /> Camera RAW support (CR2, NEF, ARW)
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.8rem", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={quizAnswers.needs_ocr}
                    onChange={(e) => setQuizAnswers({ ...quizAnswers, needs_ocr: e.target.checked })}
                  /> Optical Character Recognition (OCR text extraction)
                </label>
              </div>
            </div>

            <div>
              <label style={{ fontSize: "0.8rem", color: "var(--text-secondary)", display: "block", marginBottom: "6px" }}>
                4. Budget Preference:
              </label>
              <select
                value={quizAnswers.budget_preference}
                onChange={(e) => setQuizAnswers({ ...quizAnswers, budget_preference: e.target.value })}
                style={{ width: "100%", padding: "10px", borderRadius: "8px", background: "rgba(0,0,0,0.4)", border: "1px solid var(--border-subtle)", color: "#fff" }}
              >
                <option value="free">100% Free / Zero Watermarks Priority</option>
                <option value="paid">Open to Premium for Enterprise Features</option>
              </select>
            </div>

            <button
              onClick={handleQuizSubmit}
              style={{
                padding: "12px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #06b6d4, #3b82f6)",
                color: "#ffffff",
                fontWeight: "600",
                border: "none",
                cursor: "pointer",
                marginTop: "10px"
              }}
            >
              Calculate Best Tool Match
            </button>
          </div>

          {/* Quiz Result View */}
          <div className="glass-panel" style={{ padding: "24px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
            {recommendation ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: "0.8rem", color: "var(--accent-cyan)", fontWeight: "600", textTransform: "uppercase" }}>
                    Top Recommendation
                  </span>
                  <span style={{
                    padding: "4px 12px",
                    borderRadius: "999px",
                    background: "rgba(16,185,129,0.2)",
                    color: "#34d399",
                    fontWeight: "700",
                    fontSize: "0.85rem"
                  }}>
                    {recommendation.match_score}% Match
                  </span>
                </div>

                <h3 style={{ fontSize: "1.4rem", fontWeight: "700", color: "#f8fafc" }}>
                  {recommendation.top_tool.name}
                </h3>
                <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.6" }}>
                  {recommendation.top_tool.overview}
                </p>

                <div style={{ background: "rgba(0,0,0,0.3)", padding: "14px", borderRadius: "8px", border: "1px solid var(--border-subtle)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", textTransform: "uppercase", marginBottom: "6px" }}>
                    Why this tool matches your workflow:
                  </div>
                  <ul style={{ paddingLeft: "18px", fontSize: "0.8rem", color: "#e2e8f0", display: "flex", flexDirection: "column", gap: "4px" }}>
                    {recommendation.matched_reasons.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>

                <div style={{ fontSize: "0.78rem", color: "var(--text-muted)" }}>
                  Alternative Options: {recommendation.alternative_tools.map(t => t.name).join(", ")}
                </div>
              </div>
            ) : (
              <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 0" }}>
                <Compass size={40} style={{ margin: "0 auto 12px", opacity: 0.4 }} />
                <p>Answer the 4 questions on the left and click "Calculate Best Tool Match" to receive algorithmic recommendations.</p>
              </div>
            )}
          </div>

        </div>
      )}

      {/* 3. Comprehensive FAQs */}
      {subTab === "faqs" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {faqs.map((f) => (
            <details key={f.id} className="glass-panel" style={{ padding: "16px 20px", borderRadius: "8px" }}>
              <summary style={{ fontWeight: "600", fontSize: "0.95rem", color: "#f8fafc", cursor: "pointer", listStyle: "none", display: "flex", alignItems: "center", gap: "10px" }}>
                <HelpCircle size={18} color="var(--accent-indigo)" />
                {f.question}
              </summary>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", lineHeight: "1.7", marginTop: "12px", paddingLeft: "28px" }}>
                {f.answer}
              </p>
            </details>
          ))}
        </div>
      )}

    </div>
  );
}
