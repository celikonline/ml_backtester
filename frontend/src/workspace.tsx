import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { request } from './platform-api';
import { getStoredWorkspaceCode, getStoredWorkspaceId, setUrlWorkspaceCode, storeWorkspace, urlWorkspaceCode } from './ws-store';

export type Workspace = {
  id: string; code: string; name: string; description: string;
  market: string; base_currency: string; timezone: string;
  is_archived: number; experiment_count: number; dataset_count: number;
};

type WorkspaceContextValue = {
  workspaces: Workspace[];
  current: Workspace | null;
  currentId: string | null;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  switchWorkspace: (idOrCode: string) => void;
  createWorkspace: (name: string, market: string) => Promise<Workspace>;
  archiveWorkspace: (id: string) => Promise<void>;
};

const WorkspaceContext = createContext<WorkspaceContextValue>({
  workspaces: [], current: null, currentId: null, loading: true, error: '',
  refresh: async () => {}, switchWorkspace: () => {},
  createWorkspace: async () => { throw new Error('unavailable'); },
  archiveWorkspace: async () => {},
});

function pickId(list: Workspace[]): string | null {
  if (!list.length) return null;
  const url = urlWorkspaceCode();
  if (url) {
    const hit = list.find(w => w.code === url || w.id === url);
    if (hit) return hit.id;
  }
  const stored = getStoredWorkspaceId();
  if (stored && list.some(w => w.id === stored)) return stored;
  const storedCode = getStoredWorkspaceCode();
  if (storedCode) {
    const hit = list.find(w => w.code === storedCode);
    if (hit) return hit.id;
  }
  const def = list.find(w => w.code === 'WS-DEFAULT');
  return (def || list[0]).id;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [currentId, setCurrentId] = useState<string | null>(() => getStoredWorkspaceId());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const refresh = useCallback(async () => {
    try {
      const list = await request<Workspace[]>('/workspaces');
      setWorkspaces(list);
      setError('');
      setCurrentId(prev => {
        const next = list.some(w => w.id === prev) ? prev : pickId(list);
        const ws = list.find(w => w.id === next);
        if (ws) { storeWorkspace(ws.id, ws.code); setUrlWorkspaceCode(ws.code); }
        return next;
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const switchWorkspace = useCallback((idOrCode: string) => {
    setWorkspaces(prev => {
      const ws = prev.find(w => w.id === idOrCode || w.code === idOrCode);
      if (ws) { storeWorkspace(ws.id, ws.code); setUrlWorkspaceCode(ws.code); setCurrentId(ws.id); }
      return prev;
    });
  }, []);

  const createWorkspace = useCallback(async (name: string, market: string) => {
    const ws = await request<Workspace>('/workspaces', 'POST', { name, market });
    await refresh();
    storeWorkspace(ws.id, ws.code);
    setUrlWorkspaceCode(ws.code);
    setCurrentId(ws.id);
    return ws;
  }, [refresh]);

  const archiveWorkspace = useCallback(async (id: string) => {
    await request(`/workspaces/${id}/archive`, 'POST');
    await refresh();
  }, [refresh]);

  const current = workspaces.find(w => w.id === currentId) || null;
  return <WorkspaceContext.Provider value={{ workspaces, current, currentId, loading, error, refresh, switchWorkspace, createWorkspace, archiveWorkspace }}>{children}</WorkspaceContext.Provider>;
}

export const useWorkspace = () => useContext(WorkspaceContext);
