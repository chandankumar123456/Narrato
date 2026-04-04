import { useNavigate } from "react-router-dom";
import SuggestionChips from "../components/SuggestionChips";
import OptionsPanel from "../components/OptionsPanel";

export default function InputPage({
  prompt,
  setPrompt,
  options,
  updateOption,
  onGenerate,
}) {
  const navigate = useNavigate();
  const maxLength = 3000;

  async function handleGenerate() {
    const jobId = await onGenerate();
    if (jobId) {
      navigate(`/job/${jobId}`);
    }
  }

  return (
    <div className="flex-1 flex flex-col items-center px-6">
      {/* Hero Section */}
      <section className="text-center mt-16 mb-10 max-w-2xl">
        <h1 className="font-heading text-[3.5rem] leading-[1.1] font-bold text-on-surface tracking-tight">
          Turn Ideas into Presentations
        </h1>
        <p className="text-base text-on-surface-variant mt-4 leading-relaxed">
          Generate professional, high-impact slide decks in seconds with
          Narrato&apos;s intelligent engineering engine.
        </p>
      </section>

      {/* Input Card */}
      <section className="w-full max-w-2xl">
        <div className="bg-surface-lowest rounded-2xl p-6 shadow-ambient">
          {/* Textarea */}
          <textarea
            rows={4}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            maxLength={maxLength}
            placeholder="Describe your presentation topic or paste your outline here..."
            className="w-full resize-none text-base text-on-surface
              bg-surface-low rounded-xl p-4 border-0 outline-none
              placeholder:text-on-surface-dim
              focus:bg-surface-lowest focus:ring-2 focus:ring-primary/8
              transition-all font-body leading-relaxed"
          />
          {/* Character Counter */}
          <div className="text-right mt-1">
            <span className="text-xs text-on-surface-dim">
              {prompt.length} / {maxLength}
            </span>
          </div>
        </div>

        {/* Suggestion Chips */}
        <SuggestionChips onSelect={(s) => setPrompt(s)} disabled={false} />

        {/* Options Panel */}
        <OptionsPanel
          options={options}
          onUpdate={updateOption}
          disabled={false}
        />

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={!prompt.trim()}
          className="w-full mt-6 py-4 bg-primary text-white font-semibold text-base
            rounded-xl border-0 cursor-pointer
            hover:bg-primary-hover transition-colors
            disabled:opacity-50 disabled:cursor-not-allowed
            flex items-center justify-center gap-2 shadow-ambient"
        >
          <svg className="w-5 h-5" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10 2l1.5 4.5L16 8l-4.5 1.5L10 14l-1.5-4.5L4 8l4.5-1.5L10 2z" />
          </svg>
          Generate Presentation
        </button>
      </section>
    </div>
  );
}
