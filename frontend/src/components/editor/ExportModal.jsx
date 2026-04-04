import { downloadUrl } from "../../api/narrato";

const FORMATS = [
  {
    id: "pdf",
    label: "PDF",
    desc: "Export as PDF document",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M6 2a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6H6zm7 1.5L18.5 9H13V3.5zM8 12h1c1.1 0 2 .9 2 2s-.9 2-2 2H9v2H8v-6zm1 3c.55 0 1-.45 1-1s-.45-1-1-1H9v2h0zm3-3h1.5c.83 0 1.5.67 1.5 1.5v3c0 .83-.67 1.5-1.5 1.5H12v-6zm1 5h.5a.5.5 0 00.5-.5v-3a.5.5 0 00-.5-.5H13v4zm3-5h2v1h-1v1h1v1h-1v2h-1v-5z"/>
      </svg>
    ),
    color: "from-red-500/20 to-pink-500/20",
    border: "border-red-500/20",
  },
  {
    id: "images",
    label: "Images",
    desc: "Download as PNG slides",
    icon: (
      <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
        <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm0 16H5V5h14v14zm-5-7l-3 3.72L9 13l-3 4h12l-4-5z"/>
      </svg>
    ),
    color: "from-green-500/20 to-emerald-500/20",
    border: "border-green-500/20",
  },
];

/**
 * Export modal — format selection with download.
 */
export default function ExportModal({ isOpen, onClose, jobId, slideCount }) {
  if (!isOpen) return null;

  function handleDownload(format) {
    if (format === "pdf") {
      window.open(downloadUrl(jobId), "_blank");
    } else {
      // Images — same download endpoint (rendering engine produces both)
      window.open(downloadUrl(jobId), "_blank");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-[#12121a] rounded-2xl border border-white/10
        shadow-2xl w-full max-w-md p-6 mx-4 animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Export Presentation</h2>
            <p className="text-xs text-white/40 mt-0.5">
              {slideCount} slides ready for export
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center
              text-white/40 hover:text-white hover:bg-white/10 transition-colors cursor-pointer border-0"
          >
            <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
              <path d="M3.72 3.72a.75.75 0 011.06 0L8 6.94l3.22-3.22a.75.75 0 111.06 1.06L9.06 8l3.22 3.22a.75.75 0 11-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 01-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 010-1.06z"/>
            </svg>
          </button>
        </div>

        {/* Format Cards */}
        <div className="space-y-3">
          {FORMATS.map((f) => (
            <button
              key={f.id}
              onClick={() => handleDownload(f.id)}
              className={`w-full flex items-center gap-4 p-4 rounded-xl
                bg-gradient-to-r ${f.color} border ${f.border}
                text-left cursor-pointer transition-all
                hover:scale-[1.02] hover:shadow-lg active:scale-[0.98]`}
            >
              <div className="w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center text-white/70">
                {f.icon}
              </div>
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-white">{f.label}</h3>
                <p className="text-[10px] text-white/40 mt-0.5">{f.desc}</p>
              </div>
              <svg className="w-4 h-4 text-white/30" viewBox="0 0 16 16" fill="currentColor">
                <path d="M2.75 14A1.75 1.75 0 011 12.25v-2.5a.75.75 0 011.5 0v2.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25v-2.5a.75.75 0 011.5 0v2.5A1.75 1.75 0 0113.25 14H2.75z"/>
                <path d="M7.25 7.689V2a.75.75 0 011.5 0v5.689l1.97-1.969a.749.749 0 111.06 1.06l-3.25 3.25a.749.749 0 01-1.06 0L4.22 6.78a.749.749 0 111.06-1.06l1.97 1.969z"/>
              </svg>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
