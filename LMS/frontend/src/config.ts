const configuredApi = import.meta.env.VITE_API_URL?.trim()

if (!configuredApi && import.meta.env.PROD) {
  throw new Error("VITE_API_URL must be configured for production deployments")
}

const localApi = "http://127.0.0.1:8000"
export const API = (configuredApi || localApi).replace(/\/$/, "")
