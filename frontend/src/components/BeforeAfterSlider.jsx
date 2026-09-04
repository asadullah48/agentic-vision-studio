import React, { useState, useRef, useCallback } from "react";
import { ArrowLeftRight, Download, ZoomIn } from "lucide-react";

export default function BeforeAfterSlider({ originalUrl, convertedUrl, originalInfo, convertedInfo }) {
  const [sliderPos, setSliderPos] = useState(50);
  const containerRef = useRef(null);
  const isDragging = useRef(false);

  const handleMove = useCallback((clientX) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = clientX - rect.left;
    const pct = Math.max(0, Math.min(100, (x / rect.width) * 100));
    setSliderPos(pct);
  }, []);

  const handleTouchMove = (e) => {
    if (e.touches.length > 0) handleMove(e.touches[0].clientX);
  };

  const handleMouseDown = () => {
    isDragging.current = true;
  };

  const handleMouseUp = () => {
    isDragging.current = false;
  };

  const handleMouseMove = (e) => {
    if (isDragging.current) handleMove(e.clientX);
  };

  return (
    <div className="glass-panel" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ArrowLeftRight size={18} color="var(--accent-cyan)" />
          <h3 style={{ fontSize: "1rem", fontWeight: "600" }}>Perceptual Visual Diff Slider</h3>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Drag center curtain to inspect fidelity</span>
          {convertedUrl && (
            <a
              href={convertedUrl}
              download={convertedInfo?.filename || "converted_image"}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "6px 14px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #10b981, #059669)",
                color: "#ffffff",
                textDecoration: "none",
                fontSize: "0.8rem",
                fontWeight: "600",
                boxShadow: "0 2px 8px rgba(16,185,129,0.3)"
              }}
            >
              <Download size={14} /> Download Asset
            </a>
          )}
        </div>
      </div>

      {/* Slider Viewport */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onMouseMove={handleMouseMove}
        onTouchMove={handleTouchMove}
        style={{
          position: "relative",
          width: "100%",
          height: "460px",
          borderRadius: "10px",
          overflow: "hidden",
          background: "#080c14",
          border: "1px solid var(--border-subtle)",
          cursor: "ew-resize",
          userSelect: "none"
        }}
      >
        {/* Converted (Right / Bottom layer) */}
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <img
            src={convertedUrl || originalUrl}
            alt="Converted"
            style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
          />
          <div style={{
            position: "absolute",
            bottom: "16px",
            right: "16px",
            background: "rgba(16,185,129,0.85)",
            backdropFilter: "blur(8px)",
            padding: "4px 12px",
            borderRadius: "6px",
            fontSize: "0.75rem",
            fontWeight: "600",
            color: "#ffffff"
          }}>
            Converted: {convertedInfo?.format || "OUTPUT"} ({convertedInfo?.sizeKb || 0} KB)
          </div>
        </div>

        {/* Original (Left / Top clipped layer) */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: `${sliderPos}%`,
            overflow: "hidden",
            borderRight: "2px solid #6366f1",
            boxShadow: "2px 0 12px rgba(99,102,241,0.6)"
          }}
        >
          <div style={{ width: containerRef.current ? `${containerRef.current.clientWidth}px` : "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <img
              src={originalUrl}
              alt="Original"
              style={{ maxWidth: "100%", maxHeight: "100%", objectFit: "contain" }}
            />
          </div>
          <div style={{
            position: "absolute",
            bottom: "16px",
            left: "16px",
            background: "rgba(30,41,59,0.85)",
            backdropFilter: "blur(8px)",
            padding: "4px 12px",
            borderRadius: "6px",
            fontSize: "0.75rem",
            fontWeight: "600",
            color: "#f8fafc",
            border: "1px solid rgba(255,255,255,0.1)"
          }}>
            Original: {originalInfo?.format || "SOURCE"} ({originalInfo?.sizeKb || 0} KB)
          </div>
        </div>

        {/* Slider Handle */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: `${sliderPos}%`,
            transform: "translate(-50%, -50%)",
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            background: "#6366f1",
            boxShadow: "0 0 18px rgba(99,102,241,0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            pointerEvents: "none"
          }}
        >
          <ArrowLeftRight size={16} />
        </div>
      </div>
    </div>
  );
}
