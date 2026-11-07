
import axiosInstance from "axios";

const API_BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

export const api = axiosInstance.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
});

// Intercepteur pour injecter automatiquement le token JWT à chaque requête
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("access_token");
    if (token && config.headers) {
      if (typeof config.headers.set === 'function') {
        config.headers.set('Authorization', `Bearer ${token}`);
      } else {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Intercepteur pour gérer les expirations de session (401)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Nettoyer les tokens obsolètes
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");

      // Détecter la langue courante de l'URL pour rediriger proprement
      const currentLang = window.location.pathname.split("/")[1] || "de";
      const langPrefix = ["de", "fr", "en"].includes(currentLang) ? `/${currentLang}` : "/de";
      
      if (!window.location.pathname.includes("/login")) {
        window.location.href = `${langPrefix}/login?expired=true`;
      }
    }
    return Promise.reject(error);
  }
);

export default api;
