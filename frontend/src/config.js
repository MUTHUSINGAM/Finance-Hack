/** Backend base URL. Set VITE_API_URL in frontend/.env (e.g. http://localhost:8001) */
export const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(
  /\/$/,
  ''
);
