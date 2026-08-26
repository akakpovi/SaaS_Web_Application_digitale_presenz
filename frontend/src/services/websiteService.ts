import api from './api';

export interface Website {
  id: number;
  domain: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CheckResult {
  category: string;
  status: 'healthy' | 'warning' | 'critical' | 'neutral';
  score: number | null;
  summary: string;
  recommendation: string;
  technical_details?: Record<string, any> | null;
}

export interface Scan {
  id: number;
  website: number;
  status: string;
  trigger: string;
  health_score: number | null;
  health_status: 'healthy' | 'warning' | 'critical' | 'neutral';
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  results?: CheckResult[];
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export const websiteService = {

  async list(): Promise<Website[]> {
    const { data } = await api.get<PaginatedResponse<Website>>('/websites/');
    return data.results;
  },

  async get(id: number): Promise<Website> {
    const { data } = await api.get<Website>(`/websites/${id}/`);
    return data;
  },

  async create(domain: string, display_name?: string): Promise<Website> {
    const { data } = await api.post<Website>('/websites/', {
      domain,
      display_name: display_name || domain,
    });
    return data;
  },

  async delete(id: number): Promise<void> {
    await api.delete(`/websites/${id}/`);
  },

  async scan(id: number): Promise<Scan> {
    const { data } = await api.post<Scan>(`/websites/${id}/scan/`);
    return data;
  },
};

export const scanService = {

  async list(websiteId?: number): Promise<Scan[]> {
    const params = websiteId ? `?website=${websiteId}` : '';
    const { data } = await api.get<PaginatedResponse<Scan>>(`/scans/${params}`);
    return data.results;
  },

  async get(id: number): Promise<Scan> {
    const { data } = await api.get<Scan>(`/scans/${id}/`);
    return data;
  },

  async getResults(id: number): Promise<CheckResult[]> {
    const { data } = await api.get<CheckResult[]>(`/scans/${id}/results/`);
    return data;
  },
};
