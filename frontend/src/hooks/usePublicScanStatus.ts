// frontend/src/hooks/usePublicScanStatus.ts
// Hook réservé au chargement et au suivi de la progression d'un scan existant

import React, { useEffect, useState, useCallback, useRef } from 'react';
import axios, { AxiosError } from 'axios';
import type { PublicScanResponse } from '../types/publicScan';

const API_BASE = import.meta.env.VITE_API_URL ?? '/api/v1';

interface UsePublicScanStatusResult {
  scan: PublicScanResponse | null;
  loading: boolean;
  error: 'not_found' | 'rate_limited' | 'unknown' | null;
  retryMinutes: number;
  rescan: (url: string) => Promise<string | null>;
  sendEmail: (scanId: string, email: string) => Promise<boolean>;
}

export function usePublicScanStatus(scanId: string | undefined): UsePublicScanStatusResult {
  const [scan, setScan] = useState<PublicScanResponse | null>(null);
  // Initialisé à true car le chargement commence dès l'affichage du composant
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<'not_found' | 'rate_limited' | 'unknown' | null>(null);
  const [retryMinutes, setRetryMinutes] = useState(0);
  const pollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchScan = useCallback(async () => {
    if (!scanId) return;
    try {
      const resp = await axios.get<PublicScanResponse>(
        `${API_BASE}/public/scan/${scanId}/status/`
      );
      setScan(resp.data);
      setError(null);

      // Si le scan est encore en file d'attente ou en cours, continuer le polling
      if (['pending', 'processing', 'queued'].includes(resp.data.status)) {
        pollTimerRef.current = setTimeout(fetchScan, 3000);
      } else {
        setLoading(false);
      }
    } catch (err) {
      const axiosErr = err as AxiosError;
      if (axiosErr.response?.status === 404) {
        setError('not_found');
      } else if (axiosErr.response?.status === 429) {
        setError('rate_limited');
        const retryAfter = axiosErr.response.headers['retry-after'];
        setRetryMinutes(retryAfter ? Math.ceil(parseInt(retryAfter as string, 10) / 60) : 60);
      } else {
        setError('unknown');
      }
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    if (!scanId) {
      setLoading(false);
      return;
    }
    
    fetchScan();

    return () => {
      if (pollTimerRef.current) {
        clearTimeout(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [scanId, fetchScan]);

  const rescan = useCallback(async (url: string): Promise<string | null> => {
    try {
      const resp = await axios.post(`${API_BASE}/public/scan/`, { url });
      return resp.data?.scan_id ?? null;
    } catch {
      return null;
    }
  }, []);

  const sendEmail = useCallback(async (id: string, email: string): Promise<boolean> => {
    try {
      await axios.post(`${API_BASE}/public/scan/${id}/email/`, { email });
      return true;
    } catch {
      return false;
    }
  }, []);

  return { scan, loading, error, retryMinutes, rescan, sendEmail };
}

export default usePublicScanStatus;
