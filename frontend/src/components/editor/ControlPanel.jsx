import { useState } from "react";

const THEMES = [
  { value: "dark_modern", label: "Dark", icon: "🌙" },
  { value: "minimal_light", label: "Light", icon: "☀️" },
  { value: "bold_gradient", label: "Gradient", icon: "🎨" },
];

const DENSITIES = [
  { value: "visual", label: "More Visual" },
  { value: "minimal", label: "More Minimal" },
  { value: "data_heavy", label: "Data Heavy" },
  { value: "balanced", label: "Balanced" },
];

/**
 * Right control panel — theme switching, style density,
 * AI assist, and export controls.
 */
export default function ControlPanel({
  slide,
  theme,
  onRestyle,
  onOpenAI,
  onOpenExport,
  onEdit,
  loading,
}) {
  const [selectedTheme, setSelectedTheme] = useState(theme || "dark_modern");
  const [selectedDensity, setSelectedDensity] = useState("balanced");
  const [restyling, setRestyling] = useState(false);

  async function handleApplyTheme() {
    setRestyling(true);
    await onRestyle(selectedTheme, selectedDensity);
    setRestyling(false);
  }

  return (
    <aside className="w-64 shrink-0 border-l flex flex-col overflow-hidden"
           style={{ backgroundColor: 'var(--editor-surface)', borderColor: 'var(--editor-border)' }}>
      {/* Header */}
      <div className="px-4 py-3" style={{ borderBottom: '1px solid var(--editor-border)' }}>
        <h3 className="text-xs font-semibold uppercase tracking-wider"
            style={{ fontFamily: 'var(--font-heading)', color: 'var(--editor-text-secondary)' }}>
          Controls
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5 scrollbar-thin">
        {/* Theme Section */}
        <section>
          <h4 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
            Theme
          </h4>
          <div className="grid grid-cols-3 gap-1.5">
            {THEMES.map((t) => (
              <button
                key={t.value}
                onClick={() => setSelectedTheme(t.value)}
                className={`py-2 rounded-lg text-xs font-medium transition-all cursor-pointer border-0
                  ${selectedTheme === t.value
                    ? "bg-indigo-600 text-white ring-1 ring-indigo-400"
                    : "bg-white/5 text-white/50 hover:bg-white/10 hover:text-white/70"
                  }`}
              >
                <span className="block text-sm mb-0.5">{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>
        </section>

        {/* Density Section */}
        <section>
          <h4 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
            Style
          </h4>
          <div className="space-y-1">
            {DENSITIES.map((d) => (
              <button
                key={d.value}
                onClick={() => setSelectedDensity(d.value)}
                className={`w-full text-left px-3 py-1.5 rounded-md text-xs transition-all cursor-pointer border-0
                  ${selectedDensity === d.value
                    ? "bg-white/10 text-white font-medium"
                    : "text-white/40 hover:bg-white/5 hover:text-white/60"
                  }`}
              >
                {d.label}
              </button>
            ))}
          </div>
        </section>

        {/* Apply Theme */}
        <button
          onClick={handleApplyTheme}
          disabled={restyling || loading}
          className="w-full py-2.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold
            hover:bg-indigo-500 transition-colors disabled:opacity-50
            disabled:cursor-not-allowed cursor-pointer border-0
            flex items-center justify-center gap-2"
        >
          {restyling ? (
            <>
              <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Applying...
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0a8 8 0 100 16A8 8 0 008 0zm3.78 5.22a.75.75 0 010 1.06l-4.25 4.25a.75.75 0 01-1.06 0l-2.25-2.25a.75.75 0 111.06-1.06L7 8.94l3.72-3.72a.75.75 0 011.06 0z"/>
              </svg>
              Apply Theme
            </>
          )}
        </button>

        <div className="h-px bg-white/5" />

        {/* Edit Current Slide */}
        <button
          onClick={onEdit}
          disabled={!slide}
          className="w-full py-2 rounded-lg bg-white/5 text-white/70 text-xs font-medium
            hover:bg-white/10 hover:text-white transition-colors
            disabled:opacity-30 cursor-pointer border-0
            flex items-center gap-2 px-3"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M11.013 1.427a1.75 1.75 0 012.474 0l1.086 1.086a1.75 1.75 0 010 2.474l-8.61 8.61c-.21.21-.47.364-.756.445l-3.251.93a.75.75 0 01-.927-.928l.929-3.25a1.75 1.75 0 01.445-.758l8.61-8.61z"/>
          </svg>
          Edit Slide Content
        </button>

        {/* AI Assist */}
        <button
          onClick={onOpenAI}
          disabled={!slide}
          className="w-full py-2 rounded-lg bg-gradient-to-r from-indigo-600/20 to-purple-600/20
            text-indigo-300 text-xs font-medium
            hover:from-indigo-600/30 hover:to-purple-600/30 transition-all
            disabled:opacity-30 cursor-pointer border border-indigo-500/20
            flex items-center gap-2 px-3"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 0l1.669 4.842L14.834 6l-4.166 3.158L12.165 14 8 10.842 3.835 14l1.497-4.842L1.166 6l5.165-1.158z"/>
          </svg>
          AI Assistant
        </button>

        <div className="h-px bg-white/5" />

        {/* Export */}
        <button
          onClick={onOpenExport}
          className="w-full py-2.5 rounded-lg bg-white/5 text-white text-xs font-semibold
            hover:bg-white/10 transition-colors cursor-pointer border border-white/10
            flex items-center justify-center gap-2"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75z"/>
            <path d="M7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.969a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.78a.749.749 0 111.06-1.06l1.97 1.969z"/>
          </svg>
          Export Presentation
        </button>
      </div>
    </aside>
  );
}
