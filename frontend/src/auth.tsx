import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';

export type AuthUser = { name: string; email: string; createdAt: string };

type StoredUser = AuthUser & { pass: string };

const USERS_KEY = 'regimelab.users';
const SESSION_KEY = 'regimelab.session';

function readUsers(): StoredUser[] {
  try {
    const raw = localStorage.getItem(USERS_KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function writeUsers(list: StoredUser[]) {
  try {
    localStorage.setItem(USERS_KEY, JSON.stringify(list));
  } catch {
    /* ignore */
  }
}

async function hashPassword(password: string): Promise<string> {
  try {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`regimelab:${password}`));
    return Array.from(new Uint8Array(bytes))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');
  } catch {
    // crypto.subtle yoksa (http dışı bağlam) basit karma
    let h = 0;
    const s = `regimelab:${password}`;
    for (let i = 0; i < s.length; i++) h = (Math.imul(h, 31) + s.charCodeAt(i)) | 0;
    return `fallback:${h >>> 0}`;
  }
}

function readSession(): string | null {
  try {
    return localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

function writeSession(email: string, remember: boolean) {
  try {
    if (remember) {
      localStorage.setItem(SESSION_KEY, email);
      sessionStorage.removeItem(SESSION_KEY);
    } else {
      sessionStorage.setItem(SESSION_KEY, email);
      localStorage.removeItem(SESSION_KEY);
    }
  } catch {
    /* ignore */
  }
}

function clearSession() {
  try {
    localStorage.removeItem(SESSION_KEY);
    sessionStorage.removeItem(SESSION_KEY);
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

const normalizeEmail = (email: string) => email.trim().toLowerCase();

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const email = readSession();
    if (email) {
      const hit = readUsers().find((u) => u.email === normalizeEmail(email));
      if (hit) setUser({ name: hit.name, email: hit.email, createdAt: hit.createdAt });
      else {
        // Demo oturumu veya silinmiş kullanıcı: demo ise yerinde tut
        if (normalizeEmail(email) === DEMO_USER.email) {
          setUser({ name: DEMO_USER.name, email: DEMO_USER.email, createdAt: new Date().toISOString() });
        } else clearSession();
      }
    }
    setReady(true);
  }, []);

  const login = useCallback(async (email: string, password: string, remember: boolean) => {
    const mail = normalizeEmail(email);
    const hit = readUsers().find((u) => u.email === mail);
    const hash = await hashPassword(password);
    if (!hit || hit.pass !== hash) throw new Error('auth.invalidCredentials');
    writeSession(hit.email, remember);
    setUser({ name: hit.name, email: hit.email, createdAt: hit.createdAt });
  }, []);

  const register = useCallback(async (name: string, email: string, password: string) => {
    const mail = normalizeEmail(email);
    const users = readUsers();
    if (users.some((u) => u.email === mail)) throw new Error('auth.emailTaken');
    const newcomer: StoredUser = {
      name: name.trim(),
      email: mail,
      pass: await hashPassword(password),
      createdAt: new Date().toISOString(),
    };
    writeUsers([...users, newcomer]);
    writeSession(newcomer.email, true);
    setUser({ name: newcomer.name, email: newcomer.email, createdAt: newcomer.createdAt });
  }, []);

  const loginWithDemo = useCallback(async () => {
    const users = readUsers();
    if (!users.some((u) => u.email === DEMO_USER.email)) {
      writeUsers([
        ...users,
        {
          name: DEMO_USER.name,
          email: DEMO_USER.email,
          pass: await hashPassword(DEMO_USER.password),
          createdAt: new Date().toISOString(),
        },
      ]);
    }
    writeSession(DEMO_USER.email, true);
    const hit = readUsers().find((u) => u.email === DEMO_USER.email)!;
    setUser({ name: hit.name, email: hit.email, createdAt: hit.createdAt });
  }, []);

  const logout = useCallback(() => {
    clearSession();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, ready, login, register, loginWithDemo, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
