import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ProgressPanel from "../components/ProgressPanel";
import LivePreview from "../components/LivePreview";
import ErrorBlock from "../components/ErrorBlock";

export default function ProcessingPage({
  status,
  progress,
  previewUrls,
  error,
  jobId: hookJobId,
  resumeJob,
  handleRetry,
}) {
  const { job_id } = useParams();
  const navigate = useNavigate();

  // If we land directly on /job/:job_id, resume polling
  useEffect(() => {
    if (job_id && !hookJobId) {
      resumeJob(job_id);
    }
  }, [job_id, hookJobId, resumeJob]);

  // Navigate to result page when done
  useEffect(() => {
    if (status === "done" && job_id) {
      navigate(`/job/${job_id}/result`, { replace: true });
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

  return (
    <div className="flex-1 px-6 py-12 max-w-4xl mx-auto w-full">
      {/* Progress Panel */}
      <ProgressPanel progress={progress} />

      {/* Live Preview - shows incrementally as slides are generated */}
      {previewUrls.length > 0 && (
        <LivePreview
          previewUrls={previewUrls}
          totalSlides={null}
        />
      )}

      {/* Skeleton preview while no previews yet */}
      {previewUrls.length === 0 && progress > 20 && (
        <LivePreview previewUrls={[]} totalSlides={8} />
      )}
    </div>
  );
}
