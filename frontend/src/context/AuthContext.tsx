import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import api from '../api/client';

interface AuthContextType {
  token: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem('doclens_token')
  );

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post('/auth/login', { email, password });
    const { access_token } = res.data;
    localStorage.setItem('doclens_token', access_token);
    setToken(access_token);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    await api.post('/auth/signup', { email, password });
    // Auto-login after signup
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    localStorage.removeItem('doclens_token');
    setToken(null);
  }, []);

  return (
    <AuthContext.Provider value={{ token, isAuthenticated: !!token, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
