const SUGGESTIONS = [
  '"12-slide pitch deck for AI startup"',
  '"Quarterly marketing strategy review"',
  '"Historical analysis of the Renaissance"',
];

export default function SuggestionChips({ onSelect, disabled }) {
  return (
    <div className="flex flex-wrap gap-2 justify-center mt-3">
      {SUGGESTIONS.map((s) => (
        <button
          key={s}
          disabled={disabled}
          onClick={() => onSelect(s.replace(/"/g, ""))}
          className="px-4 py-1.5 text-xs font-medium rounded-full
            bg-secondary-fixed text-on-surface-variant
            hover:bg-secondary-fixed-dim transition-colors
            disabled:opacity-50 disabled:cursor-not-allowed
            cursor-pointer border-0"
        >
          {s}
        </button>
      ))}
    </div>
  );
}
