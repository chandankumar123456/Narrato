/**
 * Right control panel — locked single rendering system controls.
 */
export default function ControlPanel({
  slide,
  onRestyle,
  onOpenAI,
  onOpenExport,
  onEdit,
  loading,
}) {
  async function handleReapplySystem() {
    await onRestyle("layered_neutral_card_system", "locked");
  }

  return (
    <aside className="w-64 shrink-0 border-l flex flex-col overflow-hidden"
           style={{ backgroundColor: "var(--editor-surface)", borderColor: "var(--editor-border)" }}>
      <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--editor-border)" }}>
        <h3 className="text-xs font-semibold uppercase tracking-wider"
            style={{ fontFamily: "var(--font-heading)", color: "var(--editor-text-secondary)" }}>
          Controls
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 scrollbar-thin">
        <section className="rounded-lg border border-white/10 bg-white/5 p-3">
          <h4 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
            Rendering System
          </h4>
          <p className="text-xs text-white/60 m-0">
            Layered Neutral Card System is enforced globally.
          </p>
        </section>

        <button
          onClick={handleReapplySystem}
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-indigo-600 text-white text-xs font-semibold
            hover:bg-indigo-500 transition-colors disabled:opacity-50
            disabled:cursor-not-allowed cursor-pointer border-0"
        >
          Re-apply Rendering System
        </button>

        <div className="h-px bg-white/5" />

        <button
          onClick={onEdit}
          disabled={!slide}
          className="w-full py-2 rounded-lg bg-white/5 text-white/70 text-xs font-medium
            hover:bg-white/10 hover:text-white transition-colors
            disabled:opacity-30 cursor-pointer border-0"
        >
          Edit Slide Content
        </button>

        <button
          onClick={onOpenAI}
          disabled={!slide}
          className="w-full py-2 rounded-lg bg-white/5 text-white/70 text-xs font-medium
            hover:bg-white/10 hover:text-white transition-colors
            disabled:opacity-30 cursor-pointer border-0"
        >
          AI Assistant
        </button>

        <div className="h-px bg-white/5" />

        <button
          onClick={onOpenExport}
          className="w-full py-2.5 rounded-lg bg-white/5 text-white text-xs font-semibold
            hover:bg-white/10 transition-colors cursor-pointer border border-white/10"
        >
          Export Presentation
        </button>
      </div>
    </aside>
  );
}
