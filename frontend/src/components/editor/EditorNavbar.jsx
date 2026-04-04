import { Link } from "react-router-dom";

/**
 * Editor navbar — minimal top bar with logo, generate, and download actions.
 */
export default function EditorNavbar({ onExport }) {
  return (
    <nav className="w-full bg-[#0a0a0f]/90 backdrop-blur-xl border-b border-white/5 sticky top-0 z-40">
      <div className="px-4 h-12 flex items-center justify-between">
        {/* Left: Logo */}
        <div className="flex items-center gap-4">
          <Link
            to="/"
            className="font-heading text-white font-bold text-sm tracking-tight no-underline
              flex items-center gap-2"
          >
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-indigo-500 to-purple-600
              flex items-center justify-center text-[10px] font-bold">
              N
            </div>
            Narrato
          </Link>
          <span className="text-[9px] text-white/20 uppercase tracking-widest font-medium">
            Editor
          </span>
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2">
          <Link
            to="/"
            className="px-3 py-1.5 rounded-md bg-white/5 text-white/60 text-xs font-medium
              hover:bg-white/10 hover:text-white transition-colors no-underline
              flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
            New
          </Link>
          <button
            onClick={onExport}
            className="px-3 py-1.5 rounded-md bg-indigo-600 text-white text-xs font-semibold
              hover:bg-indigo-500 transition-colors cursor-pointer border-0
              flex items-center gap-1.5"
          >
            <svg className="w-3 h-3" viewBox="0 0 16 16" fill="currentColor">
              <path d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75z"/>
              <path d="M7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.969a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.78a.749.749 0 111.06-1.06l1.97 1.969z"/>
            </svg>
            Export
          </button>
        </div>
      </div>
    </nav>
  );
}
