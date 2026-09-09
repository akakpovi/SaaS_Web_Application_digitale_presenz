import React, { createContext, useState, useContext, useEffect, ReactNode } from 'react';
import { api } from '../services/api';

interface User {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
}

interface Plan {
  tier: 'free' | 'pro' | 'business';
  max_websites: number;
}

interface AuthContextType {
  user: User | null;
  plan: Plan | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, full_name: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  isAuthenticated: boolean;
}

// ✅ Exporter AuthContext
export const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setUser(null);
        setPlan(null);
        return;
      }
      const res = await api.get('/auth/me/', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUser(res.data);
      
      try {
        const subRes = await api.get('/subscriptions/me/', {
          headers: { Authorization: `Bearer ${token}` }
        });
        setPlan(subRes.data.plan);
      } catch (e) {
        setPlan({ tier: 'free', max_websites: 1 });
      }
    } catch (error) {
      localStorage.removeItem('access_token');
      setUser(null);
      setPlan(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshUser();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.post('/auth/login/', { email, password });
    localStorage.setItem('access_token', res.data.access);
    localStorage.setItem('refresh_token', res.data.refresh);
    await refreshUser();
  };

  const register = async (email: string, password: string, full_name: string) => {
    await api.post('/auth/register/', { email, password, full_name });
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    setPlan(null);
  };

  const value: AuthContextType = {
    user,
    plan,
    loading,
    login,
    register,
    logout,
    refreshUser,
    isAuthenticated: !!user,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ✅ Exporter useAuth directement depuis ce fichier
export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
