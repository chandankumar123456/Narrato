import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ProgressPanel from "../components/ProgressPanel";
import LivePreview from "../components/LivePreview";
import ErrorBlock from "../components/ErrorBlock";

export default function ProcessingPage({
  status,
  progress,
  stageLabel,
  previewUrls,
  error,
  jobId: hookJobId,
  resumeJob,
  handleRetry,
  stream,
}) {
  const { job_id } = useParams();
  const navigate = useNavigate();

  // If we land directly on /job/:job_id, resume polling
  useEffect(() => {
    if (job_id && !hookJobId) {
      resumeJob(job_id);
    }
  }, [job_id, hookJobId, resumeJob]);

  // Navigate to editor page when done
  useEffect(() => {
    if (status === "done" && job_id) {
      navigate(`/editor/${job_id}`, { replace: true });
    }
  }, [status, job_id, navigate]);

  // Error state replaces the processing UI
  if (status === "error") {
    return (
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <ErrorBlock
          error={error}
          onRetry={() => {
            handleRetry();
            navigate("/");
          }}
        />
      </div>
    );
  }

  // Build slide data from SSE stream for progressive display
  const streamSlides = stream ? Object.values(stream.slides) : [];
  const renderedSlides = streamSlides.filter((s) => s.status === "rendered");
  const totalFromStream = stream?.totalSlides || 0;

  return (
    <div className="flex-1 px-6 py-12 max-w-4xl mx-auto w-full">
      {/* Progress Panel — now with real stage labels */}
      <ProgressPanel
        progress={progress}
        stageLabel={stageLabel}
        totalSlides={totalFromStream}
      />

      {/* Progressive Slide Preview from SSE */}
      {renderedSlides.length > 0 && (
        <section className="mt-10">
          <div className="flex items-baseline justify-between mb-4">
            <h2 className="font-heading text-2xl font-semibold text-on-surface">
              Live Preview
            </h2>
            <span className="text-xs font-semibold text-on-surface-variant uppercase tracking-wider">
              {renderedSlides.length} of {totalFromStream || "?"} slides rendered
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {renderedSlides.map((slide) => (
              <div
                key={`stream-${slide.slide_id}`}
                className="relative rounded-xl overflow-hidden bg-surface-low shadow-ambient
                  aspect-[4/3] animate-fade-in"
              >
                {slide.html ? (
                  <iframe
                    srcDoc={slide.html}
                    title={`Slide ${slide.slide_id}`}
                    className="w-full h-full border-0 pointer-events-none"
                    sandbox="allow-same-origin"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center">
                    <div className="w-6 h-6 rounded bg-surface-high" />
                  </div>
                )}
                <span
                  className="absolute top-2 left-2 text-[10px] font-semibold uppercase
                    bg-primary/80 text-white px-2 py-0.5 rounded"
                >
                  Slide {String(slide.slide_id).padStart(2, "0")}
                </span>
              </div>
            ))}
            {/* Skeleton placeholders for pending slides */}
            {totalFromStream > 0 &&
              Array.from({ length: Math.max(0, totalFromStream - renderedSlides.length) }).map(
                (_, i) => (
                  <div
                    key={`pending-${i}`}
                    className="rounded-xl overflow-hidden bg-surface-low aspect-[4/3]
                      flex items-center justify-center"
                  >
                    {i === 0 ? (
                      <div className="skeleton w-full h-full rounded-xl" />
                    ) : (
                      <svg
                        className="w-6 h-6 text-on-surface-dim/30"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      >
                        <rect x="3" y="3" width="18" height="18" rx="2" />
                        <path d="M3 15l5-5 4 4 4-4 5 5" />
                      </svg>
                    )}
                  </div>
                )
              )}
          </div>
        </section>
      )}

      {/* Fallback: old preview images when no SSE slides available */}
      {renderedSlides.length === 0 && previewUrls.length > 0 && (
        <LivePreview previewUrls={previewUrls} totalSlides={null} />
      )}

      {/* Skeleton preview while no previews yet and no SSE slides */}
      {renderedSlides.length === 0 && previewUrls.length === 0 && progress > 20 && (
        <LivePreview previewUrls={[]} totalSlides={totalFromStream || 8} />
      )}
    </div>
  );
}
