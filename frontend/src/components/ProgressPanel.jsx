/**
 * Maps backend progress values to pipeline stage indicators.
 * Derived from orchestrator.py progress milestones.
 */
const STAGES = [
  { label: "Understanding your prompt", threshold: 5 },
  { label: "Building presentation structure", threshold: 35 },
  { label: "Generating slide content", threshold: 60 },
  { label: "Applying design and visuals", threshold: 85 },
];

function StageIcon({ state }) {
  if (state === "done") {
    return (
      <svg className="w-4 h-4 text-success shrink-0" viewBox="0 0 16 16" fill="currentColor">
        <path d="M8 0a8 8 0 110 16A8 8 0 018 0zm3.78 5.22a.75.75 0 00-1.06 0L7 8.94 5.28 7.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.06 0l4.25-4.25a.75.75 0 000-1.06z" />
      </svg>
    );
  }
  if (state === "active") {
    return (
      <svg className="w-4 h-4 text-primary shrink-0 ai-pulse" viewBox="0 0 16 16" fill="currentColor">
        <circle cx="8" cy="8" r="6" opacity="0.3" />
        <circle cx="8" cy="8" r="4" />
      </svg>
    );
  }
  return (
    <svg className="w-4 h-4 text-on-surface-dim shrink-0" viewBox="0 0 16 16" fill="currentColor">
      <circle cx="8" cy="8" r="4" opacity="0.3" />
    </svg>
  );
}

export default function ProgressPanel({ progress }) {
  return (
    <div className="bg-surface-lowest rounded-xl p-8 shadow-ambient max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-baseline justify-between mb-2">
        <div>
          <h2 className="font-heading text-xl font-semibold text-on-surface">
            Generating your presentation...
          </h2>
          <p className="text-sm text-on-surface-variant mt-0.5">
            This usually takes 15–45 seconds
          </p>
        </div>
        <span className="text-2xl font-heading font-semibold text-on-surface">
          {progress}%
        </span>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-surface-high rounded-full h-2 mt-4 mb-6 overflow-hidden">
        <div
          className="h-full rounded-full progress-bar-animated transition-[width] duration-500 ease-out"
          style={{ width: `${Math.max(progress, 2)}%` }}
        />
      </div>

      {/* Stage Indicators */}
      <div className="grid grid-cols-2 gap-3">
        {STAGES.map((stage, i) => {
          const next = STAGES[i + 1]?.threshold ?? 100;
          let state = "pending";
          if (progress >= next) state = "done";
          else if (progress >= stage.threshold) state = "active";

          return (
            <div key={stage.label} className="flex items-center gap-2">
              <StageIcon state={state} />
              <span
                className={`text-sm ${
                  state === "done"
                    ? "text-success font-medium"
                    : state === "active"
                    ? "text-primary font-medium"
                    : "text-on-surface-dim"
                }`}
              >
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
