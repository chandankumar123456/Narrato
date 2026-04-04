import { useEffect, useRef, useCallback, useState } from "react";

/**
 * SSE hook — subscribes to /stream/{jobId} and dispatches events.
 *
 * Uses the "adjusting state during render" pattern to reset state
 * when jobId changes, which is the React-approved approach.
 */
export default function useStream(jobId) {
  const [state, setState] = useState(makeInitial);
  const [trackedJobId, setTrackedJobId] = useState(null);
  const esRef = useRef(null);

  // Reset state when jobId changes — React-approved "adjust state during render"
  if (jobId !== trackedJobId) {
    setTrackedJobId(jobId);
    setState(makeInitial());
  }

  const close = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setState((prev) => ({ ...prev, connected: false }));
  }, []);

  useEffect(() => {
    if (!jobId) return;

    const es = new EventSource(`/stream/${jobId}`);
    esRef.current = es;

    es.onopen = () => {
      setState((prev) => ({ ...prev, connected: true }));
    };

    es.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        return;
      }

      setState((prev) => {
        const next = {
          ...prev,
          events: [...prev.events, data],
        };

        if (data.progress != null) next.progress = data.progress;
        if (data.label) next.label = data.label;
        if (data.stage) next.stage = data.stage;
        if (data.total_slides) next.totalSlides = data.total_slides;

        // Per-slide events
        if (data.type === "SLIDE_DESIGNED" && data.slide_id) {
          next.slides = {
            ...prev.slides,
            [data.slide_id]: {
              ...prev.slides[data.slide_id],
              status: "designed",
              slide_id: data.slide_id,
            },
          };
        }

        if (data.type === "SLIDE_RENDERED" && data.slide_id) {
          next.slides = {
            ...prev.slides,
            [data.slide_id]: {
              ...prev.slides[data.slide_id],
              status: "rendered",
              slide_id: data.slide_id,
              html: data.data?.html || null,
            },
          };
        }

        if (data.type === "JOB_COMPLETED") {
          next.isDone = true;
          next.progress = 100;
          next.connected = false;
        }

        if (data.type === "JOB_FAILED") {
          next.error = data.data?.error || data.label || "Generation failed";
          next.connected = false;
        }

        return next;
      });

      // Close connection on terminal events
      if (data.type === "JOB_COMPLETED" || data.type === "JOB_FAILED") {
        es.close();
        esRef.current = null;
      }
    };

    es.onerror = () => {
      if (es.readyState === EventSource.CLOSED) {
        setState((prev) => ({ ...prev, connected: false }));
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [jobId]);

  return {
    ...state,
    close,
  };
}

function makeInitial() {
  return {
    events: [],
    progress: 0,
    label: "",
    stage: "",
    slides: {},
    totalSlides: 0,
    isDone: false,
    error: null,
    connected: false,
  };
}
