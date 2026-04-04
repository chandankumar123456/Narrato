import { useState, useRef, useEffect, useCallback } from "react";

/**
 * Center canvas — renders the active slide in an iframe with
 * proper 16:9 scaling and hover overlay actions.
 *
 * Slides are authored at 1920×1080. This component scales them
 * to fit the available viewport while maintaining aspect ratio,
 * using a CSS transform approach (no content modification).
 */
export default function SlideCanvas({
  slide,
  slideIndex,
  totalSlides,
  isLoading,
  onNavigate,
  onRegenerate,
  onDuplicate,
  onEdit,
}) {
  const [hovered, setHovered] = useState(false);
  const iframeRef = useRef(null);
  const containerRef = useRef(null);
  const [scale, setScale] = useState(0.5);

  // Compute scale factor so 1920×1080 slide fits inside container
  const updateScale = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;
    const padding = 48; // 24px each side
    const availW = container.clientWidth - padding;
    const availH = container.clientHeight - padding;
    if (availW <= 0 || availH <= 0) return;
    const scaleX = availW / 1920;
    const scaleY = availH / 1080;
    setScale(Math.min(scaleX, scaleY));
  }, []);

  useEffect(() => {
    updateScale();
    window.addEventListener("resize", updateScale);
    return () => window.removeEventListener("resize", updateScale);
  }, [updateScale]);

  // Keyboard navigation
  useEffect(() => {
    function handleKey(e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
        e.preventDefault();
        onNavigate(Math.max(0, slideIndex - 1));
      } else if (e.key === "ArrowRight" || e.key === "ArrowDown") {
        e.preventDefault();
        onNavigate(Math.min(totalSlides - 1, slideIndex + 1));
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [slideIndex, totalSlides, onNavigate]);

  if (!slide) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0a0f]">
        <div className="text-center">
          <div className="w-16 h-16 rounded-2xl bg-white/5 mx-auto mb-4 flex items-center justify-center">
            <svg className="w-8 h-8 text-white/20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <path d="M3 15l5-5 4 4 4-4 5 5" />
            </svg>
          </div>
          <p className="text-sm text-white/30">No slide selected</p>
        </div>
      </div>
    );
  }

  const slideUrl = slide.html
    ? null // use srcdoc
    : slide.html_url
    ? `${slide.html_url}?t=${slide.cacheKey || ""}`
    : null;

  const scaledW = Math.round(1920 * scale);
  const scaledH = Math.round(1080 * scale);

  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0f] overflow-hidden">
      {/* Navigation Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-[#0f0f14] border-b border-white/5">
        <div className="flex items-center gap-2">
          <button
            onClick={() => onNavigate(Math.max(0, slideIndex - 1))}
            disabled={slideIndex === 0}
            className="w-7 h-7 rounded-md bg-white/5 flex items-center justify-center
              text-white/50 hover:text-white hover:bg-white/10 transition-colors
              disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer border-0"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M9.78 12.78a.75.75 0 01-1.06 0L4.47 8.53a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 1.06L6.06 8l3.72 3.72a.75.75 0 010 1.06z" />
            </svg>
          </button>
          <span className="text-xs text-white/50 font-medium min-w-[60px] text-center">
            {slideIndex + 1} / {totalSlides}
          </span>
          <button
            onClick={() => onNavigate(Math.min(totalSlides - 1, slideIndex + 1))}
            disabled={slideIndex >= totalSlides - 1}
            className="w-7 h-7 rounded-md bg-white/5 flex items-center justify-center
              text-white/50 hover:text-white hover:bg-white/10 transition-colors
              disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer border-0"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
              <path d="M6.22 3.22a.75.75 0 011.06 0l4.25 4.25a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06-1.06L9.94 8 6.22 4.28a.75.75 0 010-1.06z" />
            </svg>
          </button>
        </div>
        <span className="text-[10px] text-white/30 uppercase tracking-wider">
          {slide.type || "Slide"}
        </span>
      </div>

      {/* Canvas Area */}
      <div
        ref={containerRef}
        className="flex-1 flex items-center justify-center p-6 relative"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* Slide Frame — fixed 1920×1080 scaled to fit */}
        <div
          className="relative rounded-lg overflow-hidden shadow-2xl ring-1 ring-white/5"
          style={{ width: scaledW, height: scaledH }}
        >
          {isLoading ? (
            <div className="w-full h-full bg-[#1a1a24] flex items-center justify-center">
              <div className="flex flex-col items-center gap-3">
                <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs text-white/40">Regenerating...</span>
              </div>
            </div>
          ) : slide.html ? (
            <iframe
              ref={iframeRef}
              srcDoc={slide.html}
              title={`Slide ${slideIndex + 1}`}
              className="border-0"
              style={{
                width: 1920,
                height: 1080,
                transform: `scale(${scale})`,
                transformOrigin: "top left",
              }}
              sandbox="allow-same-origin allow-scripts"
            />
          ) : slideUrl ? (
            <iframe
              ref={iframeRef}
              src={slideUrl}
              title={`Slide ${slideIndex + 1}`}
              className="border-0"
              style={{
                width: 1920,
                height: 1080,
                transform: `scale(${scale})`,
                transformOrigin: "top left",
              }}
              sandbox="allow-same-origin allow-scripts"
            />
          ) : (
            <div className="w-full h-full bg-[#1a1a24] flex items-center justify-center">
              <span className="text-sm text-white/30">No content</span>
            </div>
          )}

          {/* Hover Overlay */}
          {hovered && !isLoading && (
            <div className="absolute inset-0 bg-black/30 backdrop-blur-[1px] flex items-center justify-center
              gap-3 transition-opacity duration-200 animate-fade-in">
              <button
                onClick={() => onEdit && onEdit()}
                className="px-3 py-2 rounded-lg bg-white/10 backdrop-blur-md text-white text-xs font-medium
                  hover:bg-white/20 transition-colors flex items-center gap-1.5 cursor-pointer border-0"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M11.013 1.427a1.75 1.75 0 012.474 0l1.086 1.086a1.75 1.75 0 010 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 01-.927-.928l.929-3.25a1.75 1.75 0 01.445-.758l8.61-8.61zm1.414 1.06a.25.25 0 00-.354 0L3.462 11.098a.25.25 0 00-.064.108l-.631 2.208 2.208-.63a.25.25 0 00.108-.064l8.61-8.611a.25.25 0 000-.354L12.427 2.487z"/>
                </svg>
                Edit
              </button>
              <button
                onClick={() => onRegenerate && onRegenerate()}
                className="px-3 py-2 rounded-lg bg-indigo-600/80 backdrop-blur-md text-white text-xs font-medium
                  hover:bg-indigo-600 transition-colors flex items-center gap-1.5 cursor-pointer border-0"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M1.705 8.005a.75.75 0 01.834.656 5.5 5.5 0 009.592 2.97l-1.204-1.204a.25.25 0 01.177-.427h3.646a.25.25 0 01.25.25v3.646a.25.25 0 01-.427.177l-1.38-1.38A7.002 7.002 0 011.05 8.84a.75.75 0 01.656-.834zM8 2.5a5.487 5.487 0 00-4.131 1.869l1.204 1.204A.25.25 0 014.896 6H1.25A.25.25 0 011 5.75V2.104a.25.25 0 01.427-.177l1.38 1.38A7.002 7.002 0 0114.95 7.16a.75.75 0 11-1.49.178A5.5 5.5 0 008 2.5z"/>
                </svg>
                Regenerate
              </button>
              <button
                onClick={() => onDuplicate && onDuplicate()}
                className="px-3 py-2 rounded-lg bg-white/10 backdrop-blur-md text-white text-xs font-medium
                  hover:bg-white/20 transition-colors flex items-center gap-1.5 cursor-pointer border-0"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"/>
                  <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"/>
                </svg>
                Duplicate
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
