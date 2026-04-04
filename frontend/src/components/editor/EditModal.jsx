import { useState } from "react";

/**
 * Inline edit modal — allows editing slide content fields.
 * Each field is rendered as an editable input.
 */
export default function EditModal({
  isOpen,
  onClose,
  slide,
  onSave,
  loading,
}) {
  const [editedContent, setEditedContent] = useState({});
  const [trackedSlideId, setTrackedSlideId] = useState(null);

  // Sync edited content when slide changes
  const currentSlideId = slide?.slide_id ?? null;
  if (currentSlideId !== trackedSlideId && slide?.content) {
    setTrackedSlideId(currentSlideId);
    setEditedContent(JSON.parse(JSON.stringify(slide.content)));
  }

  if (!isOpen || !slide) return null;

  function handleFieldChange(key, value) {
    setEditedContent((prev) => ({ ...prev, [key]: value }));
  }

  function handleBulletChange(key, index, value) {
    setEditedContent((prev) => {
      const arr = [...(prev[key] || [])];
      arr[index] = value;
      return { ...prev, [key]: arr };
    });
  }

  async function handleSave() {
    await onSave(slide.slide_id, editedContent);
    onClose();
  }

  // Render fields based on content structure
  function renderField(key, value) {
    if (value === null || value === undefined) return null;

    if (Array.isArray(value)) {
      // Array of strings (bullets)
      if (value.length > 0 && typeof value[0] === "string") {
        return (
          <div key={key} className="space-y-1.5">
            <label className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
              {formatLabel(key)}
            </label>
            {value.map((item, i) => (
              <input
                key={`${key}-${i}`}
                type="text"
                value={editedContent[key]?.[i] || ""}
                onChange={(e) => handleBulletChange(key, i, e.target.value)}
                className="w-full px-3 py-2 text-xs text-white bg-white/5 rounded-lg
                  border border-white/10 outline-none focus:border-indigo-500/30
                  transition-colors font-body"
              />
            ))}
          </div>
        );
      }
      // Array of objects — show as JSON
      return (
        <div key={key} className="space-y-1.5">
          <label className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
            {formatLabel(key)}
          </label>
          <textarea
            value={JSON.stringify(editedContent[key] || value, null, 2)}
            onChange={(e) => {
              try {
                handleFieldChange(key, JSON.parse(e.target.value));
              } catch {
                // ignore parse errors while editing
              }
            }}
            rows={Math.min(8, value.length * 2)}
            className="w-full resize-none text-xs text-white bg-white/5 rounded-lg p-3
              border border-white/10 outline-none focus:border-indigo-500/30
              transition-colors font-mono leading-relaxed"
          />
        </div>
      );
    }

    if (typeof value === "object") {
      // Nested object — recurse
      return (
        <div key={key} className="space-y-2">
          <label className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
            {formatLabel(key)}
          </label>
          <div className="pl-3 border-l border-white/5 space-y-2">
            {Object.entries(value).map(([k, v]) => renderField(`${key}.${k}`, v))}
          </div>
        </div>
      );
    }

    // Simple string/number
    return (
      <div key={key} className="space-y-1.5">
        <label className="text-[10px] font-semibold text-white/40 uppercase tracking-wider">
          {formatLabel(key)}
        </label>
        {String(value).length > 60 ? (
          <textarea
            value={getNestedValue(editedContent, key) ?? ""}
            onChange={(e) => setNestedValue(key, e.target.value)}
            rows={3}
            className="w-full resize-none text-xs text-white bg-white/5 rounded-lg p-3
              border border-white/10 outline-none focus:border-indigo-500/30
              transition-colors font-body leading-relaxed"
          />
        ) : (
          <input
            type="text"
            value={getNestedValue(editedContent, key) ?? ""}
            onChange={(e) => setNestedValue(key, e.target.value)}
            className="w-full px-3 py-2 text-xs text-white bg-white/5 rounded-lg
              border border-white/10 outline-none focus:border-indigo-500/30
              transition-colors font-body"
          />
        )}
      </div>
    );
  }

  function setNestedValue(path, value) {
    const keys = path.split(".");
    setEditedContent((prev) => {
      const copy = JSON.parse(JSON.stringify(prev));
      let obj = copy;
      for (let i = 0; i < keys.length - 1; i++) {
        if (!obj[keys[i]]) obj[keys[i]] = {};
        obj = obj[keys[i]];
      }
      obj[keys[keys.length - 1]] = value;
      return copy;
    });
  }

  function getNestedValue(obj, path) {
    const keys = path.split(".");
    let current = obj;
    for (const key of keys) {
      if (current == null) return "";
      current = current[key];
    }
    return current ?? "";
  }

  function formatLabel(key) {
    return key
      .split(".")
      .pop()
      .replace(/_/g, " ")
      .replace(/\b\w/g, (l) => l.toUpperCase());
  }

  const content = slide.content || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative bg-[#12121a] rounded-2xl border border-white/10
        shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col mx-4 animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5 shrink-0">
          <div>
            <h2 className="text-base font-semibold text-white">Edit Slide {slide.slide_id}</h2>
            <p className="text-[10px] text-white/30 mt-0.5">{slide.type || "Content"}</p>
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

        {/* Content Fields */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 scrollbar-thin">
          {Object.entries(content).map(([key, value]) => renderField(key, value))}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-white/5 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-white/5 text-white/60 text-xs font-medium
              hover:bg-white/10 transition-colors cursor-pointer border-0"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-xs font-semibold
              hover:bg-indigo-500 transition-colors disabled:opacity-50
              cursor-pointer border-0 flex items-center gap-2"
          >
            {loading ? (
              <>
                <div className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                Saving...
              </>
            ) : (
              "Save & Re-render"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
