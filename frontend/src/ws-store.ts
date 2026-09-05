// Workspace persistence helpers (no imports: safe to use from any module,
// including the API client, without import cycles).
const ID_KEY = 'regimelab.workspace_id';
const CODE_KEY = 'regimelab.workspace_code';

export function getStoredWorkspaceId(): string | null {
  try { return localStorage.getItem(ID_KEY); } catch { return null; }
}

export function getStoredWorkspaceCode(): string | null {
  try { return localStorage.getItem(CODE_KEY); } catch { return null; }
}

export function storeWorkspace(id: string, code: string) {
  try {
    localStorage.setItem(ID_KEY, id);
    localStorage.setItem(CODE_KEY, code);
  } catch { /* ignore */ }
}

export function urlWorkspaceCode(): string | null {
  try {
    return new URLSearchParams(window.location.search).get('workspace');
  } catch { return null; }
}

export function setUrlWorkspaceCode(code: string) {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('workspace', code);
    window.history.replaceState(null, '', url);
  } catch { /* ignore */ }
}
