import api from './api';
import { PaginatedResponse } from './websiteService';

export interface Alert {
  id: string;
  website_id: number;
  website_domain?: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  status: 'firing' | 'acknowledged' | 'resolved';
  title: string;
  message: string;
  created_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export const alertService = {

  async list(params?: { status?: string; severity?: string }): Promise<Alert[]> {
    const query = new URLSearchParams(params as Record<string, string>).toString();
    const { data } = await api.get<PaginatedResponse<Alert>>(`/alerts/${query ? '?' + query : ''}`);
    return data.results;
  },

  async acknowledge(id: string): Promise<Alert> {
    const { data } = await api.post<Alert>(`/alerts/${id}/acknowledge/`);
    return data;
  },

  async resolve(id: string): Promise<Alert> {
    const { data } = await api.post<Alert>(`/alerts/${id}/resolve/`);
    return data;
  },
};
