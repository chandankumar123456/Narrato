const TONES = ["professional", "casual", "inspiring", "academic"];
const STYLES = [
  { value: "modern", label: "Modern Dark" },
  { value: "corporate", label: "Corporate" },
  { value: "minimal", label: "Minimal" },
];

export default function OptionsPanel({ options, onUpdate, disabled }) {
  return (
    <div className="bg-surface-lowest rounded-xl p-6 mt-4 shadow-ambient">
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-6 items-start">
        {/* Slide Count */}
        <div>
          <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-3">
            Slide Count
          </label>
          <input
            type="range"
            min={5}
            max={30}
            value={options.slide_count}
            onChange={(e) => onUpdate("slide_count", parseInt(e.target.value))}
            disabled={disabled}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-on-surface-dim mt-1">
            <span>5 Slides</span>
            <span>30 Slides</span>
          </div>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-3">
            Tone
          </label>
          <select
            value={options.tone}
            onChange={(e) => onUpdate("tone", e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 bg-surface-low rounded-lg text-sm text-on-surface
              border-0 outline-none appearance-none cursor-pointer
              focus:bg-surface-lowest focus:ring-2 focus:ring-primary/8"
          >
            {TONES.map((t) => (
              <option key={t} value={t}>
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Visual Style */}
        <div>
          <label className="block text-xs font-semibold text-on-surface-variant uppercase tracking-wider mb-3">
            Visual Style
          </label>
          <select
            value={options.visual_style}
            onChange={(e) => onUpdate("visual_style", e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 bg-surface-low rounded-lg text-sm text-on-surface
              border-0 outline-none appearance-none cursor-pointer
              focus:bg-surface-lowest focus:ring-2 focus:ring-primary/8"
          >
            {STYLES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        {/* Generate Images Toggle */}
        <div className="flex items-center gap-3 sm:pt-6">
          <span className="text-sm text-on-surface">Generate Images</span>
          <button
            type="button"
            onClick={() => onUpdate("image_preference", !options.image_preference)}
            disabled={disabled}
            className={`toggle-switch ${options.image_preference ? "active" : ""}`}
            aria-label="Toggle image generation"
          />
        </div>
      </div>
    </div>
  );
}
