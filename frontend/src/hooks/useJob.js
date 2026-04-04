import { useState, useRef, useCallback, useEffect } from "react";
import {
  generatePresentation,
  pollStatus,
  requestPreview,
} from "../api/narrato";

/**
 * Custom hook encapsulating the full job lifecycle:
 * idle → processing → done | error
 *
 * Provides: state values + action dispatchers for the UI.
 */
export default function useJob() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("idle"); // idle | processing | done | error
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [previewUrls, setPreviewUrls] = useState([]);
  const [options, setOptions] = useState({
    slide_count: 10,
    tone: "professional",
    visual_style: "modern",
    image_preference: true,
  });

  const pollRef = useRef(null);
  const previewPollRef = useRef(null);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (previewPollRef.current) clearInterval(previewPollRef.current);
    };
  }, []);

  const updateOption = useCallback((key, value) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  const pollForPreviews = useCallback((id) => {
    let attempts = 0;
    previewPollRef.current = setInterval(async () => {
      attempts++;
      try {
        const data = await pollStatus(id);
        if (data.preview_urls && data.preview_urls.length > 0) {
          setPreviewUrls(data.preview_urls);
          clearInterval(previewPollRef.current);
          previewPollRef.current = null;
        }
      } catch (_) {
        /* ignore */
      }
      if (attempts > 10) {
        clearInterval(previewPollRef.current);
        previewPollRef.current = null;
      }
    }, 3000);
  }, []);

  const startPolling = useCallback(
    (id) => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const data = await pollStatus(id);
          setProgress(data.progress || 0);

          if (data.status === "completed") {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus("done");
            setProgress(100);

            if (data.preview_urls && data.preview_urls.length > 0) {
              setPreviewUrls(data.preview_urls);
            } else {
              try {
                await requestPreview(id);
              } catch (_) {
                /* optional */
              }
              pollForPreviews(id);
            }
          } else if (data.status === "failed") {
            clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus("error");
            setError(data.error || "Generation failed.");
          }
        } catch (_) {
          /* network hiccup, keep polling */
        }
      }, 2000);
    },
    [pollForPreviews]
  );

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    setStatus("processing");
    setError(null);
    setProgress(0);
    setPreviewUrls([]);

    try {
      const { job_id } = await generatePresentation(prompt, options);
      setJobId(job_id);
      startPolling(job_id);
      return job_id;
    } catch (e) {
      setStatus("error");
      setError(
        e?.response?.data?.detail || "Generation failed. Please try again."
      );
      return null;
    }
  }, [prompt, options, startPolling]);

  // Resume polling for an existing job
  const resumeJob = useCallback(
    (id) => {
      setJobId(id);
      setStatus("processing");
      setProgress(0);
      setPreviewUrls([]);
      setError(null);
      startPolling(id);
    },
    [startPolling]
  );

  const handleReset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (previewPollRef.current) clearInterval(previewPollRef.current);
    setStatus("idle");
    setJobId(null);
    setError(null);
    setProgress(0);
    setPreviewUrls([]);
    setPrompt("");
  }, []);

  const handleRetry = useCallback(() => {
    setStatus("idle");
    setError(null);
    setProgress(0);
    setPreviewUrls([]);
  }, []);

  return {
    // State
    prompt,
    status,
    jobId,
    error,
    progress,
    previewUrls,
    options,
    // Actions
    setPrompt,
    updateOption,
    handleGenerate,
    handleReset,
    handleRetry,
    resumeJob,
  };
}
