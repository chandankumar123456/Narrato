import axios from "axios";
const BASE = "http://localhost:8000";

export async function generatePresentation(prompt, options = {}) {
  const { data } = await axios.post(`${BASE}/generate`, { prompt, options });
  return data; // { job_id, status, estimated_seconds }
}

export async function pollStatus(jobId) {
  const { data } = await axios.get(`${BASE}/status/${jobId}`);
  return data;
}

export function downloadUrl(jobId) {
  return `${BASE}/download/${jobId}`;
}