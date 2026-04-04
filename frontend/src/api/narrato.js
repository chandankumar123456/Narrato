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