import axios from "axios";

// Use relative URLs; Vite dev server proxies to backend
const api = axios.create({ baseURL: "" });

export async function generatePresentation(prompt, options = {}) {
  const { data } = await api.post("/generate", { prompt, options });
  return data; // { job_id, status, estimated_seconds }
}

export async function pollStatus(jobId) {
  const { data } = await api.get(`/status/${jobId}`);
  return data;
}

export function downloadUrl(jobId) {
  return `/download/${jobId}`;
}

export async function requestPreview(jobId) {
  const { data } = await api.post(`/preview/${jobId}`);
  return data;
}

export function previewImageUrl(path) {
  // path already starts with /previews/...
  return path;
}

// ── Interactive Product Layer APIs ──────────────────────────

export async function fetchSlides(jobId) {
  const { data } = await api.get(`/slides/${jobId}`);
  return data; // { job_id, slides: [{slide_id, html_url, content, type}], status, total }
}

export async function regenerateSlide(jobId, slideId, instruction = "") {
  const { data } = await api.post(`/regenerate-slide/${jobId}`, {
    slide_id: slideId,
    instruction,
  });
  return data; // { slide_id, html_url, html, content, status }
}

export async function restyleSlides(jobId, theme, density = "balanced") {
  const { data } = await api.post(`/restyle-slides/${jobId}`, {
    theme,
    density,
  });
  return data; // { job_id, theme, slides: [...], status }
}

export async function updateSlide(jobId, slideId, content) {
  const { data } = await api.post(`/update-slide/${jobId}`, {
    slide_id: slideId,
    content,
  });
  return data; // { slide_id, html_url, html, status }
}

export async function reorderSlides(jobId, order) {
  const { data } = await api.post(`/reorder-slides/${jobId}`, { order });
  return data;
}

export async function duplicateSlide(jobId, slideId) {
  const { data } = await api.post(`/duplicate-slide/${jobId}`, {
    slide_id: slideId,
  });
  return data;
}

export async function deleteSlide(jobId, slideId) {
  const { data } = await api.delete(`/delete-slide/${jobId}/${slideId}`);
  return data;
}