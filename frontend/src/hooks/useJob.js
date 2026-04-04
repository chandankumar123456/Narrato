import { useState, useRef, useCallback, useEffect } from "react";
import {
  generatePresentation,
  pollStatus,
  requestPreview,
} from "../api/narrato";
import useStream from "./useStream";

/**
 * Custom hook encapsulating the full job lifecycle:
 * idle → processing → done | error
 *
 * Integrates SSE streaming (useStream) for real-time progress,
 * with a polling fallback if SSE is unavailable.
 */
export default function useJob() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState("idle"); // idle | processing | done | error
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [progress, setProgress] = useState(0);
  const [stageLabel, setStageLabel] = useState("");
  const [previewUrls, setPreviewUrls] = useState([]);
  const [options, setOptions] = useState({
    slide_count: 10,
    tone: "professional",
    visual_style: "modern",
    image_preference: true,
  });

  const pollRef = useRef(null);
  const previewPollRef = useRef(null);

  // SSE stream hook — activated when jobId is set and status is processing
  const stream = useStream(status === "processing" ? jobId : null);

  // Sync SSE progress into local state
  useEffect(() => {
    if (stream.connected || stream.events.length > 0) {
      if (stream.progress > progress) {
        setProgress(stream.progress);
      }
      if (stream.label) {
        setStageLabel(stream.label);
      }
    }
  }, [stream.progress, stream.label, stream.connected, stream.events.length, progress]);

  // SSE terminal: done
  useEffect(() => {
    if (stream.isDone && status === "processing") {
      // Stop any polling
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      setStatus("done");
      setProgress(100);
      // Trigger preview generation
      if (jobId) {
        requestPreview(jobId).catch(() => {});
        pollForPreviews(jobId);
      }
    }
  }, [stream.isDone, status, jobId]); // eslint-disable-line react-hooks/exhaustive-deps

  // SSE terminal: error
  useEffect(() => {
    if (stream.error && status === "processing") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      setStatus("error");
      setError(stream.error);
    }
  }, [stream.error, status]);

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
      } catch {
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
          // Only update progress from polling if SSE isn't providing it
          if (!stream.connected && data.progress > progress) {
            setProgress(data.progress || 0);
          }

          if (data.status === "completed") {
            clearInterval(pollRef.current);
            pollRef.current = null;
            // Only set done if SSE hasn't already
            if (status === "processing") {
              setStatus("done");
              setProgress(100);

              if (data.preview_urls && data.preview_urls.length > 0) {
                setPreviewUrls(data.preview_urls);
              } else {
                try {
                  await requestPreview(id);
                } catch {
                  /* optional */
                }
                pollForPreviews(id);
              }
            }
          } else if (data.status === "failed") {
            clearInterval(pollRef.current);
            pollRef.current = null;
            if (status === "processing") {
              setStatus("error");
              setError(data.error || "Generation failed.");
            }
          }
        } catch {
          /* network hiccup, keep polling */
        }
      }, 2000);
    },
    [pollForPreviews, stream.connected, progress, status]
  );

  const handleGenerate = useCallback(async () => {
    if (!prompt.trim()) return;
    setStatus("processing");
    setError(null);
    setProgress(0);
    setStageLabel("");
    setPreviewUrls([]);

    try {
      const { job_id } = await generatePresentation(prompt, options);
      setJobId(job_id);
      // SSE will auto-connect via useStream. Start polling as fallback.
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
      setStageLabel("");
      setPreviewUrls([]);
      setError(null);
      startPolling(id);
    },
    [startPolling]
  );

  const handleReset = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (previewPollRef.current) clearInterval(previewPollRef.current);
    stream.close();
    setStatus("idle");
    setJobId(null);
    setError(null);
    setProgress(0);
    setStageLabel("");
    setPreviewUrls([]);
    setPrompt("");
  }, [stream]);

  const handleRetry = useCallback(() => {
    setStatus("idle");
    setError(null);
    setProgress(0);
    setStageLabel("");
    setPreviewUrls([]);
  }, []);

  return {
    // State
    prompt,
    status,
    jobId,
    error,
    progress,
    stageLabel,
    previewUrls,
    options,
    // Stream state (for ProcessingPage to use directly)
    stream,
    // Actions
    setPrompt,
    updateOption,
    handleGenerate,
    handleReset,
    handleRetry,
    resumeJob,
  };
}
