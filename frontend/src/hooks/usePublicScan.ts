// frontend/src/hooks/usePublicScan.ts
// Hook réservé au déclenchement d'un nouveau scan public depuis l'accueil

import React, { useCallback, useState } from 'react';
import axios, { AxiosError } from 'axios';

interface PublicScanTriggerResponse {
  scan_id: string;
  score: number;
  status: string;
}

interface UsePublicScanReturn {
  loading: boolean;
  error: string | null;
  isRateLimited: boolean;
  scanResult: PublicScanTriggerResponse | null;
  triggerScan: (url: string) => Promise<void>;
  dismissRateLimitModal: () => void;
}

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

export function usePublicScan(): UsePublicScanReturn {
  // Initialisé à false pour éviter le blocage "Analyse..." au chargement
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isRateLimited, setIsRateLimited] = useState(false);
  const [scanResult, setScanResult] = useState<PublicScanTriggerResponse | null>(null);

  const triggerScan = useCallback(async (url: string) => {
    setLoading(true);
    setError(null);
    setIsRateLimited(false);

    try {
      const response = await axios.post<PublicScanTriggerResponse>(
        `${API_BASE}/public/scan/`,
        { url },
        { headers: { 'Content-Type': 'application/json' } }
      );
      setScanResult(response.data);

      try {
        sessionStorage.setItem('has_scanned', 'true');
      } catch {
        // Ignoré (mode navigation privée)
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>;

      if (axiosError.response?.status === 429) {
        setIsRateLimited(true);
      } else {
        setError(
          axiosError.response?.data?.detail ??
            "Une erreur est survenue lors du scan. Veuillez réessayer."
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const dismissRateLimitModal = useCallback(() => {
    setIsRateLimited(false);
  }, []);

  return {
    loading,
    error,
    isRateLimited,
    scanResult,
    triggerScan,
    dismissRateLimitModal,
  };
}

export default usePublicScan;
