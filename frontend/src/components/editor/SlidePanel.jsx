/**
 * Left sidebar slide panel — thumbnail list with navigation,
 * delete, and duplicate controls.
 *
 * Each thumbnail renders an iframe at 1920×1080 scaled down
 * to fit the thumbnail container via CSS transform.
 */
export default function SlidePanel({
  slides,
  activeSlide,
  onSelect,
  onDuplicate,
  onDelete,
  slideLoading,
}) {
  // Thumbnail width inside the panel (accounting for padding)
  // Panel is w-56 (224px), with px-3 (12px each side) = 200px available
  const thumbW = 200;
  const thumbScale = thumbW / 1920;
  const thumbH = Math.round(1080 * thumbScale);

  return (
    <aside className="w-56 shrink-0 bg-[#0f0f14] border-r border-white/5 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-white/5">
        <h3 className="text-xs font-semibold text-white/50 uppercase tracking-wider">
          Slides
        </h3>
        <span className="text-[10px] text-white/30">{slides.length} slides</span>
      </div>

      {/* Slide List */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-thin">
        {slides.map((slide, idx) => (
          <div
            key={`slide-${slide.slide_id}-${idx}`}
            onClick={() => onSelect(idx)}
            className={`group relative rounded-lg cursor-pointer transition-all duration-200
              ${activeSlide === idx
                ? "ring-2 ring-indigo-500 bg-white/8"
                : "hover:bg-white/5 ring-1 ring-white/5"
              }
              ${slideLoading === slide.slide_id ? "opacity-60 animate-pulse" : ""}
            `}
          >
            {/* Slide Number Badge */}
            <div className="absolute top-1.5 left-1.5 z-10 bg-black/60 backdrop-blur-sm
              text-[9px] font-bold text-white/70 px-1.5 py-0.5 rounded">
              {String(idx + 1).padStart(2, "0")}
            </div>

            {/* Thumbnail */}
            <div
              className="bg-[#1a1a24] rounded-t-lg overflow-hidden"
              style={{ width: thumbW, height: thumbH }}
            >
              {slide.html_url ? (
                <iframe
                  src={`${slide.html_url}?t=${slide.cacheKey || ""}`}
                  title={`Slide ${idx + 1}`}
                  className="border-0 pointer-events-none"
                  style={{
                    width: 1920,
                    height: 1080,
                    transform: `scale(${thumbScale})`,
                    transformOrigin: "top left",
                  }}
                  loading="lazy"
                  sandbox="allow-same-origin allow-scripts"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <div className="w-6 h-6 rounded bg-white/5" />
                </div>
              )}
            </div>

            {/* Slide Type */}
            <div className="px-2 py-1.5">
              <span className="text-[10px] text-white/40 truncate block">
                {slide.type || "Slide"}
              </span>
            </div>

            {/* Hover Actions */}
            <div className="absolute top-1.5 right-1.5 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-10">
              <button
                onClick={(e) => { e.stopPropagation(); onDuplicate(slide.slide_id); }}
                className="w-5 h-5 rounded bg-black/60 backdrop-blur-sm flex items-center justify-center
                  text-white/60 hover:text-white hover:bg-indigo-600 transition-colors cursor-pointer border-0"
                title="Duplicate"
              >
                <svg className="w-2.5 h-2.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M0 6.75C0 5.784.784 5 1.75 5h1.5a.75.75 0 010 1.5h-1.5a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-1.5a.75.75 0 011.5 0v1.5A1.75 1.75 0 019.25 16h-7.5A1.75 1.75 0 010 14.25v-7.5z"/>
                  <path d="M5 1.75C5 .784 5.784 0 6.75 0h7.5C15.216 0 16 .784 16 1.75v7.5A1.75 1.75 0 0114.25 11h-7.5A1.75 1.75 0 015 9.25v-7.5zm1.75-.25a.25.25 0 00-.25.25v7.5c0 .138.112.25.25.25h7.5a.25.25 0 00.25-.25v-7.5a.25.25 0 00-.25-.25h-7.5z"/>
                </svg>
              </button>
              {slides.length > 1 && (
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(slide.slide_id); }}
                  className="w-5 h-5 rounded bg-black/60 backdrop-blur-sm flex items-center justify-center
                    text-white/60 hover:text-red-400 hover:bg-red-600/20 transition-colors cursor-pointer border-0"
                  title="Delete"
                >
                  <svg className="w-2.5 h-2.5" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M11 1.75V3h2.25a.75.75 0 010 1.5H2.75a.75.75 0 010-1.5H5V1.75C5 .784 5.784 0 6.75 0h2.5C10.216 0 11 .784 11 1.75zM9.5 1.75a.25.25 0 00-.25-.25h-2.5a.25.25 0 00-.25.25V3h3V1.75zM4.997 6.178a.75.75 0 10-1.493.144l.44 4.571A2.75 2.75 0 006.69 13.5h2.62a2.75 2.75 0 002.745-2.607l.44-4.571a.75.75 0 10-1.493-.144l-.44 4.571a1.25 1.25 0 01-1.247 1.251H6.69a1.25 1.25 0 01-1.247-1.251l-.44-4.571z"/>
                  </svg>
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </aside>
  );
}
