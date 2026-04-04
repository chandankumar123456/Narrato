import { useState, useCallback } from "react";
import {
  fetchSlides,
  regenerateSlide,
  restyleSlides,
  updateSlide,
  reorderSlides,
  duplicateSlide,
  deleteSlide,
} from "../api/narrato";

/**
 * Custom hook for the interactive slide editor.
 * Manages slide data, selection, and all editing operations.
 */
export default function useEditor(jobId) {
  const [slides, setSlides] = useState([]);
  const [activeSlide, setActiveSlide] = useState(0);
  const [loading, setLoading] = useState(false);
  const [slideLoading, setSlideLoading] = useState(null); // slide index being processed
  const [theme, setTheme] = useState("dark_modern");
  const [error, setError] = useState(null);

  const loadSlides = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSlides(jobId);
      const slidesData = (data.slides || []).map((s, i) => ({
        ...s,
        index: i,
        cacheKey: Date.now(),
      }));
      setSlides(slidesData);
      if (slidesData.length > 0 && activeSlide >= slidesData.length) {
        setActiveSlide(0);
      }
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to load slides");
    } finally {
      setLoading(false);
    }
  }, [jobId, activeSlide]);

  const handleRegenerate = useCallback(
    async (slideId, instruction) => {
      setSlideLoading(slideId - 1);
      setError(null);
      try {
        const result = await regenerateSlide(jobId, slideId, instruction);
        setSlides((prev) =>
          prev.map((s) =>
            s.slide_id === slideId
              ? {
                  ...s,
                  html_url: result.html_url,
                  content: result.content || s.content,
                  html: result.html,
                  cacheKey: Date.now(),
                }
              : s
          )
        );
        return result;
      } catch (e) {
        setError(e?.response?.data?.detail || "Regeneration failed");
        return null;
      } finally {
        setSlideLoading(null);
      }
    },
    [jobId]
  );

  const handleRestyle = useCallback(
    async (newTheme, density) => {
      setLoading(true);
      setError(null);
      try {
        const result = await restyleSlides(jobId, newTheme, density);
        setTheme(newTheme);
        if (result.slides) {
          setSlides((prev) =>
            prev.map((s, i) => {
              const restyled = result.slides[i];
              return restyled
                ? {
                    ...s,
                    html_url: restyled.html_url,
                    html: restyled.html,
                    cacheKey: Date.now(),
                  }
                : s;
            })
          );
        }
        return result;
      } catch (e) {
        setError(e?.response?.data?.detail || "Restyle failed");
        return null;
      } finally {
        setLoading(false);
      }
    },
    [jobId]
  );

  const handleUpdateSlide = useCallback(
    async (slideId, content) => {
      setSlideLoading(slideId - 1);
      setError(null);
      try {
        const result = await updateSlide(jobId, slideId, content);
        setSlides((prev) =>
          prev.map((s) =>
            s.slide_id === slideId
              ? {
                  ...s,
                  html_url: result.html_url,
                  html: result.html,
                  cacheKey: Date.now(),
                }
              : s
          )
        );
        return result;
      } catch (e) {
        setError(e?.response?.data?.detail || "Update failed");
        return null;
      } finally {
        setSlideLoading(null);
      }
    },
    [jobId]
  );

  const handleDuplicate = useCallback(
    async (slideId) => {
      setError(null);
      try {
        await duplicateSlide(jobId, slideId);
        await loadSlides();
      } catch (e) {
        setError(e?.response?.data?.detail || "Duplicate failed");
      }
    },
    [jobId, loadSlides]
  );

  const handleDelete = useCallback(
    async (slideId) => {
      if (slides.length <= 1) return;
      setError(null);
      try {
        await deleteSlide(jobId, slideId);
        setSlides((prev) => {
          const next = prev.filter((s) => s.slide_id !== slideId);
          return next.map((s, i) => ({ ...s, slide_id: i + 1, index: i }));
        });
        if (activeSlide >= slides.length - 1) {
          setActiveSlide(Math.max(0, slides.length - 2));
        }
      } catch (e) {
        setError(e?.response?.data?.detail || "Delete failed");
      }
    },
    [jobId, slides.length, activeSlide]
  );

  const handleReorder = useCallback(
    async (fromIndex, toIndex) => {
      if (fromIndex === toIndex) return;
      setError(null);
      const newSlides = [...slides];
      const [moved] = newSlides.splice(fromIndex, 1);
      newSlides.splice(toIndex, 0, moved);
      const reindexed = newSlides.map((s, i) => ({
        ...s,
        slide_id: i + 1,
        index: i,
      }));
      setSlides(reindexed);
      setActiveSlide(toIndex);
      try {
        const order = reindexed.map((_, i) => {
          // The original slide_id before reorder
          return slides.indexOf(newSlides[i]) + 1;
        });
        await reorderSlides(jobId, order);
      } catch (e) {
        setError(e?.response?.data?.detail || "Reorder failed");
        await loadSlides(); // rollback
      }
    },
    [jobId, slides, loadSlides]
  );

  return {
    slides,
    activeSlide,
    setActiveSlide,
    loading,
    slideLoading,
    theme,
    error,
    setError,
    loadSlides,
    handleRegenerate,
    handleRestyle,
    handleUpdateSlide,
    handleDuplicate,
    handleDelete,
    handleReorder,
  };
}
