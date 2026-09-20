const localApi = "http://127.0.0.1:8000"
const configuredApi = import.meta.env.VITE_API_URL?.trim()

export const API = (configuredApi || localApi).replace(/\/$/, "")
