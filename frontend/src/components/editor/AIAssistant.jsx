import { useState } from "react";

const QUICK_ACTIONS = [
  { label: "Improve this slide", instruction: "Improve this slide - make it more impactful, specific, and engaging" },
  { label: "Add an example", instruction: "Add a concrete, real-world example to make the content more relatable" },
  { label: "Make more persuasive", instruction: "Make this slide more persuasive and compelling for the audience" },
  { label: "Simplify content", instruction: "Simplify the content - use clearer language, fewer words, easier to understand" },
  { label: "Add data/stats", instruction: "Add relevant statistics or data points to support the content" },
  { label: "Make more visual", instruction: "Restructure the content to be more visual and scannable with clear hierarchy" },
];

/**
 * AI Assistant panel — slide-level improvement interface.
 * Appears as a slide-over panel from the right.
 */
export default function AIAssistant({
  isOpen,
  onClose,
  slideId,
  slideType,
  onRegenerate,
  loading,
}) {
  const [customInstruction, setCustomInstruction] = useState("");
  const [processing, setProcessing] = useState(false);
  const [lastAction, setLastAction] = useState(null);

  async function handleAction(instruction) {
    setProcessing(true);
    setLastAction(instruction);
    await onRegenerate(slideId, instruction);
    setProcessing(false);
  }

  async function handleCustomSubmit(e) {
    e.preventDefault();
    if (!customInstruction.trim()) return;
    await handleAction(customInstruction.trim());
    setCustomInstruction("");
  }

  if (!isOpen) return null;

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-[#0f0f14] border-l border-white/[0.06]
      shadow-2xl z-50 flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06]">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 to-purple-500
            flex items-center justify-center">
            <svg className="w-3.5 h-3.5 text-white" viewBox="0 0 16 16" fill="currentColor">
              <path d="M8 0l1.669 4.842L14.834 6l-4.166 3.158L12.165 14 8 10.842 3.835 14l1.497-4.842L1.166 6l5.165-1.158z"/>
            </svg>
          </div>
          <h3 className="text-sm font-semibold text-white"
              style={{ fontFamily: "'Manrope', sans-serif" }}>AI Assistant</h3>
        </div>
        <button
          onClick={onClose}
          className="w-6 h-6 rounded-md bg-white/5 flex items-center justify-center
            text-white/40 hover:text-white hover:bg-white/10 transition-colors cursor-pointer border-0"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
            <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/>
          </svg>
        </button>
      </div>

      {/* Context */}
      <div className="px-4 py-3 bg-white/[0.02] border-b border-white/5">
        <p className="text-[10px] text-white/30 uppercase tracking-wider">Editing</p>
        <p className="text-xs text-white/60 mt-0.5">
          Slide {slideId} · {slideType || "Content"}
        </p>
      </div>

      {/* Quick Actions */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2 scrollbar-thin">
        <h4 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
          Quick Improvements
        </h4>
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => handleAction(action.instruction)}
            disabled={processing || loading}
            className={`w-full text-left px-3 py-2.5 rounded-lg text-xs transition-all
              cursor-pointer border-0 flex items-center gap-2
              ${processing && lastAction === action.instruction
                ? "bg-indigo-600/20 text-indigo-300 ring-1 ring-indigo-500/30"
                : "bg-white/5 text-white/60 hover:bg-white/10 hover:text-white/80"
              }
              disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {processing && lastAction === action.instruction ? (
              <div className="w-3 h-3 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin shrink-0" />
            ) : (
              <svg className="w-3 h-3 shrink-0 text-indigo-400" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0l1.669 4.842L14.834 6l-4.166 3.158L12.165 14 8 10.842 3.835 14l1.497-4.842L1.166 6l5.165-1.158z"/>
              </svg>
            )}
            {action.label}
          </button>
        ))}

        <div className="h-px bg-white/5 my-3" />

        {/* Custom Instruction */}
        <h4 className="text-[10px] font-semibold text-white/40 uppercase tracking-wider mb-2">
          Custom Instruction
        </h4>
        <form onSubmit={handleCustomSubmit} className="space-y-2">
          <textarea
            value={customInstruction}
            onChange={(e) => setCustomInstruction(e.target.value)}
            placeholder="Tell the AI what to change..."
            rows={3}
            disabled={processing || loading}
            className="w-full resize-none text-xs text-white bg-white/5 rounded-lg p-3
              border border-white/10 outline-none
              placeholder:text-white/20
              focus:border-indigo-500/30 focus:bg-white/[0.07]
              transition-all font-body leading-relaxed
              disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={processing || loading || !customInstruction.trim()}
            className="w-full py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold
              hover:bg-indigo-500 transition-colors
              disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer border-0
              flex items-center justify-center gap-2"
          >
            {processing ? (
              <>
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Processing...
              </>
            ) : (
              <>
                <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M.989 8L.064 2.68a1.342 1.342 0 011.85-1.462l13.402 5.744a1.13 1.13 0 010 2.076L1.913 14.782a1.343 1.343 0 01-1.85-1.463L.99 8zm1.536.5L2.1 12.26l9.984-4.282H2.525zm0-1l8.01 0L2.1 3.74l.425 3.76z"/>
                </svg>
                Apply Changes
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
