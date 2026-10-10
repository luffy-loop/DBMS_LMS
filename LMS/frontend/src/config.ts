const configuredApi = import.meta.env.VITE_API_URL?.trim()
const productionApi = "https://dbms-lms-hwvp.onrender.com"
const localApi = "http://127.0.0.1:8000"

export const API = (import.meta.env.PROD ? productionApi : (configuredApi || localApi)).replace(/\/$/, "")
