import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

export type AuthUser = { name: string; email: string; id: string; role: string; session_id?: string };

const TOKEN_KEY = 'regimelab.token';
const SESSION_KEY = 'regimelab.session';

export function getToken(): string | null {
  return readToken();
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string, remember: boolean) {
  try {
    if (remember) {
      localStorage.setItem(TOKEN_KEY, token);
      sessionStorage.removeItem(TOKEN_KEY);
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
      localStorage.removeItem(TOKEN_KEY);
    }
  } catch {
    /* ignore */
  }
}

function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore */
  }
}

export const DEMO_USER = { name: 'Demo Quant', email: 'demo@regimelab.io', password: 'demo1234' };

type AuthContextValue = {
  user: AuthUser | null;
  ready: boolean;
  login: (email: string, password: string, remember: boolean) => Promise<void>;
  register: (name: string, email: string, password: string) => Promise<void>;
  loginWithDemo: () => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue>({
  user: null,
  ready: false,
  login: async () => {},
  register: async () => {},
  loginWithDemo: async () => {},
  logout: () => {},
});

const API_BASE = '/api';

function authRequestHeaders(lang?: string): Record<string, string> {
  let requested = lang;
  if (!requested) {
    try { requested = localStorage.getItem('regimelab.lang') || 'tr'; } catch { requested = 'tr'; }
  }
  return { 'Content-Type': 'application/json', 'Accept-Language': requested };
}

function authErrorMessage(data: any, fallback: string): string {
  const code = data?.error?.code;
  if (code === 'email_conflict') return 'auth.emailTaken';
  if (code === 'invalid_credentials') return 'auth.invalidCredentials';
  return data?.detail || data?.error?.message || fallback;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = readToken();
    if (token) {
      fetch(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data) setUser({ name: data.name, email: data.email, id: data.id, role: data.role || 'user', session_id: data.session_id });
          else clearToken();
        })
        .catch(() => clearToken());
    }
    setReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: authRequestHeaders(),
      body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(authErrorMessage(data, 'auth.loginFailed'));
    }
    const data = await res.json();
    writeToken(data.token, remember);
    setUser({ name: data.name, email: data.email, id: data.id, role: data.role || 'user', session_id: data.session_id });
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: authRequestHeaders(),
      body: JSON.stringify({ name: name.trim(), email: email.trim().toLowerCase(), password }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(authErrorMessage(data, 'auth.registerFailed'));
    }
    const data = await res.json();
    writeToken(data.token, true);
    setUser({ name: data.name, email: data.email, id: data.id, role: data.role || 'user', session_id: data.session_id });
  }, []);

  const loginWithDemo = useCallback(async () => {
    await login(DEMO_USER.email, DEMO_USER.password, true);
  }, [login]);

  const logout = useCallback(async () => {
    // Server-side session revoke first; the JWT must stop working everywhere.
    const token = readToken();
    if (token) {
      try {
        await fetch(`${API_BASE}/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        });
      } catch {
        /* offline — still clear local state */
      }
    }
    clearToken();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, ready, login, register, loginWithDemo, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
