import api from './api';

export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  is_email_verified: boolean;
}

export interface AuthTokens {
  access: string;
  refresh: string;
  user: User;
}

export interface RegisterResponse {
  user: User;
  detail: string;
}

export const authService = {

  // Register : retourne juste le message, pas de tokens
  async register(email: string, password: string, full_name: string): Promise<RegisterResponse> {
    const { data } = await api.post<RegisterResponse>('/auth/register/', {
      email,
      password,
      full_name,
    });
    return data;
  },

  // Login : retourne access + refresh + user
  async login(email: string, password: string): Promise<User> {
    const { data } = await api.post<AuthTokens>('/auth/login/', { email, password });
    localStorage.setItem('access_token', data.access);
    localStorage.setItem('refresh_token', data.refresh);
    localStorage.setItem('user', JSON.stringify(data.user));
    return data.user;
  },

  async logout(): Promise<void> {
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
      try {
        await api.post('/auth/logout/', { refresh });
      } catch { /* blacklist echoue = pas grave */ }
    }
    localStorage.clear();
  },

  async fetchMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me/');
    localStorage.setItem('user', JSON.stringify(data));
    return data;
  },

  getCurrentUser(): User | null {
    const raw = localStorage.getItem('user');
    return raw ? JSON.parse(raw) : null;
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('access_token');
  },
};
