export default function ErrorBlock({ error, onRetry }) {
  return (
    <div className="bg-error-bg rounded-xl p-5 flex items-start gap-4 max-w-xl mx-auto shadow-ambient">
      {/* Icon */}
      <div className="shrink-0 w-10 h-10 rounded-full bg-error/10 flex items-center justify-center mt-0.5">
        <svg
          className="w-5 h-5 text-error"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z"
            clipRule="evenodd"
          />
        </svg>
      </div>

      {/* Message */}
      <div className="flex-1 min-w-0">
        <h3 className="text-base font-semibold text-on-surface">
          Something went wrong while generating your presentation
        </h3>
        <p className="text-sm text-on-surface-variant mt-1">
          {error ||
            "Our connection to the generation engine was interrupted. Please try again."}
        </p>
      </div>

      {/* Retry */}
      <button
        onClick={onRetry}
        className="shrink-0 px-4 py-2 text-sm font-medium text-on-surface
          bg-surface-lowest rounded-lg border border-outline-variant
          hover:bg-surface-low transition-colors cursor-pointer"
      >
        Retry
      </button>
    </div>
  );
}
