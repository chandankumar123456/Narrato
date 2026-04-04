import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { downloadUrl, previewImageUrl } from "../api/narrato";

export default function ResultPage({
  status,
  jobId: hookJobId,
  previewUrls,
  handleReset,
  resumeJob,
}) {
  const { job_id } = useParams();
  const navigate = useNavigate();

  // Resume polling if user lands directly on /job/:id/result (e.g. browser refresh)
  // This triggers when we have a URL param but no hook state yet (idle + no hookJobId)
  useEffect(() => {
    const shouldResumeJob = job_id && !hookJobId && status === "idle";
    if (shouldResumeJob) {
      resumeJob(job_id);
    }
  }, [job_id, hookJobId, status, resumeJob]);

  // If still processing, redirect to processing page
  useEffect(() => {
    if (status === "processing" && job_id) {
      navigate(`/job/${job_id}`, { replace: true });
    }
  }, [status, job_id, navigate]);

  const activeJobId = hookJobId || job_id;
  const slideCount = previewUrls.length;

  function handleCreateAnother() {
    handleReset();
    navigate("/");
  }

  return (
    <div className="flex-1 px-6 py-16 max-w-4xl mx-auto w-full">
      {/* Success Icon */}
      <div className="text-center mb-8">
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-success/10 mb-4">
          <svg
            className="w-8 h-8 text-success"
            viewBox="0 0 24 24"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z"
              clipRule="evenodd"
            />
          </svg>
        </div>

        <h1 className="font-heading text-3xl font-bold text-on-surface">
          Your presentation is ready
        </h1>
        <p className="text-base text-on-surface-variant mt-2">
          {slideCount > 0
            ? `All ${slideCount} slides have been generated, optimized, and are ready for export.`
            : "Your presentation has been generated and is ready for export."}
        </p>
      </div>

      {/* Slide Preview Grid */}
      {slideCount > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
          {previewUrls.map((url, i) => (
            <div
              key={url}
              className="rounded-xl overflow-hidden bg-surface-low aspect-[4/3] shadow-sm"
            >
              <img
                src={previewImageUrl(url)}
                alt={`Slide ${i + 1}`}
                className="w-full h-full object-cover"
                loading="lazy"
              />
            </div>
          ))}
        </div>
      )}

      {/* Empty preview placeholder if no previews loaded yet */}
      {slideCount === 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="rounded-xl bg-surface-low aspect-[4/3]"
            />
          ))}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex items-center justify-center gap-4">
        <a
          href={downloadUrl(activeJobId)}
          download
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-white
            font-semibold text-sm rounded-xl no-underline
            hover:bg-primary-hover transition-colors shadow-ambient"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.75 2.75a.75.75 0 00-1.5 0v8.614L6.295 8.235a.75.75 0 10-1.09 1.03l4.25 4.5a.75.75 0 001.09 0l4.25-4.5a.75.75 0 00-1.09-1.03l-2.955 3.129V2.75z" />
            <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
          </svg>
          Download PPT
        </a>

        <button
          onClick={handleCreateAnother}
          className="inline-flex items-center gap-2 px-6 py-3
            bg-surface-lowest text-on-surface font-medium text-sm
            rounded-xl border border-outline-variant
            hover:bg-surface-low transition-colors cursor-pointer"
        >
          <svg className="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
          </svg>
          Create Another
        </button>
      </div>
    </div>
  );
}
