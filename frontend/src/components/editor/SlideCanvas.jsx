import { useRef, useEffect } from "react";

/**
 * Continuous canvas — renders all slides in a single vertical narrative surface.
 * Selection is preserved via focused section scrolling.
 */
export default function SlideCanvas({
  slides,
  slideIndex,
  totalSlides,
  slideLoadingId,
  onNavigate,
  onRegenerate,
  onDuplicate,
  onEdit,
}) {
  const containerRef = useRef(null);
  const sectionRefs = useRef([]);

  useEffect(() => {
    function handleKey(e) {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "ArrowUp" || e.key === "ArrowLeft") {
        e.preventDefault();
        onNavigate(Math.max(0, slideIndex - 1));
      } else if (e.key === "ArrowDown" || e.key === "ArrowRight") {
        e.preventDefault();
        onNavigate(Math.min(totalSlides - 1, slideIndex + 1));
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [slideIndex, totalSlides, onNavigate]);

  useEffect(() => {
    const el = sectionRefs.current[slideIndex];
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [slideIndex]);

  if (!slides || slides.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[#0a0a0f]">
        <p className="text-sm text-white/30">No slides loaded</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-[#0a0a0f] overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-[#0f0f14] border-b border-white/[0.06]">
        <span className="text-xs text-white/50 font-medium">Continuous deck view</span>
        <span className="text-[10px] text-white/30 uppercase tracking-wider">
          {slideIndex + 1} / {totalSlides}
        </span>
      </div>

      <div ref={containerRef} className="flex-1 overflow-auto px-6 py-6 space-y-5 scrollbar-thin">
        {slides.map((item, idx) => {
          const active = idx === slideIndex;
          const slideUrl = item.html ? null : item.html_url ? `${item.html_url}?t=${item.cacheKey || ""}` : null;
          const loading = slideLoadingId === item.slide_id;
          return (
            <section
              key={`canvas-slide-${item.slide_id}-${idx}`}
              ref={(el) => (sectionRefs.current[idx] = el)}
              onClick={() => onNavigate(idx)}
              className={`relative rounded-lg overflow-hidden border cursor-pointer transition-all ${
                active ? "border-indigo-500 ring-2 ring-indigo-500/30" : "border-white/10 hover:border-white/20"
              }`}
            >
              <div className="absolute top-2 left-2 z-10 bg-black/70 text-[10px] text-white/80 px-2 py-1 rounded">
                Slide {idx + 1}
              </div>

              {loading ? (
                <div className="w-full aspect-[16/9] bg-[#1a1a24] flex items-center justify-center">
                  <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : item.html ? (
                <iframe
                  srcDoc={item.html}
                  title={`Slide ${idx + 1}`}
                  className="w-full aspect-[16/9] border-0 bg-white"
                  sandbox="allow-same-origin allow-scripts"
                />
              ) : slideUrl ? (
                <iframe
                  src={slideUrl}
                  title={`Slide ${idx + 1}`}
                  className="w-full aspect-[16/9] border-0 bg-white"
                  sandbox="allow-same-origin allow-scripts"
                />
              ) : (
                <div className="w-full aspect-[16/9] bg-[#1a1a24] flex items-center justify-center text-white/30 text-sm">
                  No content
                </div>
              )}

              {active && (
                <div className="flex items-center gap-2 px-3 py-2 bg-[#0f0f14] border-t border-white/[0.06]">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onEdit && onEdit();
                    }}
                    className="px-3 py-1.5 rounded-md bg-white/10 text-white text-xs hover:bg-white/20 border-0 cursor-pointer"
                  >
                    Edit
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onRegenerate && onRegenerate();
                    }}
                    className="px-3 py-1.5 rounded-md bg-indigo-600 text-white text-xs hover:bg-indigo-500 border-0 cursor-pointer"
                  >
                    Regenerate
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDuplicate && onDuplicate();
                    }}
                    className="px-3 py-1.5 rounded-md bg-white/10 text-white text-xs hover:bg-white/20 border-0 cursor-pointer"
                  >
                    Duplicate
                  </button>
                </div>
              )}
            </section>
          );
        })}
      </div>
    </div>
  );
}
